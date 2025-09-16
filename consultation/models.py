from datetime import datetime, date
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal

from django.utils import timezone

from finance.models import PatientTransactionModel
from insurance.models import PatientInsuranceModel, HMOCoveragePlanModel


class SpecializationGroupModel(models.Model):
    """General, ENT. specialization under same group can share same consultation payment"""
    name = models.CharField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name.title()


class SpecializationModel(models.Model):
    """Medical specializations like Cardiology, Pediatrics, etc."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, blank=True)
    group = models.ForeignKey(SpecializationGroupModel, blank=True, null=True, on_delete=models.SET_NULL)
    description = models.TextField(blank=True)

    # Pricing
    base_consultation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'specializations'
        ordering = ['name']

    def __str__(self):
        return self.name.title()

    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.name[:3].upper()
        super().save(*args, **kwargs)


# 2. CONSULTATION BLOCKS & ROOMS (Simplified)
class ConsultationBlockModel(models.Model):
    """Building blocks/wings"""
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = 'consultation_blocks'

    def __str__(self):
        return self.name.title()


class ConsultationRoomModel(models.Model):
    """Individual consultation rooms"""
    name = models.CharField(max_length=200)
    block = models.ForeignKey(ConsultationBlockModel, on_delete=models.CASCADE, related_name='rooms')
    specialization = models.ForeignKey(
        SpecializationModel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        help_text="Primary specialization for this room"
    )

    # Room status
    is_active = models.BooleanField(default=True)
    capacity = models.IntegerField(default=1, help_text="Number of doctors that can use this room")

    class Meta:
        db_table = 'consultation_rooms'
        unique_together = ['name', 'block']

    def __str__(self):
        return f"{self.block.name} - {self.name}"


# 3. CONSULTANT DOCTORS (Link staff to consultations)
class ConsultantModel(models.Model):
    """Doctors who can do consultations - links to your StaffModel"""
    staff = models.ForeignKey(
        'human_resource.StaffModel',
        on_delete=models.CASCADE,
        related_name='consultant_profile'
    )
    specialization = models.ForeignKey(SpecializationModel, on_delete=models.CASCADE)

    # Consultation settings
    default_consultation_duration = models.IntegerField(default=20, help_text="Minutes per consultation")
    max_daily_patients = models.IntegerField(default=30, help_text="Maximum patients per day")

    # Availability
    is_available_for_consultation = models.BooleanField(default=True)
    consultation_days = models.CharField(
        max_length=20,
        default='mon,tue,wed,thu,fri',
        help_text="Comma-separated: mon,tue,wed,thu,fri,sat,sun"
    )
    consultation_start_time = models.TimeField(default="08:00")
    consultation_end_time = models.TimeField(default="16:00")

    # Room assignment
    assigned_room = models.ForeignKey(
        ConsultationRoomModel,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='consultants'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'consultants'

    def __str__(self):
        return f"Dr. {self.staff.__str__()} ({self.specialization.name})"

    @property
    def is_available_today(self):
        """Check if consultant is available today"""
        today = date.today().strftime('%a').lower()[:3]
        return today in self.consultation_days.lower()


# 4. CONSULTATION FEES (Separated from type - cleaner)
class ConsultationFeeModel(models.Model):
    """Consultation fees by specialization and patient type"""
    specialization = models.ForeignKey(SpecializationModel, on_delete=models.CASCADE, related_name='fees')

    # Patient categorization
    PATIENT_CATEGORIES = [
        ('regular', 'Regular Patient'),
        ('insurance', 'Insurance Patient'),
    ]
    patient_category = models.CharField(max_length=20, choices=PATIENT_CATEGORIES, default='regular')
    insurance = models.ForeignKey(HMOCoveragePlanModel, on_delete=models.CASCADE, blank=True, null=True, related_name='insurance')

    # Pricing
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Validity
    is_active = models.BooleanField(default=True)
    validity_in_days = models.PositiveIntegerField(
        default=1,
        help_text="Number of days this fee is valid after being applied."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'consultation_fees'
        unique_together = ['specialization', 'patient_category', 'insurance']

    def __str__(self):
        return f"{self.specialization.name} - {self.patient_category} (₦{self.amount})"


# 6. PATIENT QUEUE SYSTEM (The Real Queue!)
class PatientQueueModel(models.Model):
    """Main patient queue - tracks patient journey"""
    patient = models.ForeignKey('patient.PatientModel', on_delete=models.CASCADE)
    payment = models.ForeignKey(PatientTransactionModel, on_delete=models.CASCADE)
    specialization = models.ForeignKey(SpecializationModel, on_delete=models.SET_NULL,
        null=True,  blank=True
    )

    consultant = models.ForeignKey(ConsultantModel, on_delete=models.CASCADE, blank=True, null=True)

    # Queue position and status
    QUEUE_STATUS = [
        ('waiting_vitals', 'Waiting for Vitals'),
        ('vitals_done', 'Vitals Completed - Waiting for Doctor'),
        ('with_doctor', 'With Doctor'),
        ('consultation_paused', 'Consultation Paused'),
        ('consultation_completed', 'Consultation Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=25, choices=QUEUE_STATUS, default='waiting_vitals')
    queue_number = models.CharField(max_length=20, unique=True, blank=True)

    # Timing
    joined_queue_at = models.DateTimeField(auto_now_add=True)
    vitals_started_at = models.DateTimeField(null=True, blank=True)
    vitals_completed_at = models.DateTimeField(null=True, blank=True)
    consultation_started_at = models.DateTimeField(null=True, blank=True)
    consultation_ended_at = models.DateTimeField(null=True, blank=True)

    # Staff assignments
    vitals_nurse = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='vitals_queue'
    )

    # Priority and notes
    is_emergency = models.BooleanField(default=False)
    priority_level = models.IntegerField(default=0, help_text="0=Normal, 1=High, 2=Emergency")
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'patient_queue'
        ordering = ['priority_level', 'joined_queue_at']  # Emergency first, then FIFO

    def __str__(self):
        return f"Queue {self.queue_number}: {self.patient} ({self.status})"

    def save(self, *args, **kwargs):
        if not self.specialization and self.payment and hasattr(self.payment, 'fee_structure'):
            self.specialization = self.payment.fee_structure.specialization

        if not self.queue_number:
            # Generate queue number: CSL20241225001

            today = date.today().strftime('%Y%m%d')
            last_queue = PatientQueueModel.objects.filter(
                queue_number__startswith=f'Q{today}'
            ).order_by('id').last()

            if last_queue:
                try:
                    last_num = int(last_queue.queue_number[-3:])
                    next_num = last_num + 1
                except ValueError:
                    next_num = 1
            else:
                next_num = 1

            print(next_num)

            self.queue_number = f'Q{today}{str(next_num).zfill(3)}'

        super().save(*args, **kwargs)

    def start_vitals(self, nurse):
        """Mark vitals as started"""
        self.status = 'waiting_vitals'
        self.vitals_nurse = nurse
        self.vitals_started_at = datetime.now()
        self.save()

    def complete_vitals(self):
        """Mark vitals as completed"""
        if self.status == 'waiting_vitals':
            self.status = 'vitals_done'
        self.vitals_completed_at = datetime.now()
        self.save()

    def start_consultation(self):
        """Mark consultation as started"""
        self.status = 'with_doctor'
        self.consultation_started_at = datetime.now()
        self.save()

    def pause_consultation(self):
        """Pause consultation (patient stepped out)"""
        self.status = 'consultation_paused'
        self.save()

    def resume_consultation(self):
        """Resume consultation"""
        self.status = 'with_doctor'
        self.save()

    def complete_consultation(self):
        """Mark consultation as completed"""
        self.status = 'consultation_completed'
        self.consultation_ended_at = datetime.now()
        self.save()


# 7. PATIENT VITALS (Pre-consultation)
class PatientVitalsModel(models.Model):
    """Patient vitals taken by nurses before consultation"""
    queue_entry = models.OneToOneField(PatientQueueModel, on_delete=models.CASCADE, related_name='vitals')

    # Basic vitals
    temperature = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True, help_text="°C")
    blood_pressure_systolic = models.IntegerField()
    blood_pressure_diastolic = models.IntegerField()
    pulse_rate = models.IntegerField(null=True, blank=True, help_text="BPM")
    respiratory_rate = models.IntegerField(null=True, blank=True, help_text="per minute")
    oxygen_saturation = models.IntegerField(null=True, blank=True, help_text="SpO2 %")

    # Physical measurements
    height = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="cm")
    weight = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="kg")
    bmi = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)

    # Nurse observations
    general_appearance = models.TextField(blank=True)
    extra_note = models.TextField(blank=True)
    chief_complaint = models.TextField(blank=True, help_text="What patient is complaining of")

    # Tracking
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recorded_vitals')
    notes = models.TextField(blank=True)

    class Meta:
        db_table = 'patient_vitals'

    def __str__(self):
        return f"Vitals: {self.queue_entry.patient} - {self.recorded_at.strftime('%Y-%m-%d')}"

    def save(self, *args, **kwargs):
        # Calculate BMI if height and weight are provided
        if self.height and self.weight:
            height_m = float(self.height) / 100  # Convert cm to meters
            self.bmi = float(self.weight) / (height_m * height_m)

        super().save(*args, **kwargs)

    @property
    def blood_pressure(self):
        """Return formatted blood pressure"""
        if self.blood_pressure_systolic and self.blood_pressure_diastolic:
            return f"{self.blood_pressure_systolic}/{self.blood_pressure_diastolic}"
        return None


class DiagnosisOption(models.Model):
    name = models.CharField(max_length=200, unique=True)
    icd_code = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# 8. CONSULTATION SESSIONS (The actual consultation)
class ConsultationSessionModel(models.Model):
    queue_entry = models.OneToOneField(PatientQueueModel, on_delete=models.CASCADE, related_name='consultation')

    # Consultation classification
    consultation_type = models.CharField(
        max_length=20,
        choices=[
            ('new', 'New Patient'),
            ('follow_up', 'Follow-up Visit'),
        ],
        help_text="Only NEW consultations appear in OPD register"
    )

    # Main consultation note
    assessment = models.TextField(help_text="Comprehensive consultation notes")
    chief_complaint = models.TextField(help_text="Comprehensive consultation notes")
    diagnosis = models.TextField(help_text="Comprehensive consultation notes")

    # Diagnosis fields (only for NEW consultations)
    primary_diagnosis = models.ForeignKey(
        DiagnosisOption,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_consultations',
        help_text="Required for new consultations"
    )
    other_diagnosis_text = models.CharField(
        max_length=500,
        blank=True,
        null=True,
        help_text="If diagnosis not in list above"
    )

    # Case completion status
    case_status = models.CharField(
        max_length=20,
        choices=[
            ('ongoing', 'Ongoing Treatment'),
            ('completed', 'Case Completed'),
            ('referred', 'Referred'),
            ('discharged', 'Discharged'),
        ],
        default='ongoing',
        help_text="Mark as 'completed' to make next visit a NEW consultation"
    )

    # Optional voice recording
    voice_recording = models.FileField(
        upload_to='consultations/',
        null=True,
        blank=True
    )

    # Session status
    status = models.CharField(
        max_length=20,
        choices=[
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
        ],
        default='in_progress'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        # Auto-determine consultation type on creation
        if not self.pk:  # New record
            self.consultation_type = self.determine_consultation_type()
        super().save(*args, **kwargs)

    def determine_consultation_type(self):
        """Determine if this is a new or follow-up consultation"""
        patient = self.queue_entry.patient

        # Check for previous consultations for this patient
        previous_consultations = ConsultationSessionModel.objects.filter(
            queue_entry__patient=patient,
            status='completed'
        ).order_by('-completed_at')

        # If no previous consultations, it's NEW
        if not previous_consultations.exists():
            return 'new'

        # Get the most recent consultation
        last_consultation = previous_consultations.first()

        # If last consultation was marked as completed/discharged, this is NEW
        if last_consultation.case_status in ['completed', 'discharged']:
            return 'new'

        # Otherwise, it's a follow-up
        return 'follow_up'

    def complete_consultation(self):
        """Complete the consultation session"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

        # Also complete the queue entry
        self.queue_entry.complete_consultation()

    def __str__(self):
        return f"{self.get_consultation_type_display()}: {self.queue_entry.patient} - {self.created_at.strftime('%Y-%m-%d')}"


