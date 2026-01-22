from datetime import date
from decimal import Decimal

from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from patient.models import PatientModel  # Assuming you have a PatientModel model


class InpatientSettings(models.Model):
    """Global settings for inpatient services"""

    # Bed billing settings
    bed_billing_for_admission = models.CharField(
        max_length=20,
        choices=[
            ('free', 'Free'),
            ('daily', 'Daily Charge'),
            ('one_time', 'One-time Charge'),
        ],
        default='free',
        help_text="How are beds billed for regular admissions?"
    )
    bed_billing_for_surgery = models.CharField(
        max_length=20,
        choices=[
            ('free', 'Free'),
            ('daily', 'Daily Charge'),
            ('one_time', 'One-time Charge'),
        ],
        default='daily',
        help_text="How are beds billed for surgery patients?"
    )

    # Admission billing
    admission_billing_type = models.CharField(
        max_length=20,
        choices=[
            ('none', 'No Admission Fee'),
            ('one_time', 'One-time Fee'),
            ('daily', 'Daily Fee'),
        ],
        default='one_time',
        help_text="Type of admission billing"
    )
    admission_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Admission fee amount"
    )

    # Surgery billing
    surgery_billing_type = models.CharField(
        max_length=20,
        choices=[
            ('none', 'No Surgery Fee'),
            ('one_time', 'One-time Fee'),
            ('daily', 'Daily Fee'),
        ],
        default='one_time',
        help_text="Type of surgery facility billing"
    )
    surgery_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Surgery facility fee amount"
    )

    # Bed cost amount (when not free)
    bed_daily_cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Daily bed cost when charged"
    )

    # Auto-compilation settings (surgery only)
    compile_surgery_drugs = models.BooleanField(
        default=True,
        help_text="Automatically include drugs from surgery packages?"
    )
    compile_surgery_labs = models.BooleanField(
        default=True,
        help_text="Automatically include lab tests from surgery packages?"
    )
    compile_surgery_scans = models.BooleanField(
        default=True,
        help_text="Automatically include scans from surgery packages?"
    )
    # NEW: Admission fee settings
    charge_admission_fee = models.BooleanField(
        default=False,
        help_text="Charge one-time admission fee when patient is admitted?"
    )
    admission_fee_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)],
        help_text="One-time admission fee amount"
    )

    # NEW: Default debt limit
    default_max_debt = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('50000.00'),
        validators=[MinValueValidator(0)],
        help_text="Default maximum debt allowed per admission"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Inpatient Settings"
        verbose_name_plural = "Inpatient Settings"

    def __str__(self):
        return f"Inpatient Settings (Updated: {self.updated_at.strftime('%Y-%m-%d')})"


class AdmissionType(models.Model):
    """
    Types of admission packages with their pricing structure.
    Examples: General Ward, ICU, Private Suite, Semi-Private Room
    """
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of admission type (e.g., General Ward, ICU, Private Suite)"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Description of what this admission type includes"
    )

    # Bed fee
    bed_daily_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Daily bed charge for this admission type"
    )

    # Consultation fee
    consultation_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Consultation fee charged per ward round"
    )
    consultation_fee_duration_days = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="How many days one consultation fee covers (e.g., 3 = fee covers 3 days)"
    )

    # Deposit & debt management
    requires_deposit = models.BooleanField(
        default=True,
        help_text="Does this admission type require an initial deposit?"
    )
    minimum_deposit_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('10000.00'),
        validators=[MinValueValidator(0)],
        help_text="Minimum deposit required for admission"
    )
    max_debt_allowed = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('50000.00'),
        validators=[MinValueValidator(0)],
        help_text="Maximum debt allowed before services are blocked"
    )

    # Status
    is_active = models.BooleanField(default=True)

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_admission_types'
    )

    class Meta:
        ordering = ['name']
        verbose_name = "Admission Type"
        verbose_name_plural = "Admission Types"

    def __str__(self):
        return self.name


