from django.db import models, transaction
from django.contrib.auth.models import User
from patient.models import PatientModel


class ServiceCategory(models.Model):
    """Categories for organizing services and items
    Example might be dentist, eyes, glass
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    show_as_record_column = models.BooleanField(
        default=False,
        help_text="Show this category as a separate column in daily reports"
    )
    category_type = models.CharField(
        max_length=20,
        choices=[
            ('service', 'Service/Procedure'),
            ('item', 'Item/Product'),
            ('mixed', 'Both Services and Items')
        ],
        default='mixed'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name_plural = "Service Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def total_services(self):
        return self.services.filter(is_active=True).count()

    @property
    def total_items(self):
        return self.service_items.filter(is_active=True).count()


class Service(models.Model):
    """Individual services/procedures offered"""
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.CASCADE,
        related_name='services'
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Default price (can be overridden during transaction)"
    )
    has_results = models.BooleanField(
        default=False,
        help_text="Does this service produce results that need to be recorded?"
    )

    result_template = models.JSONField(
        blank=True,
        null=True,
        help_text="Template for recording results in JSON format"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ['category', 'name']
        ordering = ['category__name', 'name']

    def __str__(self):
        return f"{self.category.name} - {self.name}"


class ServiceItem(models.Model):
    """Physical items/products like glasses, drugs, supplies"""
    category = models.ForeignKey(
        ServiceCategory,
        on_delete=models.CASCADE,
        related_name='service_items'
    )
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True, null=True)
    model_number = models.CharField(max_length=100, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    cost_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Purchase/cost price for profit calculation"
    )
    stock_quantity = models.IntegerField(default=0)
    minimum_stock_level = models.IntegerField(default=5)
    unit_of_measure = models.CharField(
        max_length=20,
        choices=[
            ('piece', 'Piece'),
            ('pair', 'Pair'),
            ('box', 'Box'),
            ('bottle', 'Bottle'),
            ('pack', 'Pack'),
            ('meter', 'Meter'),
            ('liter', 'Liter'),
            ('kg', 'Kilogram'),
        ],
        default='piece'
    )
    expiry_date = models.DateField(null=True, blank=True)
    is_prescription_required = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        unique_together = ['category', 'name', 'model_number']
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


class PatientModelServiceTransaction(models.Model):
    """Records of services/items provided to patientModels"""
    patientModel = models.ForeignKey(PatientModel, on_delete=models.CASCADE)

    # Service or Item (only one should be filled)
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='transactions'
    )
    service_item = models.ForeignKey(
        ServiceItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='transactions'
    )

    # Transaction details
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price per unit at time of transaction"
    )
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Total discount applied"
    )
    total_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Final amount after discount"
    )

    # Payment status
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('paid', 'Paid'),
            ('partial', 'Partially Paid'),
            ('waived', 'Waived'),
            ('cancelled', 'Cancelled')
        ],
        default='pending'
    )
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    # Related records
    consultation_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Link to consultation if applicable"
    )
    admission_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Link to admission if applicable"
    )
    surgery_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Link to surgery if applicable"
    )

    # Tracking
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_services'
    )
    recorded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_services'
    )
    notes = models.TextField(blank=True, null=True)
    transaction_date = models.DateTimeField(auto_now_add=True)
    service_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the service was actually performed (if different from recorded)"
    )

    class Meta:
        ordering = ['-transaction_date']

    def clean(self):
        from django.core.exceptions import ValidationError
        # Ensure either service or service_item is provided, not both
        if not self.service and not self.service_item:
            raise ValidationError("Either service or service_item must be provided")
        if self.service and self.service_item:
            raise ValidationError("Cannot have both service and service_item")

    def save(self, *args, **kwargs):
        """
        Overridden save method to handle stock movements atomically and correctly
        for both new and updated transactions.
        """
        # Use a database transaction to ensure all or nothing completes.
        with transaction.atomic():
            # 1. Keep track of the original state if this is an update
            original_state = None
            if self.pk:
                original_state = PatientModelServiceTransaction.objects.get(pk=self.pk)

            # 2. Calculate financial totals
            subtotal = self.unit_price * self.quantity
            self.total_amount = subtotal - self.discount

            # 3. Save the transaction itself
            super().save(*args, **kwargs)

            # --- Stock Management Logic ---

            # 4. Reverse the original stock movement if it existed and has changed
            if original_state and original_state.service_item and original_state.payment_status != 'cancelled':
                # Check if the item, quantity, or status has changed in a way that requires reversal
                if (self.service_item != original_state.service_item or
                        self.quantity != original_state.quantity or
                        self.payment_status == 'cancelled'):
                    # Create a "return" movement to reverse the original deduction
                    ServiceItemStockMovement.objects.create(
                        service_item=original_state.service_item,
                        movement_type='return',
                        quantity=original_state.quantity,  # Positive quantity to add stock back
                        reference_type='sale_reversal',
                        reference_id=self.pk,
                        notes=f"Reversal for updated transaction #{self.pk}",
                        created_by=getattr(self, 'recorded_by', None)
                    )

            # 5. Apply the new stock movement if necessary
            # We check the original state to avoid double-counting stock movement if nothing relevant changed
            is_new_movement_needed = (original_state is None or
                                      self.service_item != original_state.service_item or
                                      self.quantity != original_state.quantity or
                                      self.payment_status != original_state.payment_status)

            if self.service_item and self.payment_status != 'cancelled' and is_new_movement_needed:
                # Create the new "sale" movement
                ServiceItemStockMovement.objects.create(
                    service_item=self.service_item,
                    movement_type='sale',
                    quantity=-self.quantity,  # Negative quantity to deduct stock
                    reference_type='sale',
                    reference_id=self.pk,
                    notes=f"Sale from transaction #{self.pk}",
                    created_by=getattr(self, 'recorded_by', None)
                )

    def __str__(self):
        item_name = self.service.name if self.service else self.service_item.name
        return f"{self.patientModel} - {item_name} ({self.transaction_date.strftime('%Y-%m-%d')})"

    @property
    def balance_due(self):
        return self.total_amount - self.amount_paid

    @property
    def category_name(self):
        if self.service:
            return self.service.category.name
        return self.service_item.category.name


class ServiceItemStockMovement(models.Model):
    """Track all stock movements for service items"""
    service_item = models.ForeignKey(
        ServiceItem,
        on_delete=models.CASCADE,
        related_name='stock_movements'
    )
    movement_type = models.CharField(
        max_length=20,
        choices=[
            ('stock_in', 'Stock In'),
            ('stock_out', 'Stock Out'),
            ('adjustment', 'Stock Adjustment'),
            ('transfer', 'Transfer'),
            ('expired', 'Expired/Damaged'),
            ('sale', 'Sale to PatientModel'),
            ('return', 'Return from PatientModel')
        ]
    )
    quantity = models.IntegerField(help_text="Positive for in, negative for out")
    unit_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Cost per unit for stock-in transactions"
    )
    total_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Total cost for this movement"
    )
    previous_stock = models.IntegerField(help_text="Stock level before this movement")
    new_stock = models.IntegerField(help_text="Stock level after this movement")

    # Reference documents
    reference_type = models.CharField(
        max_length=20,
        choices=[
            ('purchase', 'Purchase Order'),
            ('sale', 'PatientModel Sale'),
            ('transfer', 'Stock Transfer'),
            ('adjustment', 'Stock Adjustment'),
            ('expiry', 'Expiry/Damage'),
            ('return', 'Return')
        ],
        null=True,
        blank=True
    )
    reference_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="ID of related transaction/document"
    )

    # Supplier/destination info
    batch_number = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.DateField(null=True, blank=True)

    # Tracking
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Calculate new stock level
        if not self.pk:  # New record
            self.previous_stock = self.service_item.stock_quantity
            self.new_stock = self.previous_stock + self.quantity

            # Calculate total cost for stock-in
            if self.movement_type == 'stock_in' and self.unit_cost:
                self.total_cost = abs(self.quantity) * self.unit_cost

        super().save(*args, **kwargs)

        # Update service item stock
        self.service_item.stock_quantity = self.new_stock

        # Update cost price if it's a stock-in with unit cost
        if self.movement_type == 'stock_in' and self.unit_cost:
            self.service_item.cost_price = self.unit_cost

        self.service_item.save()

    def __str__(self):
        return f"{self.service_item.name} - {self.get_movement_type_display()} ({self.quantity})"


class ServiceResult(models.Model):
    transaction = models.ForeignKey(
        PatientModelServiceTransaction,
        on_delete=models.CASCADE,
        related_name='results'
    )

    # Change this to JSONField
    result_data = models.JSONField(
        help_text="The actual result data in JSON format"
    )

    # Keep these for metadata
    result_file = models.FileField(
        upload_to='service_results/',
        null=True,
        blank=True,
        help_text="For file attachments (X-rays, reports, etc.)"
    )

    is_abnormal = models.BooleanField(default=False)
    interpretation = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='service_created_by', blank=True)

    def __str__(self):
        return f"Result for {self.transaction}"