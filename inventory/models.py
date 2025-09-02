"""Django models for Hospital Inventory & Asset Management

Place this file in an app called `inventory` (e.g. inventory/models.py).
This design covers consumable inventory items and durable assets, with
history records (stock movements, damages, usage) and asset maintenance.

Assumptions:
- There is an HR app with a Department model available at 'hr.Department'.
- There is a patients app with a Patient model available at 'patients.Patient'.
- `AUTH_USER_MODEL` is used for staff tracking.

Notes on usage:
- Create StockRecord objects to record inbound/outbound stock. A post-save
  signal will update the InventoryItem.quantity atomically.
- Create AssetMaintenance/AssetDamage/AssetPurchase to track asset lifecycle
  and costs.
- Use StockUsage to track specific usage events with quantities.

"""
from decimal import Decimal
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.core.validators import MinValueValidator


class Unit(models.Model):
    """Unit of measure (e.g. pcs, box, kg, litre)."""
    name = models.CharField(max_length=32, unique=True)
    abbreviation = models.CharField(max_length=12, blank=True)

    def __str__(self):
        return self.abbreviation or self.name

    class Meta:
        ordering = ['name']


class Supplier(models.Model):
    name = models.CharField(max_length=120)
    contact_person = models.CharField(max_length=120, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class InventoryCategory(models.Model):
    """Categorize inventory (e.g. Linen, Pharmaceuticals, Stationery)."""
    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = "Inventory Categories"
        ordering = ['name']

    def __str__(self):
        return self.name


class InventoryItem(models.Model):
    """Represents an inventory stockable item (consumable or durable small item).

    Keep a cached `quantity` for quick reads; StockRecord entries are the source
    of truth and are used to update quantity atomically.
    """
    ITEM_TYPE_CHOICES = [
        ("consumable", "Consumable"),
        ("medication", "Medication"),
        ("reagent", "Reagent"),
        ("ppe", "PPE"),
        ("small_equipment", "Small Equipment"),
    ]

    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=80, blank=True, db_index=True)
    category = models.ForeignKey(InventoryCategory, on_delete=models.SET_NULL, null=True, blank=True)
    item_type = models.CharField(max_length=32, choices=ITEM_TYPE_CHOICES, default="consumable")
    unit = models.ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.ForeignKey("hr.Department", on_delete=models.SET_NULL, null=True, blank=True)

    # Cached quantity for quick reads. Keep in sync via StockRecord signals.
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))]
    )

    reorder_level = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))]
    )
    min_level = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))]
    )

    last_purchase_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Additional useful fields
    expiry_date = models.DateField(null=True, blank=True, help_text="For medications and perishables")
    batch_number = models.CharField(max_length=100, blank=True)
    storage_location = models.CharField(max_length=200, blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("name", "department")
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.sku})" if self.sku else self.name

    @property
    def is_low_stock(self):
        """Check if current stock is below reorder level."""
        return self.quantity <= self.reorder_level

    @property
    def is_critical_stock(self):
        """Check if current stock is below minimum level."""
        return self.quantity <= self.min_level

    @property
    def is_expired(self):
        """Check if item has expired (for items with expiry dates)."""
        if self.expiry_date:
            return timezone.now().date() > self.expiry_date
        return False

    def recalc_quantity(self):
        """Recompute quantity from StockRecord entries.
        Uses aggregation and updates cached `quantity`.
        """
        with transaction.atomic():
            total_in = self.stock_records.filter(
                transaction_type__in=[StockRecord.TYPE_IN, StockRecord.TYPE_ADJUST_IN]
            ).aggregate(models.Sum('quantity'))['quantity__sum'] or Decimal('0')

            total_out = self.stock_records.filter(
                transaction_type__in=[StockRecord.TYPE_OUT, StockRecord.TYPE_ADJUST_OUT, StockRecord.TYPE_DAMAGE]
            ).aggregate(models.Sum('quantity'))['quantity__sum'] or Decimal('0')

            new_qty = Decimal(total_in) - Decimal(total_out)
            self.quantity = max(new_qty, Decimal('0.000'))  # Ensure non-negative
            self.save(update_fields=['quantity', 'updated_at'])
        return self.quantity


