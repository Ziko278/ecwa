from django.db import models, transaction
from django.contrib.auth.models import User
from django.utils import timezone

from patient.models import PatientModel


class ServiceCategory(models.Model):
    """Categories for organizing services and items"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    category_type = models.CharField(
        max_length=20,
        choices=[
            ('service', 'Service/Procedure'),
            ('item', 'Item/Product'),
            ('mixed', 'Both Services and Items')
        ],
        default='mixed'
    )
    show_as_record_column = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Service Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class Service(models.Model):
    """Individual services/procedures offered"""
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='services')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    has_results = models.BooleanField(default=False)
    result_template = models.JSONField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['category', 'name']
        ordering = ['category__name', 'name']

    def __str__(self):
        return f"{self.category.name} - {self.name}"


class ServiceItem(models.Model):
    """Physical items/products like glasses, drugs, supplies"""
    category = models.ForeignKey(ServiceCategory, on_delete=models.CASCADE, related_name='service_items')
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_quantity = models.IntegerField(default=0)
    minimum_stock_level = models.IntegerField(default=5)
    unit_of_measure = models.CharField(
        max_length=20,
        choices=[
            ('piece', 'Piece'), ('pair', 'Pair'), ('box', 'Box'),
            ('bottle', 'Bottle'), ('pack', 'Pack'), ('kg', 'Kilogram'),
        ],
        default='piece'
    )
    expiry_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['category', 'name']
        ordering = ['category__name', 'name']

    def __str__(self):
        return f"{self.category.name} - {self.name}"

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.minimum_stock_level

    @property
    def is_expired(self):
        if self.expiry_date:
            from django.utils import timezone
            return self.expiry_date < timezone.now().date()
        return False


class PatientServiceTransaction(models.Model):
    """Records of services/items provided to patients"""
    patient = models.ForeignKey(PatientModel, on_delete=models.CASCADE)

    # Service or Item (only one should be filled)
    service = models.ForeignKey(Service, on_delete=models.CASCADE, null=True, blank=True, related_name='transactions')
    service_item = models.ForeignKey(ServiceItem, on_delete=models.CASCADE, null=True, blank=True,
                                     related_name='transactions')

    # Transaction details
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantity_dispensed = models.PositiveIntegerField(default=0,
                                                     help_text="How many units of the item have been given to the patient.")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    admission = models.ForeignKey(
        'inpatient.Admission', on_delete=models.SET_NULL, null=True, blank=True, related_name='service_drug_orders',
        help_text="Link to an admission record if applicable"
    )
    surgery = models.ForeignKey(
        'inpatient.Surgery', on_delete=models.SET_NULL, null=True, blank=True, related_name='service_drug_orders',
        help_text="Link to a surgery record if applicable"
    )

    consultation = models.ForeignKey(
        'consultation.ConsultationSessionModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='service_drug_consultation_order',
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ('pending_payment', 'Pending Payment'),
            ('paid', 'Paid'),
            ('partially_dispensed', 'Partially Dispensed'),
            ('fully_dispensed', 'Fully Dispensed'),
            ('cancelled', 'Cancelled')
        ],
        default='pending_payment'
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Basic tracking
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def clean(self):
        from django.core.exceptions import ValidationError
        if not self.service and not self.service_item:
            raise ValidationError("Either service or service_item must be provided")
        if self.service and self.service_item:
            raise ValidationError("Cannot have both service and service_item")

    def save(self, *args, **kwargs):
        """
        Handles financial calculations and triggers stock movements
        based on specific status changes.
        """
        with transaction.atomic():
            original_state = None
            if self.pk:
                # Get the state of the object *before* any changes were made
                original_state = PatientServiceTransaction.objects.get(pk=self.pk)

            # Always calculate totals on every save
            subtotal = self.unit_price * self.quantity
            self.total_amount = subtotal - self.discount

            # Save the primary object first
            super().save(*args, **kwargs)

            # --- NEW, PRECISE STOCK DEDUCTION LOGIC ---
            # This block runs only if the object is being updated (not created)
            if original_state:
                # Condition 1: Was the item just dispensed?
                # Check if the status changed FROM 'paid' or 'partially_dispensed'
                # TO 'partially_dispensed' or 'fully_dispensed'.
                was_just_dispensed = (
                        original_state.status in ['paid', 'partially_dispensed'] and
                        self.status in ['partially_dispensed', 'fully_dispensed']
                )

                # Condition 2: Did the dispensed quantity actually increase?
                quantity_was_added = self.quantity_dispensed > original_state.quantity_dispensed

                if was_just_dispensed and quantity_was_added:
                    # Calculate exactly how much was given out in this specific action
                    quantity_to_deduct = self.quantity_dispensed - original_state.quantity_dispensed

                    # Create the stock movement for that specific amount
                    ServiceItemStockMovement.objects.create(
                        service_item=self.service_item,
                        movement_type='sale',
                        quantity=-quantity_to_deduct,  # Deduct only the new amount
                        reference_type='sale',
                        reference_id=self.pk,
                        notes=f"Dispensed {quantity_to_deduct} units from transaction #{self.pk}",
                        created_by=self.performed_by
                    )

            # --- CANCELLATION/RETURN LOGIC ---
            # If the transaction is cancelled, return the stock
            if original_state and self.status == 'cancelled' and original_state.status != 'cancelled':
                # Check how much had been dispensed before cancellation
                quantity_to_return = original_state.quantity_dispensed
                if quantity_to_return > 0:
                    ServiceItemStockMovement.objects.create(
                        service_item=self.service_item,
                        movement_type='return',
                        quantity=quantity_to_return,  # Positive to return stock
                        reference_type='sale_reversal',
                        reference_id=self.pk,
                        notes=f"Return from cancelled transaction #{self.pk}",
                        created_by=self.performed_by
                    )

    def __str__(self):
        item_name = self.service.name if self.service else self.service_item.name
        return f"{self.patient} - {item_name} ({self.created_at.strftime('%Y-%m-%d')})"

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    @property
    def category_name(self):
        if self.service:
            return self.service.category.name
        return self.service_item.category.name

    @property
    def quantity_remaining(self):
        if self.service_item:
            return self.quantity - self.quantity_dispensed
        return 0


class ServiceItemBatch(models.Model):
    """Tracks different batches/purchases of service items"""
    name = models.CharField(max_length=250, blank=True, unique=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = "Service Item Batches"

    def __str__(self):
        return self.name.upper()

    def save(self, *args, **kwargs):
        if not self.name:
            # Get the highest existing batch number by name
            last_batch = ServiceItemBatch.objects.filter(
                name__startswith='BATCH-'
            ).order_by('name').last()

            if last_batch and last_batch.name.startswith('BATCH-'):
                try:
                    # Extract number from BATCH-0001 format
                    last_number = int(last_batch.name.split('-')[1])
                    next_id = last_number + 1
                except (IndexError, ValueError):
                    next_id = 1  # Fallback if parsing fails
            else:
                next_id = 1  # No previous batches found

            # Generate unique batch name, handling potential race conditions
            while True:
                batch_name = f'BATCH-{str(next_id).zfill(4)}'
                if not ServiceItemBatch.objects.filter(name=batch_name).exists():
                    self.name = batch_name
                    break
                next_id += 1  # If name exists, try the next number

        super().save(*args, **kwargs)


class ServiceItemStockMovement(models.Model):
    """Track stock movements for service items"""
    service_item = models.ForeignKey(ServiceItem, on_delete=models.CASCADE, related_name='stock_movements')
    batch = models.ForeignKey(
        ServiceItemBatch,
        on_delete=models.SET_NULL,
        related_name='stock_entries', null=True, blank=True
    )
    movement_type = models.CharField(
        max_length=20,
        choices=[
            ('stock_in', 'Stock In'),
            ('stock_out', 'Stock Out'),
            ('adjustment', 'Stock Adjustment'),
            ('sale', 'Sale to Patient'),
            ('return', 'Return from Patient'),
            ('expired', 'Expired/Damaged')
        ]
    )
    quantity = models.IntegerField(help_text="Positive for in, negative for out")
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    previous_stock = models.IntegerField(help_text="Stock level before this movement")
    new_stock = models.IntegerField(help_text="Stock level after this movement")

    reference_type = models.CharField(
        max_length=20,
        choices=[
            ('purchase', 'Purchase Order'),
            ('sale', 'Patient Sale'),
            ('adjustment', 'Stock Adjustment'),
            ('sale_reversal', 'Sale Reversal'),
            ('expiry', 'Expiry/Damage')
        ],
        null=True, blank=True
    )
    reference_id = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL, null=True, blank=True
    )

    # Supplier/batch info
    batch_number = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.DateField(null=True, blank=True)

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.pk:  # New record
            self.previous_stock = self.service_item.stock_quantity
            self.new_stock = self.previous_stock + self.quantity

        super().save(*args, **kwargs)

        # Update service item stock and cost
        self.service_item.stock_quantity = self.new_stock
        if self.movement_type == 'stock_in' and self.unit_cost:
            self.service_item.cost_price = self.unit_cost
        self.service_item.save()

    def __str__(self):
        return f"{self.service_item.name} - {self.get_movement_type_display()} ({self.quantity})"


class ServiceResult(models.Model):
    """Store service results"""
    transaction = models.OneToOneField(PatientServiceTransaction, on_delete=models.CASCADE, related_name='result')
    result_data = models.JSONField(help_text="The actual result data in JSON format")
    result_file = models.FileField(upload_to='service_results/', null=True, blank=True)
    is_abnormal = models.BooleanField(default=False)
    interpretation = models.TextField(blank=True, null=True)

    # --- NEW FIELDS ---
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='verified_service_results')
    verified_at = models.DateTimeField(null=True, blank=True)
    # --- END NEW FIELDS ---

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='created_service_results')

    def __str__(self):
        return f"Result for {self.transaction}"

    def save(self, *args, **kwargs):
        # Automatically set verified_at timestamp when is_verified is set to True
        if self.is_verified and not self.verified_at:
            self.verified_at = timezone.now()
        # If unchecked, clear the timestamp and verifier
        elif not self.is_verified:
            self.verified_at = None
            self.verified_by = None
        super().save(*args, **kwargs)