class AdmissionTask(models.Model):
    """
    Scheduled tasks for nurses/staff during admission.
    Examples: Drug administration, vital signs check, wound care
    """
    admission = models.ForeignKey(
        'Admission',
        on_delete=models.CASCADE,
        related_name='tasks',
        help_text="The admission this task belongs to"
    )

    # Task details
    task_type = models.CharField(
        max_length=20,
        choices=[
            ('drug', 'Drug Administration'),
            ('vitals', 'Vital Signs Check'),
            ('lab', 'Lab Sample Collection'),
            ('scan', 'Imaging Appointment'),
            ('wound_care', 'Wound Care'),
            ('feeding', 'Feeding/Nutrition'),
            ('physiotherapy', 'Physiotherapy'),
            ('other', 'Other')
        ],
        help_text="Type of task to be performed"
    )

    # Related orders (for context)
    drug_order = models.ForeignKey(
        'pharmacy.DrugOrderModel',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='administration_tasks',
        help_text="Drug order this task is for (if task_type is 'drug')"
    )

    description = models.TextField(
        help_text="Detailed description of what needs to be done"
    )

    # Scheduling
    scheduled_datetime = models.DateTimeField(
        help_text="When this task should be performed"
    )
    completed_datetime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the task was actually completed"
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('missed', 'Missed'),
            ('cancelled', 'Cancelled')
        ],
        default='pending'
    )

    # Staff assignment
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_admission_tasks',
        help_text="Staff member assigned to perform this task"
    )
    completed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='completed_admission_tasks',
        help_text="Staff member who completed this task"
    )

    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Additional instructions or special considerations"
    )
    completion_notes = models.TextField(
        blank=True,
        help_text="Notes recorded when task was completed"
    )

    # Recurrence (for recurring tasks like TDS, QDS)
    is_recurring = models.BooleanField(
        default=False,
        help_text="Is this part of a recurring task series?"
    )
    recurrence_pattern = models.CharField(
        max_length=50,
        blank=True,
        help_text="Frequency pattern: OD, BD, TDS, QDS, Q4H, Q6H, etc."
    )
    parent_task = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='recurring_instances',
        help_text="Parent task if this is part of a recurring series"
    )

    # Priority
    priority = models.CharField(
        max_length=20,
        choices=[
            ('low', 'Low'),
            ('normal', 'Normal'),
            ('high', 'High'),
            ('urgent', 'Urgent')
        ],
        default='normal'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_admission_tasks',
        help_text="User who created this task"
    )

    class Meta:
        ordering = ['scheduled_datetime', 'priority']
        verbose_name = "Admission Task"
        verbose_name_plural = "Admission Tasks"
        indexes = [
            models.Index(fields=['admission', 'status']),
            models.Index(fields=['scheduled_datetime']),
            models.Index(fields=['status', 'scheduled_datetime']),
        ]

    def __str__(self):
        return f"{self.get_task_type_display()} - {self.admission.patient} @ {self.scheduled_datetime.strftime('%Y-%m-%d %H:%M')}"

    @property
    def patient(self):
        """Quick access to patient"""
        return self.admission.patient

    @property
    def is_overdue(self):
        """Check if task is overdue"""
        if self.status in ['completed', 'cancelled']:
            return False
        return timezone.now() > self.scheduled_datetime

    @property
    def minutes_overdue(self):
        """Calculate how many minutes overdue"""
        if not self.is_overdue:
            return 0
        delta = timezone.now() - self.scheduled_datetime
        return int(delta.total_seconds() / 60)

    @property
    def time_until_due(self):
        """Time remaining until task is due"""
        if self.is_overdue:
            return None
        delta = self.scheduled_datetime - timezone.now()
        hours = int(delta.total_seconds() / 3600)
        minutes = int((delta.total_seconds() % 3600) / 60)
        return f"{hours}h {minutes}m"