class StockRecord(models.Model):
    """History of stock transactions for InventoryItem.

    Use `transaction_type` to describe the movement.
    """
    TYPE_IN = 'in'
    TYPE_OUT = 'out'
    TYPE_TRANSFER = 'transfer'
    TYPE_DAMAGE = 'damage'
    TYPE_ADJUST_IN = 'adjust_in'
    TYPE_ADJUST_OUT = 'adjust_out'

    TRANSACTION_CHOICES = [
        (TYPE_IN, 'Stock In (purchase/receive)'),
        (TYPE_OUT, 'Stock Out (usage/issue)'),
        (TYPE_TRANSFER, 'Transfer (between departments/locations)'),
        (TYPE_DAMAGE, 'Damage/Write-off'),
        (TYPE_ADJUST_IN, 'Adjustment (+)'),
        (TYPE_ADJUST_OUT, 'Adjustment (-)'),
    ]

    item = models.ForeignKey(InventoryItem, related_name='stock_records', on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=32, choices=TRANSACTION_CHOICES)
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )

    # Optional linkage to a supplier, order, or destination location
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    reference = models.CharField(max_length=200, blank=True, help_text='Free-form reference: PO #, request #, etc.')
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.ForeignKey("hr.Department", on_delete=models.SET_NULL, null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Additional fields for better tracking
    batch_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    # Link to usage record if this is usage-related
    usage = models.ForeignKey('StockUsage', on_delete=models.SET_NULL, null=True, blank=True, related_name='stock_records')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_transaction_type_display()} {self.quantity} of {self.item.name}"

    def clean(self):
        """Validate the record before saving."""
        from django.core.exceptions import ValidationError

        # Ensure positive quantity
        if self.quantity <= 0:
            raise ValidationError("Quantity must be positive")

        # Validate supplier for stock-in transactions
        if self.transaction_type == self.TYPE_IN and not self.supplier:
            raise ValidationError("Supplier is required for stock-in transactions")


class StockUsage(models.Model):
    """High-level record for when items are used as part of a clinical activity.

    This creates a usage event that can contain multiple items via StockUsageItem.
    """
    patient = models.ForeignKey('patients.Patient', on_delete=models.SET_NULL, null=True, blank=True)
    purpose = models.CharField(max_length=200, blank=True, help_text="e.g. Surgery, Treatment, Routine Care")
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.ForeignKey('hr.Department', on_delete=models.SET_NULL, null=True, blank=True)
    usage_date = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        patient_info = f" for {self.patient}" if self.patient else ""
        return f"Usage {self.id}{patient_info} - {self.purpose}"

    class Meta:
        ordering = ['-usage_date']

    @property
    def total_cost(self):
        """Calculate total cost of all items used in this usage event."""
        return self.usage_items.aggregate(
            total=models.Sum(models.F('quantity') * models.F('unit_cost'))
        )['total'] or Decimal('0.00')


class StockUsageItem(models.Model):
    """Individual items used in a StockUsage event."""
    usage = models.ForeignKey(StockUsage, related_name='usage_items', on_delete=models.CASCADE)
    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE)
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"{self.quantity} x {self.item.name} (Usage {self.usage.id})"

    def save(self, *args, **kwargs):
        """Auto-populate unit_cost from item's last purchase price if not provided."""
        if not self.unit_cost and self.item.last_purchase_price:
            self.unit_cost = self.item.last_purchase_price
        super().save(*args, **kwargs)

    class Meta:
        unique_together = ('usage', 'item')


