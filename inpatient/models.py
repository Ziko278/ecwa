from django.db import models
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

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "Inpatient Settings"
        verbose_name_plural = "Inpatient Settings"

    def __str__(self):
        return f"Inpatient Settings (Updated: {self.updated_at.strftime('%Y-%m-%d')})"


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
            ('maintenance', 'Under Maintenance'),
            ('reserved', 'Reserved'),
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
        if self.status == 'occupied':
            active_admission = self.admissions.filter(status='active').first()
            return active_admission.patientModel if active_admission else None
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


class Admission(models.Model):
    """Patient admissions"""
    patient = models.ForeignKey(PatientModel, on_delete=models.CASCADE, related_name='admissions')
    admission_number = models.CharField(max_length=50, unique=True)

    # Admission details
    admission_type = models.CharField(
        max_length=20,
        choices=[
            ('emergency', 'Emergency'),
            ('elective', 'Elective'),
            ('transfer', 'Transfer'),
            ('readmission', 'Readmission'),
        ],
        default='elective'
    )
    chief_complaint = models.TextField()
    admission_diagnosis = models.TextField()

    # Bed assignment
    bed = models.ForeignKey(
        Bed,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='admissions'
    )

    # Status and dates
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('discharged', 'Discharged'),
            ('transferred', 'Transferred'),
            ('deceased', 'Deceased'),
            ('absconded', 'Absconded'),
        ],
        default='active'
    )
    admission_date = models.DateTimeField(default=timezone.now)
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
            if self.status == 'active':
                self.bed.status = 'occupied'
            elif self.status in ['discharged', 'transferred', 'deceased', 'absconded']:
                # Only free the bed if this is the current admission
                if self.bed.current_patient == self.patientModel:
                    self.bed.status = 'available'
            self.bed.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.admission_number} - {self.patientModel}"

    @property
    def length_of_stay(self):
        end_date = self.actual_discharge_date or timezone.now()
        return (end_date - self.admission_date).days

    @property
    def is_active(self):
        return self.status == 'active'

    @property
    def ward_name(self):
        return self.bed.ward.name if self.bed else None


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