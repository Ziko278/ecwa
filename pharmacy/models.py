from django.db import models, transaction
from django.core.validators import MinValueValidator
from django.contrib.auth.models import User
from datetime import date
from decimal import Decimal


# 1. SIMPLIFIED DRUG CATEGORIES
class DrugCategoryModel(models.Model):
    """Categories for easier drug organization"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'drug_categories'
        verbose_name_plural = 'Drug Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


# 2. GENERIC DRUG (Updated with category FK)
class GenericDrugModel(models.Model):
    """
    Represents the generic drug entity (e.g., Paracetamol, Amoxicillin)
    This follows WHO's International Non-proprietary Names (INN) system
    """
    generic_name = models.CharField(max_length=200, unique=True, help_text="WHO/INN generic name")

    # Category relationship
    category = models.ForeignKey(
        DrugCategoryModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='generic_drugs'
    )

    # WHO ATC Classification System - World Standard
    atc_code = models.CharField(
        max_length=10,
        blank=True,
        help_text="WHO ATC code (e.g., N02BE01 for Paracetamol)"
    )

    # Basic properties
    is_prescription_only = models.BooleanField(default=True)

    # Administrative
    status = models.CharField(
        max_length=20,
        choices=[('active', 'ACTIVE'), ('inactive', 'INACTIVE')],
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'generic_drugs'
        ordering = ['generic_name']

    def __str__(self):
        return self.generic_name.title()


# 2. SIMPLIFIED DRUG FORMULATIONS
class DrugFormulationModel(models.Model):
    """Different forms of the same drug (tablet, injection, syrup, etc.)"""
    FORM_CHOICES = [
        ('tablet', 'Tablet'),
        ('capsule', 'Capsule'),
        ('injection', 'Injection'),
        ('syrup', 'Syrup'),
        ('cream', 'Cream'),
        ('drops', 'Drops'),
    ]

    generic_drug = models.ForeignKey(
        GenericDrugModel,
        on_delete=models.CASCADE,
        related_name='formulations'
    )
    form_type = models.CharField(max_length=20, choices=FORM_CHOICES)
    strength = models.CharField(max_length=50, help_text="e.g., 500mg, 250mg/5ml")

    status = models.CharField(
        max_length=20,
        choices=[('active', 'ACTIVE'), ('inactive', 'INACTIVE')],
        default='active'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'drug_formulations'
        unique_together = ['generic_drug', 'form_type', 'strength']
        ordering = ['generic_drug__generic_name', 'form_type']

    def __str__(self):
        return f"{self.generic_drug.generic_name} {self.strength} {self.form_type}"


# 3. SIMPLIFIED MANUFACTURER
class ManufacturerModel(models.Model):
    """Drug manufacturers and suppliers"""
    name = models.CharField(max_length=200, unique=True)
    country = models.CharField(max_length=100, blank=True)
    is_approved = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'drug_manufacturers'
        ordering = ['name']

    def __str__(self):
        return self.name


class DrugModel(models.Model):
    """The actual drug product in your inventory"""
    # Core relationships
    formulation = models.ForeignKey(DrugFormulationModel, on_delete=models.CASCADE, related_name='products')
    manufacturer = models.ForeignKey(ManufacturerModel, on_delete=models.CASCADE, related_name='products', blank=True, null=True)

    # Product identification
    brand_name = models.CharField(max_length=200, blank=True, default='', help_text="Commercial/Brand name")
    sku = models.CharField(max_length=100, blank=True, default='', help_text="Stock Keeping Unit")

    # Stock tracking - Store vs Pharmacy
    store_quantity = models.FloatField(default=0, help_text="Quantity in store/warehouse")
    pharmacy_quantity = models.FloatField(default=0, help_text="Quantity in pharmacy counter")
    minimum_stock_level = models.IntegerField(default=10)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    pack_size = models.PositiveIntegerField(
        default=1, null=True, blank=True,
        help_text="Number of units in a single sellable pack (e.g., 12 tablets per card)."
    )

    # Status
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'drugs'
        ordering = ['formulation__generic_drug__generic_name', 'brand_name']

    def __str__(self):
        # Start with the base representation, using brand_name if available
        if self.brand_name:
            display_text = f"{self.brand_name} ({self.formulation})"
        else:
            display_text = str(self.formulation)

        # Append manufacturer name only if it exists
        if self.manufacturer:
            display_text += f" - {self.manufacturer.name}"

        return display_text

    @property
    def generic_name(self):
        return self.formulation.generic_drug.generic_name

    @property
    def total_quantity(self):
        """Total quantity in both store and pharmacy"""
        return self.store_quantity + self.pharmacy_quantity

    @property
    def is_low_stock(self):
        return self.total_quantity <= self.minimum_stock_level

    @property
    def last_cost_price(self):
        """
        Returns the unit_cost_price from the most recent DrugStockModel entry.
        """

        last_stock = DrugStockModel.objects.filter(drug=self).order_by('-id').first()
        return last_stock.unit_cost_price if last_stock else 0


# 5. DRUG BATCH MODEL (For tracking different purchases)
class DrugBatchModel(models.Model):
    """Track different batches/purchases of drugs"""
    name = models.CharField(max_length=250, blank=True)
    date = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'drug_batches'
        ordering = ['-date']

    def __str__(self):
        return self.name.upper()

    def save(self, *args, **kwargs):
        if not self.name:
            # Get the highest existing batch number
            last_batch = DrugBatchModel.objects.filter(
                name__startswith='batch-'
            ).order_by('name').last()

            if last_batch and last_batch.name.startswith('batch-'):
                try:
                    # Extract number from batch-0001 format
                    last_number = int(last_batch.name.split('-')[1])
                    next_id = last_number + 1
                except (IndexError, ValueError):
                    next_id = 1
            else:
                next_id = 1

            # Generate unique batch name (with safety limit)
            max_attempts = 100
            attempts = 0
            while attempts < max_attempts:
                batch_name = f'batch-{str(next_id).rjust(4, "0")}'
                if not DrugBatchModel.objects.filter(name=batch_name).exists():
                    self.name = batch_name
                    break
                next_id += 1
                attempts += 1

            # Fallback if somehow we hit max attempts
            if not self.name:
                import uuid
                self.name = f'batch-{uuid.uuid4().hex[:8]}'

        if not self.date:
            self.date = date.today()

        super().save(*args, **kwargs)


# 6. DRUG STOCK MODEL (Individual stock entries)
class DrugStockModel(models.Model):
    """Individual stock entries for each drug purchase"""
    LOCATION_CHOICES = [
        ('store', 'Store/Warehouse'),
        ('pharmacy', 'Pharmacy Counter'),
    ]

    drug = models.ForeignKey(DrugModel, on_delete=models.CASCADE, related_name='stock_entries')
    batch = models.ForeignKey(DrugBatchModel, on_delete=models.CASCADE, blank=True, null=True, related_name='stock_items')

    # Quantities
    quantity_bought = models.FloatField()
    quantity_left = models.FloatField(blank=True, default=0)

    # Pricing
    unit_cost_price = models.DecimalField(max_digits=10, decimal_places=2)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2)
    total_cost_price = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    current_worth = models.DecimalField(max_digits=12, decimal_places=2, default=0, blank=True, null=True)

    # Location and dates
    location = models.CharField(max_length=20, choices=LOCATION_CHOICES, default='store')
    expiry_date = models.DateField(blank=True, null=True)
    batch_number = models.CharField(max_length=100, blank=True, default='')

    # Status and tracking
    status = models.CharField(
        max_length=15,
        choices=[('active', 'Active'), ('expired', 'Expired'), ('damaged', 'Damaged')],
        default='active'
    )

    date_added = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'drug_stocks'
        ordering = ['-date_added']

    def __str__(self):
        return f"{self.drug} - Batch: {self.batch}"

    @property
    def is_expired(self):
        if self.expiry_date:
            return self.expiry_date <= date.today()
        return False

    def save(self, *args, **kwargs):
        # Auto-calculate fields before saving
        quantity_bought_decimal = Decimal(str(self.quantity_bought))
        if not self.total_cost_price:
            self.total_cost_price = self.unit_cost_price * quantity_bought_decimal

        if self.quantity_left is None or self.quantity_left == 0:
            self.quantity_left = self.quantity_bought
        quantity_left_decimal = Decimal(str(self.quantity_left))
        self.current_worth = quantity_left_decimal * self.selling_price

        if not self.batch:
            last_batch = DrugBatchModel.objects.last()
            self.batch = last_batch

        # Use a database transaction to ensure data integrity
        with transaction.atomic():
            if not self.pk:  # This is a new entry (creation)
                super().save(*args, **kwargs)  # Save the new stock entry first
                # Now, update the parent drug's quantity
                if self.location == 'store':
                    self.drug.store_quantity += self.quantity_bought
                else:
                    self.drug.pharmacy_quantity += self.quantity_bought
                self.drug.save()
            else:  # This is an existing entry (update)
                # Get the original state from the database *before* saving changes
                original_stock = DrugStockModel.objects.get(pk=self.pk)

                # Step 1: Reverse the old quantities from the parent drug
                if original_stock.location == 'store':
                    self.drug.store_quantity -= original_stock.quantity_bought
                else:
                    self.drug.pharmacy_quantity -= original_stock.quantity_bought

                # Step 2: Save the current stock model with its changes
                super().save(*args, **kwargs)

                # Step 3: Apply the new quantities to the parent drug
                if self.location == 'store':
                    self.drug.store_quantity += self.quantity_bought
                else:
                    self.drug.pharmacy_quantity += self.quantity_bought

                # Step 4: Save the updated parent drug
                self.drug.save()

    def delete(self, *args, **kwargs):
        # Use a database transaction to ensure data integrity
        with transaction.atomic():
            # Get the values before this instance is deleted
            quantity_to_subtract = self.quantity_bought
            location = self.location

            # Update the parent drug by subtracting the quantity
            if location == 'store':
                self.drug.store_quantity -= quantity_to_subtract
            else:
                self.drug.pharmacy_quantity -= quantity_to_subtract
            self.drug.save()

            # Call the original delete method to complete the deletion
            super().delete(*args, **kwargs)


# 7. DRUG STOCK OUT MODEL (Track removals/sales/wastage)
class DrugStockOutModel(models.Model):
    """Track drug removals from stock"""
    REASON_CHOICES = [
        ('sale', 'Sale'),
        ('expired', 'Expired'),
        ('damaged', 'Damaged/Spoilt'),
        ('return', 'Return to Supplier'),
        ('transfer', 'Transfer'),  # Added for internal transfers
        ('other', 'Other'),
    ]

    stock = models.ForeignKey(DrugStockModel, on_delete=models.CASCADE, related_name='stock_outs')
    drug = models.ForeignKey(DrugModel, on_delete=models.CASCADE)

    quantity = models.FloatField()
    reason = models.CharField(max_length=20, choices=REASON_CHOICES, default='sale')
    location_reduced_from = models.CharField(max_length=20, choices=[('store', 'Store'), ('pharmacy', 'Pharmacy')],
                                           help_text="Which drug location was reduced")
    worth = models.DecimalField(max_digits=12, decimal_places=2, blank=True)

    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = 'drug_stock_outs'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.drug} - {self.quantity} ({self.reason})"

    def save(self, *args, **kwargs):
        # Calculate worth if not provided
        if not self.worth:
            self.worth = self.stock.selling_price * self.quantity

        # REMOVED: Automatic stock and drug quantity updates
        # These are now handled in the view for better control
        super().save(*args, **kwargs)


# 8. DRUG TRANSFER MODEL (Store to Pharmacy transfers)
class DrugTransferModel(models.Model):
    """Track transfers from store to pharmacy"""
    drug = models.ForeignKey(DrugModel, on_delete=models.CASCADE, related_name='transfers')
    quantity = models.FloatField()

    transferred_at = models.DateTimeField(auto_now_add=True)
    transferred_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'drug_transfers'
        ordering = ['-transferred_at']

    def __str__(self):
        return f"Transfer: {self.drug} - {self.quantity}"

    def save(self, *args, **kwargs):
        is_new = not self.id
        super().save(*args, **kwargs)

        if is_new:
            # Update drug quantities
            self.drug.store_quantity -= self.quantity
            self.drug.pharmacy_quantity += self.quantity
            self.drug.save()


# 9. PHARMACY SETTINGS
class PharmacySettingModel(models.Model):
    """General pharmacy settings"""
    drug_sale_without_prescription = models.BooleanField(default=False)
    auto_transfer_threshold = models.IntegerField(
        default=5,
        help_text="Auto-suggest transfer when pharmacy stock is below this level"
    )

    class Meta:
        db_table = 'pharmacy_settings'

    def __str__(self):
        return "Pharmacy Settings"


class DrugOrderModel(models.Model):
    """
    Represents a patient's order or prescription for a specific drug.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Dispense'),
        ('paid', 'Paid'),
        ('partially_paid', 'Partially Paid'),
        ('dispensed', 'Dispensed'),
        ('partially_dispensed', 'Partially Dispensed'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    ]

    patient = models.ForeignKey(
        'patient.PatientModel',
        on_delete=models.CASCADE,
        related_name='drug_prescriptions',
        help_text="The patient for whom the drug is ordered."
    )
    drug = models.ForeignKey(
        DrugModel, # Assuming DrugModel is in the same app
        on_delete=models.CASCADE,
        related_name='drug_orders',
        help_text="The specific drug product ordered."
    )

    quantity_ordered = models.FloatField(
        validators=[MinValueValidator(0.01)],
        help_text="The total quantity of the drug ordered (e.g., 30 tablets, 1 bottle)."
    )
    quantity_paid = models.FloatField(
        default=0.0,
        help_text="The quantity of the drug actually dispensed."
    )
    quantity_dispensed = models.FloatField(
        default=0.0,
        help_text="The quantity of the drug actually dispensed."
    )

    # Prescription/Dosage Details
    dosage_instructions = models.TextField(
        blank=True,
        help_text="e.g., 'Take 1 tablet twice daily after meals for 7 days'."
    )
    duration = models.CharField(
        max_length=50,
        blank=True,
        help_text="e.g., '7 days', 'until finished', 'PRN'."
    )

    # Order & Dispensing Tracking
    order_number = models.CharField(
        max_length=20,
        unique=True,
        blank=True,
        help_text="Auto-generated unique order number."
    )
    ordered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescribed_drugs',
        help_text="The user (e.g., doctor, nurse) who ordered the drug."
    )
    ordered_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the order was placed."
    )

    dispensed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='dispensed_drugs',
        help_text="The user (e.g., pharmacist) who dispensed the drug."
    )
    dispensed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the drug was dispensed."
    )

    status = models.CharField(
        max_length=25,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current status of the drug order."
    )
    notes = models.TextField(
        blank=True,
        help_text="Any additional notes about the order or dispensing."
    )
    admission = models.ForeignKey(
        'inpatient.Admission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drug_orders',
        help_text="Link to an admission record if applicable"
    )
    surgery = models.ForeignKey(
        'inpatient.Surgery',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drug_orders',
        help_text="Link to a surgery record if applicable"
    )

    consultation = models.ForeignKey(
        'consultation.ConsultationSessionModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drug_consultation_order',
    )

    class Meta:
        db_table = 'drug_orders'
        ordering = ['-ordered_at']
        verbose_name = 'Drug Order'
        verbose_name_plural = 'Drug Orders'

    def __str__(self):
        return f"Order {self.order_number} for {self.patient} - {self.drug.brand_name}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Auto-generate order number (similar to your existing pattern)
            today = date.today()
            date_str = today.strftime('%Y%m%d')
            last_order = DrugOrderModel.objects.filter(
                order_number__startswith=f'DRG{date_str}'
            ).order_by('-order_number').first()

            if last_order:
                try:
                    last_num = int(last_order.order_number[-3:])
                    next_num = last_num + 1
                except ValueError:
                    next_num = 1
            else:
                next_num = 1
            self.order_number = f'DRG{date_str}{str(next_num).zfill(3)}'

        super().save(*args, **kwargs)

    @property
    def is_fully_dispensed(self):
        return self.quantity_ordered == self.quantity_dispensed

    @property
    def remaining_to_dispense(self):
        return self.quantity_ordered - self.quantity_dispensed