# 9. DOCTOR SCHEDULE (When doctors are available)
class DoctorScheduleModel(models.Model):
    """Doctor availability schedule"""
    consultant = models.ForeignKey(ConsultantModel, on_delete=models.CASCADE, related_name='schedules')

    # Schedule details
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    # Capacity
    max_patients = models.IntegerField(default=20)
    current_bookings = models.IntegerField(default=0)

    # Status
    is_available = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'doctor_schedules'
        unique_together = ['consultant', 'date']
        ordering = ['date', 'start_time']

    def __str__(self):
        return f"{self.consultant} - {self.date} ({self.start_time}-{self.end_time})"

    @property
    def is_fully_booked(self):
        """Check if schedule is fully booked"""
        return self.current_bookings >= self.max_patients

    @property
    def available_slots(self):
        """Number of available slots"""
        return max(0, self.max_patients - self.current_bookings)


# 10. CONSULTATION SETTINGS
class ConsultationSettingsModel(models.Model):
    """Global consultation settings"""

    # Queue settings
    auto_assign_queue_numbers = models.BooleanField(default=True)
    max_queue_size_per_doctor = models.IntegerField(default=50)

    # Timing settings
    default_consultation_duration = models.IntegerField(default=20, help_text="Minutes")
    vitals_timeout_minutes = models.IntegerField(default=30, help_text="Max time for vitals")
    consultation_timeout_hours = models.IntegerField(default=2, help_text="Max consultation time")

    # Insurance settings
    default_insurance_coverage_percent = models.IntegerField(default=70)

    # Notifications
    send_queue_notifications = models.BooleanField(default=True)
    send_vitals_reminders = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'consultation_settings'

    def __str__(self):
        return "Consultation Settings"