class Admission(models.Model):
    """Patient admissions"""
    patient = models.ForeignKey(PatientModel, on_delete=models.CASCADE, related_name='admissions')
    admission_number = models.CharField(max_length=50, unique=True)

    # Admission details
    admission_type = models.ForeignKey(
        'AdmissionType',
        null=True,
        on_delete=models.PROTECT,
        related_name='admissions',
        help_text="Type of admission (General Ward, ICU, Private, etc.)"
    )

    chief_complaint = models.TextField()
    admission_diagnosis = models.TextField()

    # Bed assignment
    bed = models.ForeignKey(
        'Bed',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admissions'
    )

    # Status and dates
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Confirmation'),  # NEW
            ('active', 'Active'),
            ('discharged', 'Discharged'),
            ('transferred', 'Transferred'),
            ('deceased', 'Deceased'),
            ('absconded', 'Absconded'),
        ],
        default='pending'  # CHANGED from 'active'
    )

    admission_date = models.DateTimeField(default=timezone.now)

    # NEW: Separate activation date for billing
    admission_activated_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when admission was confirmed and billing started"
    )

    expected_discharge_date = models.DateField(null=True, blank=True)
    actual_discharge_date = models.DateTimeField(null=True, blank=True)

    # Staff assignments
    attending_doctor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attending_admissions'
    )
    admitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admitted_patients'
    )

    # Notes
    admission_notes = models.TextField(blank=True, null=True)
    discharge_notes = models.TextField(blank=True, null=True)

    # Financial tracking
    deposit_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Current deposit balance remaining"
    )
    total_charges = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Running total of all services charged"
    )
    total_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Total amount paid (deposits + direct payments)"
    )

    # Consultation fee tracking
    last_consultation_fee_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of last consultation fee charged"
    )
    last_consultation_fee_valid_until = models.DateField(
        null=True,
        blank=True,
        help_text="Date until which last consultation fee is valid"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-admission_date']

    def save(self, *args, **kwargs):
        if not self.admission_number:
            # Generate admission number
            from datetime import datetime
            self.admission_number = f"ADM{datetime.now().strftime('%Y%m%d%H%M%S')}"

        # Update bed status
        if self.bed:
            if self.status == 'pending':
                # Reserve bed for pending admission
                self.bed.status = 'reserved'
            elif self.status == 'active':
                # Occupy bed for active admission
                self.bed.status = 'occupied'
            elif self.status in ['discharged', 'transferred', 'deceased', 'absconded']:
                # Only free the bed if this is the current admission
                if self.bed.current_patient == self.patient:
                    self.bed.status = 'available'
            self.bed.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.admission_number} - {self.patient}"

    @property
    def length_of_stay(self):
        end_date = self.actual_discharge_date or timezone.now()
        return (end_date - self.admission_date).days

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def is_pending(self):
        return self.status == 'pending'

    @property
    def ward_name(self):
        return self.bed.ward.name if self.bed else None

    @property
    def debt_balance(self):
        """Amount owed = total charges - total paid"""
        return self.total_charges - self.total_paid

    @property
    def debt_limit_reached(self):
        """Check if debt limit has been reached"""
        max_debt = self.admission_type.max_debt_allowed if self.admission_type else Decimal('50000.00')
        return self.debt_balance >= max_debt

    @property
    def length_of_stay_days(self):
        """
        Calculate length of stay in days from ACTIVATION date.
        Rule: Any part of a day counts as a full day.
        """
        if not self.admission_activated_date:
            return 0

        end_datetime = self.actual_discharge_date or timezone.now()

        # Calculate from activation date, not admission date
        delta = end_datetime.date() - self.admission_activated_date.date()

        # Add 1 because partial day = full day
        return delta.days + 1

    @property
    def can_order_services(self):
        """Check if patient can order new services"""
        return not self.debt_limit_reached or self.deposit_balance > Decimal('0.00')

    @property
    def ward_rounds(self):
        """Get all consultations (ward rounds) for this admission"""
        return self.consultations.order_by('-created_at')

    @property
    def last_ward_round(self):
        """Get most recent ward round"""
        return self.consultations.order_by('-created_at').first()

    @property
    def can_be_confirmed(self):
        """Check if admission can be confirmed (has minimum deposit)"""
        if self.status != 'pending':
            return False
        if not self.admission_type:
            return False
        return self.deposit_balance >= self.admission_type.minimum_deposit_amount

    def confirm_admission(self, confirmed_by, bed=None):
        """
        Confirm a pending admission.
        Called by ward attendant after verifying payment.
        """
        if self.status != 'pending':
            raise ValueError("Only pending admissions can be confirmed")

        if not self.can_be_confirmed:
            raise ValueError("Minimum deposit not met. Cannot confirm admission.")

        with transaction.atomic():
            self.status = 'active'
            self.admission_activated_date = timezone.now()

            # Assign bed if provided
            if bed:
                # Free old bed if exists
                if self.bed and self.bed != bed:
                    old_bed = self.bed
                    old_bed.status = 'available'
                    old_bed.save()

                self.bed = bed
                bed.status = 'occupied'
                bed.save()
            elif self.bed:
                # Bed was already reserved, just occupy it
                self.bed.status = 'occupied'
                self.bed.save()

            self.save()

            # Trigger initial charges via signal
            from django.db.models.signals import post_save
            post_save.send(
                sender=self.__class__,
                instance=self,
                created=False,
                update_fields=['status', 'admission_activated_date']
            )

        return True