class ExternalPrescription(models.Model):
    """
    Represents a prescription for a drug not available in the local inventory.
    """
    patient = models.ForeignKey(
        'patient.PatientModel',
        on_delete=models.CASCADE,
        related_name='external_prescriptions'
    )
    consultation = models.ForeignKey(
        'consultation.ConsultationSessionModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='external_prescriptions',
    )
    admission = models.ForeignKey(
        'inpatient.Admission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='external_prescriptions'
    )
    surgery = models.ForeignKey(
        'inpatient.Surgery',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='external_prescriptions'
    )
    ordered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='prescribed_external_drugs'
    )

    drug_name = models.CharField(max_length=255, help_text="Name of the prescribed drug not in inventory.")
    dosage_instructions = models.TextField(blank=True)
    duration = models.CharField(max_length=100, blank=True)
    quantity = models.CharField(max_length=100, help_text="Manually entered quantity (e.g., '1 Bottle', '2 Packs').")
    notes = models.TextField(blank=True)

    ordered_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'external_prescriptions'
        ordering = ['-ordered_at']
        verbose_name = 'External Prescription'
        verbose_name_plural = 'External Prescriptions'

    def __str__(self):
        return f"External Rx for {self.patient}: {self.drug_name}"


class DispenseRecord(models.Model):
    """
    Record each dispense event (partial dispensing allowed).
    """
    order = models.ForeignKey(
        'DrugOrderModel',
        on_delete=models.CASCADE,
        related_name='dispense_records'
    )
    dispensed_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="Pharmacist or staff who dispensed the drug."
    )
    dispensed_qty = models.FloatField()
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Dispense Record"
        verbose_name_plural = "Dispense Records"

    def __str__(self):
        return f"Dispensed {self.dispensed_qty} for {self.order.order_number}"