class StockDamage(models.Model):
    """Additional detail for damaged stock items (write-off)."""
    item = models.ForeignKey(InventoryItem, related_name='damages', on_delete=models.CASCADE)
    quantity = models.DecimalField(
        max_digits=14,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    reason = models.TextField(blank=True)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    department = models.ForeignKey('hr.Department', on_delete=models.SET_NULL, null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    date_reported = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Damage {self.quantity} x {self.item.name}"

    class Meta:
        ordering = ['-date_reported']


# -------------------- Assets --------------------
class AssetType(models.TextChoices):
    DIAGNOSTIC = 'diagnostic', 'Diagnostic'
    THERAPEUTIC = 'therapeutic', 'Therapeutic'
    IT = 'it', 'IT & Electronics'
    FURNITURE = 'furniture', 'Furniture'
    VEHICLE = 'vehicle', 'Vehicle'
    OTHER = 'other', 'Other'


class AssetStatus(models.TextChoices):
    EXCELLENT = 'excellent', 'Excellent'
    GOOD = 'good', 'Good'
    FAIR = 'fair', 'Fair'
    POOR = 'poor', 'Poor'
    NEEDS_REPAIR = 'needs_repair', 'Needs Repair'
    OUT_OF_SERVICE = 'out_of_service', 'Out of Service'
    DECOMMISSIONED = 'decommissioned', 'Decommissioned'


class Asset(models.Model):
    """Durable assets such as machines, beds, laptops, vehicles."""
    name = models.CharField(max_length=200)
    serial_number = models.CharField(max_length=200, blank=True, null=True, db_index=True)
    asset_tag = models.CharField(max_length=50, unique=True, null=True, blank=True, help_text="Internal asset tag")
    asset_type = models.CharField(max_length=32, choices=AssetType.choices, default=AssetType.OTHER)
    department = models.ForeignKey('hr.Department', on_delete=models.SET_NULL, null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)

    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    vendor = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)

    condition = models.CharField(
        max_length=80,
        choices=AssetStatus.choices,
        default=AssetStatus.GOOD,
        help_text='Current condition of the asset'
    )
    is_operational = models.BooleanField(default=True)

    # Warranty information
    warranty_expiry = models.DateField(null=True, blank=True)
    warranty_provider = models.CharField(max_length=200, blank=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-purchase_date', 'name']

    def __str__(self):
        identifiers = []
        if self.asset_tag:
            identifiers.append(self.asset_tag)
        elif self.serial_number:
            identifiers.append(self.serial_number)

        if identifiers:
            return f"{self.name} ({', '.join(identifiers)})"
        return self.name

    @property
    def is_under_warranty(self):
        """Check if asset is still under warranty."""
        if self.warranty_expiry:
            return timezone.now().date() <= self.warranty_expiry
        return False

    @property
    def needs_maintenance(self):
        """Check if asset has overdue maintenance."""
        overdue_maintenance = self.maintenances.filter(
            next_due__lt=timezone.now().date()
        ).exists()
        return overdue_maintenance

    def current_value(self, depreciation_rate_per_year=Decimal('0.15')):
        """A simple straight-line depreciation estimator (not accounting for salvage).
        Override in business logic if you need more accurate accounting.
        """
        if not self.purchase_date or not self.purchase_cost:
            return None
        years = (timezone.now().date() - self.purchase_date).days / 365.25
        depreciation = Decimal(str(years)) * depreciation_rate_per_year * self.purchase_cost
        val = self.purchase_cost - depreciation
        return max(val, Decimal('0.00'))

    def total_maintenance_cost(self):
        """Calculate total maintenance cost for this asset."""
        return self.maintenances.aggregate(
            total=models.Sum('cost')
        )['total'] or Decimal('0.00')


class AssetMaintenance(models.Model):
    """Maintenance/Service events for assets."""
    MAINTENANCE_TYPE_CHOICES = [
        ('preventive', 'Preventive'),
        ('corrective', 'Corrective'),
        ('emergency', 'Emergency'),
        ('calibration', 'Calibration'),
        ('inspection', 'Inspection'),
    ]

    asset = models.ForeignKey(Asset, related_name='maintenances', on_delete=models.CASCADE)
    maintenance_type = models.CharField(max_length=32, choices=MAINTENANCE_TYPE_CHOICES, default='preventive')
    performed_on = models.DateField()
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    service_provider = models.CharField(max_length=200, blank=True, help_text="External service provider if applicable")
    description = models.TextField(blank=True)
    cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    next_due = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_maintenance_type_display()} on {self.asset} - {self.performed_on}"

    class Meta:
        ordering = ['-performed_on']


class AssetPurchase(models.Model):
    """Purchase records for assets."""
    asset = models.ForeignKey(Asset, related_name='purchases', on_delete=models.CASCADE)
    purchase_date = models.DateField()
    invoice_reference = models.CharField(max_length=200, blank=True)
    cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    purchaser = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    purchase_order_number = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        ref = self.invoice_reference or self.purchase_order_number or f"Purchase {self.id}"
        return f"{ref} - {self.cost}"

    class Meta:
        ordering = ['-purchase_date']


class AssetDamage(models.Model):
    """Damage reports for assets."""
    SEVERITY_CHOICES = [
        ('minor', 'Minor'),
        ('moderate', 'Moderate'),
        ('major', 'Major'),
        ('total_loss', 'Total Loss'),
    ]

    asset = models.ForeignKey(Asset, related_name='damages', on_delete=models.CASCADE)
    date_reported = models.DateField(default=timezone.now)
    reported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    severity = models.CharField(max_length=32, choices=SEVERITY_CHOICES, default='minor')
    repair_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    is_total_loss = models.BooleanField(default=False)
    repair_completed = models.BooleanField(default=False)
    repair_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_severity_display()} damage to {self.asset} on {self.date_reported}"

    class Meta:
        ordering = ['-date_reported']


# -------------------- Signals --------------------
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver


@receiver(post_save, sender=StockRecord)
def update_inventory_quantity_on_save(sender, instance, created, **kwargs):
    """Update InventoryItem quantity when StockRecord is saved."""
    if created:  # Only update on creation to avoid infinite loops
        instance.item.recalc_quantity()


@receiver(post_delete, sender=StockRecord)
def update_inventory_quantity_on_delete(sender, instance, **kwargs):
    """Update InventoryItem quantity when StockRecord is deleted."""
    instance.item.recalc_quantity()


@receiver(post_save, sender=StockUsageItem)
def create_stock_record_for_usage(sender, instance, created, **kwargs):
    """Automatically create StockRecord when StockUsageItem is created."""
    if created:
        StockRecord.objects.create(
            item=instance.item,
            transaction_type=StockRecord.TYPE_OUT,
            quantity=instance.quantity,
            performed_by=instance.usage.performed_by,
            department=instance.usage.department,
            reference=f"Usage {instance.usage.id}",
            usage=instance.usage,
            cost=instance.unit_cost
        )