class Ward(models.Model):
    """Hospital wards/departments"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    ward_type = models.CharField(
        max_length=20,
        choices=[
            ('general', 'General Ward'),
            ('private', 'Private Ward'),
            ('icu', 'ICU'),
            ('surgery', 'Surgery Ward'),
            ('maternity', 'Maternity'),
            ('pediatric', 'Pediatric'),
            ('emergency', 'Emergency'),
        ],
        default='general'
    )
    capacity = models.PositiveIntegerField(help_text="Total number of beds")
    location = models.CharField(max_length=200, blank=True, null=True)
    floor = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def available_beds(self):
        return self.beds.filter(status='available').count()

    @property
    def occupied_beds(self):
        return self.beds.filter(status='occupied').count()

    @property
    def occupancy_rate(self):
        if self.capacity > 0:
            return round((self.occupied_beds / self.capacity) * 100, 2)
        return 0



class Bed(models.Model):
    """Individual beds within wards"""
    ward = models.ForeignKey(Ward, on_delete=models.CASCADE, related_name='beds')
    bed_number = models.CharField(max_length=20)
    bed_type = models.CharField(
        max_length=20,
        choices=[
            ('standard', 'Standard'),
            ('electric', 'Electric'),
            ('icu', 'ICU Bed'),
            ('isolation', 'Isolation'),
            ('bariatric', 'Bariatric'),
        ],
        default='standard'
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('available', 'Available'),
            ('occupied', 'Occupied'),
            ('reserved', 'Reserved'),  # NEW - for pending admissions
            ('maintenance', 'Under Maintenance'),
            ('cleaning', 'Being Cleaned'),
        ],
        default='available',
        blank=True
    )
    daily_rate = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Override ward rate if different"
    )
    features = models.TextField(
        blank=True,
        null=True,
        help_text="Special features (e.g., oxygen outlet, monitor, etc.)"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['ward', 'bed_number']
        ordering = ['ward__name', 'bed_number']

    def __str__(self):
        return f"{self.ward.name} - Bed {self.bed_number}"

    @property
    def current_patient(self):
        """Get the currently admitted patient in this bed"""
        if self.status in ['occupied', 'reserved']:
            active_admission = self.admissions.filter(status__in=['active', 'pending']).first()
            return active_admission.patient if active_admission else None
        return None


class SurgeryType(models.Model):
    """Types of surgeries offered"""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)
    category = models.CharField(
        max_length=50,
        choices=[
            ('general', 'General Surgery'),
            ('orthopedic', 'Orthopedic'),
            ('cardiac', 'Cardiac'),
            ('neurological', 'Neurological'),
            ('gynecological', 'Gynecological'),
            ('urological', 'Urological'),
            ('ophthalmic', 'Ophthalmic'),
            ('ent', 'ENT'),
            ('plastic', 'Plastic Surgery'),
            ('emergency', 'Emergency Surgery'),
        ]
    )
    specialization = models.ForeignKey(
        'consultation.SpecializationModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='surgery_types',
        help_text="Medical specialization that performs this surgery type"
    )
    base_surgeon_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Base surgeon fee for this surgery type"
    )
    base_anesthesia_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Base anesthesia fee"
    )
    base_facility_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Base facility/theater fee"
    )
    estimated_duration_hours = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Estimated surgery duration in hours"
    )
    requires_icu = models.BooleanField(
        default=False,
        help_text="Does this surgery typically require ICU?"
    )
    typical_stay_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Typical hospital stay in days"
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['category', 'name']
        verbose_name_plural = "Surgery Types"

    def __str__(self):
        return self.name

    @property
    def total_base_fee(self):
        return self.base_surgeon_fee + self.base_anesthesia_fee + self.base_facility_fee


# Similar models for surgery packages
class SurgeryDrug(models.Model):
    """Drugs included in surgery packages"""
    surgery = models.ForeignKey(SurgeryType, on_delete=models.CASCADE)
    drug = models.ForeignKey('pharmacy.DrugModel', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    is_optional = models.BooleanField(default=False)
    timing = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="e.g., 'Pre-op', 'Post-op', 'During surgery'"
    )

    def __str__(self):
        return f"{self.drug.name} for {self.surgery.name}"


class SurgeryLab(models.Model):
    """Lab tests included in surgery packages"""
    surgery = models.ForeignKey(SurgeryType, on_delete=models.CASCADE)
    lab = models.ForeignKey('laboratory.LabTestTemplateModel', on_delete=models.CASCADE)
    is_optional = models.BooleanField(default=False)
    timing = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="e.g., 'Pre-op', 'Post-op', 'Day 1'"
    )

    def __str__(self):
        return f"{self.lab.name} for {self.surgery.name}"


class SurgeryScan(models.Model):
    """Scans included in surgery packages"""
    surgery = models.ForeignKey(SurgeryType, on_delete=models.CASCADE)
    scan = models.ForeignKey('scan.ScanTemplateModel', on_delete=models.CASCADE)
    is_optional = models.BooleanField(default=False)
    timing = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="e.g., 'Pre-op', 'Intra-op', 'Follow-up'"
    )

    def __str__(self):
        return f"{self.scan.name} for {self.surgery.name}"


class Surgery(models.Model):
    """Surgical procedures"""
    patient = models.ForeignKey(PatientModel, on_delete=models.CASCADE, related_name='surgeries')
    surgery_number = models.CharField(max_length=50, unique=True)

    # Surgery details
    surgery_type = models.ForeignKey(SurgeryType, on_delete=models.CASCADE)

    admission = models.ForeignKey(
        Admission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='surgeries',
        help_text="Associated admission if any"
    )

    # Scheduling
    scheduled_date = models.DateTimeField()
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)

    specialization = models.ForeignKey(
        'consultation.SpecializationModel',  # Adjust app name if different
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='surgeries',
        help_text="Medical specialization performing this surgery"
    )

    # Staff
    primary_surgeon = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='primary_surgeries',
        blank=True
    )
    assistant_surgeon = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assisted_surgeries'
    )
    anesthesiologist = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='anesthesia_surgeries'
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
            ('postponed', 'Postponed'),
        ],
        default='scheduled'
    )

    # Clinical details
    pre_op_diagnosis = models.TextField()
    post_op_diagnosis = models.TextField(blank=True, null=True)
    procedure_notes = models.TextField(blank=True, null=True)
    complications = models.TextField(blank=True, null=True)

    # Custom fees (if different from base type fees)
    custom_surgeon_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Override surgeon fee if different"
    )
    custom_anesthesia_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Override anesthesia fee if different"
    )
    custom_facility_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Override facility fee if different"
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-scheduled_date']
        verbose_name_plural = "Surgeries"

    def save(self, *args, **kwargs):
        if not self.surgery_number:
            # Generate surgery number
            from datetime import datetime
            self.surgery_number = f"SUR{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if not self.specialization:
            try:
                self.specialization = self.surgery_type.specialization
            except:
                pass
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.surgery_number} - {self.surgery_type.name} - {self.patient}"

    @property
    def total_surgeon_fee(self):
        return self.custom_surgeon_fee or self.surgery_type.base_surgeon_fee

    @property
    def total_anesthesia_fee(self):
        return self.custom_anesthesia_fee or self.surgery_type.base_anesthesia_fee

    @property
    def total_facility_fee(self):
        return self.custom_facility_fee or self.surgery_type.base_facility_fee

    @property
    def total_surgery_cost(self):
        return self.total_surgeon_fee + self.total_anesthesia_fee + self.total_facility_fee

    @property
    def duration_hours(self):
        if self.actual_start_time and self.actual_end_time:
            duration = self.actual_end_time - self.actual_start_time
            return round(duration.total_seconds() / 3600, 2)
        return None

    @property
    def is_completed(self):
        return self.status == 'completed'

    @property
    def surgeon_name(self):
        return f"{self.primary_surgeon.__str__()}" if self.primary_surgeon else None