# 10. DRUG TEMPLATES (For bulk drug creation)
class DrugTemplateModel(models.Model):
    """Templates for bulk creating drug variants - specific combinations only"""
    name = models.CharField(max_length=200, help_text="Template name (e.g., 'Paracetamol Variants')")
    generic_name = models.CharField(max_length=200)
    category = models.ForeignKey(DrugCategoryModel, on_delete=models.SET_NULL, null=True, blank=True)
    is_prescription = models.BooleanField(default=True)

    # Specific combinations as JSON array of objects
    drug_combinations = models.JSONField(
        default=list,
        help_text="""
        Array of specific combinations like:
        [
            {"strength": "500mg", "form": "tablet", "manufacturer": "GSK"},
            {"strength": "250mg", "form": "syrup", "manufacturer": "Emzor"},
            {"strength": "500mg", "form": "tablet", "manufacturer": "Bond"}
        ]
        """
    )

    # Processing status
    is_processed = models.BooleanField(default=False, help_text="Has this template been used to create drugs?")
    drugs_created_count = models.IntegerField(default=0, help_text="Number of drug variants created")

    created_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = 'drug_templates'
        ordering = ['-created_at']

    def __str__(self):
        status = "✓ Processed" if self.is_processed else "⏳ Pending"
        return f"{self.name} ({status})"

    def create_drug_variants(self, selected_indices=None):
        """
        Create actual drug variants from specific combinations
        selected_indices: List of indices to process (if None, processes all)
        """
        from django.utils import timezone

        if self.is_processed:
            return {"error": "Template already processed"}

        created_drugs = []
        errors = []

        try:
            # Get or create generic drug
            generic_drug, _ = GenericDrugModel.objects.get_or_create(
                generic_name=self.generic_name,
                defaults={
                    'category': self.category,
                    'is_prescription_only': self.is_prescription
                }
            )

            # Process specific combinations
            combinations_to_process = (
                [self.drug_combinations[i] for i in selected_indices]
                if selected_indices
                else self.drug_combinations
            )

            for combo in combinations_to_process:
                try:
                    # Get or create manufacturer
                    manufacturer, _ = ManufacturerModel.objects.get_or_create(
                        name=combo['manufacturer']
                    )

                    # Create formulation
                    formulation, _ = DrugFormulationModel.objects.get_or_create(
                        generic_drug=generic_drug,
                        form_type=combo['form'],
                        strength=combo['strength']
                    )

                    # Generate unique SKU
                    sku_base = f"{generic_drug.generic_name[:3].upper()}-{combo['strength']}-{combo['form'][:3].upper()}-{manufacturer.name[:3].upper()}"
                    sku = sku_base
                    counter = 1
                    while DrugModel.objects.filter(sku=sku).exists():
                        sku = f"{sku_base}-{counter}"
                        counter += 1

                    # Create drug variant
                    drug, created = DrugModel.objects.get_or_create(
                        formulation=formulation,
                        manufacturer=manufacturer,
                        defaults={'sku': sku}
                    )

                    if created:
                        created_drugs.append(drug)

                except Exception as e:
                    errors.append(f"Error creating {combo}: {str(e)}")

            # Mark as processed
            self.is_processed = True
            self.drugs_created_count = len(created_drugs)
            self.processed_at = timezone.now()
            self.save()

            return {
                "success": True,
                "created_count": len(created_drugs),
                "created_drugs": created_drugs,
                "errors": errors
            }

        except Exception as e:
            return {"error": f"Template processing failed: {str(e)}"}

    @property
    def preview_combinations(self):
        """Preview what will be created"""
        return [
            f"{combo['manufacturer']} {combo['strength']} {self.generic_name} {combo['form']}"
            for combo in self.drug_combinations
        ]


# 11. BULK IMPORT LOG (For tracking imports)
class DrugImportLogModel(models.Model):
    """Track bulk drug imports"""
    import_file = models.FileField(upload_to='drug_imports/')
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    import_date = models.DateTimeField(auto_now_add=True)
    total_records = models.IntegerField(default=0)
    successful_records = models.IntegerField(default=0)
    failed_records = models.IntegerField(default=0)
    error_log = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=[('processing', 'Processing'), ('completed', 'Completed'), ('failed', 'Failed')],
        default='processing'
    )

    class Meta:
        db_table = 'drug_import_logs'
        ordering = ['-import_date']

    def __str__(self):
        return f"Import {self.id} - {self.status}"