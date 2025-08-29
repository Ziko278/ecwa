from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import date


# 1. SCAN CATEGORIES (Simple grouping)
class ScanCategoryModel(models.Model):
    """Categories like Cardiology, Radiology, Neurology, etc."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, blank=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scan_categories'
        verbose_name_plural = 'Scan Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


# 2. SCAN TEMPLATES (The Key Model - Like Lab Templates!)
class ScanTemplateModel(models.Model):
    """Pre-built scan templates with standard procedures"""
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)
    category = models.ForeignKey(
        ScanCategoryModel,
        on_delete=models.CASCADE,
        related_name='templates'
    )

    # Scan configuration as JSON
    scan_parameters = models.JSONField(
        default=dict,
        help_text="""
        Standard format:
        {
            "preparation": [
                "Patient should fast for 12 hours",
                "Remove all metal objects"
            ],
            "procedure_steps": [
                "Position patient supine",
                "Apply gel to chest",
                "Record 12-lead ECG"
            ],
            "measurements": [
                {
                    "name": "Heart Rate",
                    "code": "HR",
                    "unit": "bpm",
                    "normal_range": {"min": 60, "max": 100}
                },
                {
                    "name": "PR Interval",
                    "code": "PR",
                    "unit": "ms",
                    "normal_range": {"min": 120, "max": 200}
                }
            ]
        }
        """
    )

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    # Scan requirements
    scan_type = models.CharField(
        max_length=50,
        choices=[
            ('ecg', 'ECG/EKG'),
            ('echo', 'Echocardiogram'),
            ('xray', 'X-Ray'),
            ('ct', 'CT Scan'),
            ('mri', 'MRI'),
            ('ultrasound', 'Ultrasound'),
            ('eeg', 'EEG'),
            ('stress_test', 'Stress Test'),
            ('holter', 'Holter Monitor'),
            ('other', 'Other'),
        ],
        default='ecg'
    )

    # Duration and preparation
    estimated_duration = models.CharField(max_length=50, blank=True, help_text="e.g., 30 minutes, 1 hour")
    preparation_required = models.BooleanField(default=False)
    fasting_required = models.BooleanField(default=False)

    # Equipment needed
    equipment_required = models.TextField(blank=True, help_text="List of equipment/machines needed")

    # Status
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scan_templates'
        ordering = ['category__name', 'name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def measurement_names(self):
        """Quick preview of measurements"""
        if self.scan_parameters and 'measurements' in self.scan_parameters:
            return [param['name'] for param in self.scan_parameters['measurements']]
        return []


# 3. SCAN ORDERS (When a scan is requested)
class ScanOrderModel(models.Model):
    """Individual scan orders for patients"""
    # Using Patient model from your existing system
    patient = models.ForeignKey('patient.PatientModel', on_delete=models.CASCADE, related_name='scan_orders')
    template = models.ForeignKey(ScanTemplateModel, on_delete=models.CASCADE, related_name='orders')

    # Order details
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    ordered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ordered_scans')

    # Status tracking
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid - Scheduled'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    # Payment
    amount_charged = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    payment_status = models.BooleanField(default=False)
    payment_date = models.DateTimeField(blank=True, null=True)
    payment_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='processed_scan_payments')

    # Scheduling
    scheduled_date = models.DateTimeField(blank=True, null=True)
    scheduled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='scheduled_scans')

    # Execution
    scan_started_at = models.DateTimeField(blank=True, null=True)
    scan_completed_at = models.DateTimeField(blank=True, null=True)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='performed_scans')

    # Dates
    ordered_at = models.DateTimeField(auto_now_add=True)

    # Notes
    clinical_indication = models.TextField(blank=True, help_text="Why this scan was ordered")
    special_instructions = models.TextField(blank=True)

    class Meta:
        db_table = 'scan_orders'
        ordering = ['-ordered_at']

    def __str__(self):
        return f"{self.template.name} - {self.patient} ({self.order_number})"

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Auto-generate order number
            today = date.today()
            date_str = today.strftime('%Y%m%d')
            last_order = ScanOrderModel.objects.filter(
                order_number__startswith=f'SCN{date_str}'
            ).order_by('-order_number').first()

            if last_order:
                try:
                    last_num = int(last_order.order_number[-3:])
                    next_num = last_num + 1
                except ValueError:
                    next_num = 1
            else:
                next_num = 1

            self.order_number = f'SCN{date_str}{str(next_num).zfill(3)}'

        if not self.amount_charged:
            self.amount_charged = self.template.price

        super().save(*args, **kwargs)


# 4. SCAN RESULTS (The actual scan results)
class ScanResultModel(models.Model):
    """Scan results - stores measurements and findings"""
    order = models.OneToOneField(ScanOrderModel, on_delete=models.CASCADE, related_name='result')

    # Results stored as JSON matching the template structure
    measurements_data = models.JSONField(
        default=dict,
        help_text="""
        Results in same structure as template:
        {
            "measurements": [
                {
                    "parameter_code": "HR",
                    "parameter_name": "Heart Rate", 
                    "value": "78",
                    "unit": "bpm",
                    "normal_range": "60-100",
                    "status": "normal"
                }
            ]
        }
        """
    )

    # Key findings
    findings = models.TextField(blank=True, help_text="Main findings from the scan")
    impression = models.TextField(blank=True, help_text="Clinical impression/conclusion")
    recommendations = models.TextField(blank=True, help_text="Recommended follow-up or treatment")

    # Image/file attachments
    scan_images = models.JSONField(
        default=list,
        blank=True,
        help_text="List of image file paths or URLs"
    )

    scan_files = models.JSONField(
        default=list,
        blank=True,
        help_text="List of additional files (PDFs, reports, etc.)"
    )

    # Quality control
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='verified_scans')
    verified_at = models.DateTimeField(blank=True, null=True)

    # Technician and doctor notes
    technician_notes = models.TextField(blank=True)
    doctor_interpretation = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scan_results'

    def __str__(self):
        return f"Results: {self.order}"

    @property
    def has_abnormal_findings(self):
        """Check if any measurements are outside normal range"""
        if self.measurements_data and 'measurements' in self.measurements_data:
            return any(
                result.get('status') in ['high', 'low', 'abnormal']
                for result in self.measurements_data['measurements']
            )
        return False


# 5. SCAN EQUIPMENT (Equipment used for scans)
class ScanEquipmentModel(models.Model):
    """Equipment used for performing scans"""
    name = models.CharField(max_length=200)
    equipment_type = models.CharField(
        max_length=50,
        choices=[
            ('ecg_machine', 'ECG Machine'),
            ('echo_machine', 'Echo Machine'),
            ('xray_machine', 'X-Ray Machine'),
            ('ct_scanner', 'CT Scanner'),
            ('mri_scanner', 'MRI Scanner'),
            ('ultrasound', 'Ultrasound Machine'),
            ('eeg_machine', 'EEG Machine'),
            ('stress_test', 'Stress Test Equipment'),
            ('holter_monitor', 'Holter Monitor'),
        ]
    )

    model_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True, unique=True)
    manufacturer = models.CharField(max_length=100, blank=True)

    # Which scans can this equipment perform
    supported_templates = models.ManyToManyField(
        ScanTemplateModel,
        blank=True,
        related_name='equipment'
    )

    # Location and status
    location = models.CharField(max_length=100, blank=True, help_text="Room or department")
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('maintenance', 'Under Maintenance'),
        ('inactive', 'Inactive'),
        ('calibration', 'Needs Calibration'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Maintenance tracking
    last_maintenance = models.DateField(blank=True, null=True)
    next_maintenance = models.DateField(blank=True, null=True)
    last_calibration = models.DateField(blank=True, null=True)
    next_calibration = models.DateField(blank=True, null=True)

    # Purchase info
    purchase_date = models.DateField(blank=True, null=True)
    warranty_expires = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scan_equipment'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.equipment_type})"

    @property
    def needs_maintenance(self):
        """Check if maintenance is due"""
        if self.next_maintenance:
            return self.next_maintenance <= date.today()
        return False

    @property
    def needs_calibration(self):
        """Check if calibration is due"""
        if self.next_calibration:
            return self.next_calibration <= date.today()
        return False


# 6. SCAN APPOINTMENTS (Scheduling system)
class ScanAppointmentModel(models.Model):
    """Appointment scheduling for scans"""
    scan_order = models.ForeignKey(ScanOrderModel, on_delete=models.CASCADE, related_name='appointments')
    equipment = models.ForeignKey(ScanEquipmentModel, on_delete=models.CASCADE, related_name='appointments')

    # Appointment time
    appointment_date = models.DateTimeField()
    estimated_duration = models.IntegerField(help_text="Duration in minutes")

    # Status
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('no_show', 'No Show'),
        ('cancelled', 'Cancelled'),
        ('rescheduled', 'Rescheduled'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')

    # Staff assignment
    technician = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='scan_appointments')

    # Preparation status
    patient_prepared = models.BooleanField(default=False)
    preparation_notes = models.TextField(blank=True)

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = 'scan_appointments'
        ordering = ['appointment_date']

    def __str__(self):
        return f"{self.scan_order.template.name} - {self.appointment_date.strftime('%Y-%m-%d %H:%M')}"


# 7. SCAN TEMPLATE BUILDER (For easy setup - like your Lab Template Builder!)
class ScanTemplateBuilderModel(models.Model):
    """Helper model for building scan templates easily"""
    name = models.CharField(max_length=200)
    category = models.ForeignKey(ScanCategoryModel, on_delete=models.CASCADE)

    # Common scan type presets
    scan_preset = models.CharField(
        max_length=100,
        choices=[
            ('basic_ecg', 'Basic ECG (12-lead)'),
            ('stress_ecg', 'Stress Test ECG'),
            ('chest_xray', 'Chest X-Ray'),
            ('abdominal_ultrasound', 'Abdominal Ultrasound'),
            ('cardiac_echo', 'Cardiac Echo'),
            ('brain_ct', 'Brain CT Scan'),
            ('basic_eeg', 'Basic EEG'),
            ('custom', 'Custom Parameters'),
        ]
    )

    # Custom parameters for non-preset scans
    custom_parameters = models.JSONField(default=list, blank=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    scan_type = models.CharField(max_length=50, default='ecg')
    estimated_duration = models.CharField(max_length=50, default='30 minutes')

    # Processing status
    is_processed = models.BooleanField(default=False)
    created_template = models.ForeignKey(
        ScanTemplateModel,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        db_table = 'scan_template_builders'

    def __str__(self):
        status = "Built" if self.is_processed else "Pending"
        return f"{self.name} ({status})"

    def build_template(self):
        """Convert this builder into an actual template"""
        if self.is_processed:
            return {"error": "Template already built"}

        # Get preset parameters or use custom
        if self.scan_preset != 'custom':
            parameters = self._get_preset_parameters()
        else:
            parameters = self.custom_parameters

        # Create the template
        template = ScanTemplateModel.objects.create(
            name=self.name,
            code=self.name.upper().replace(' ', '_'),
            category=self.category,
            scan_parameters=parameters,
            price=self.price,
            scan_type=self.scan_type,
            estimated_duration=self.estimated_duration
        )

        # Mark as processed
        self.is_processed = True
        self.created_template = template
        self.save()

        return {"success": True, "template": template}

    def _get_preset_parameters(self):
        """Get standard parameters for common scan types"""
        presets = {
            'basic_ecg': {
                "preparation": [
                    "Remove jewelry and metal objects from chest area",
                    "Patient should be relaxed and lying flat"
                ],
                "procedure_steps": [
                    "Clean skin with alcohol if needed",
                    "Apply electrodes to chest, arms, and legs",
                    "Record 12-lead ECG for 10 seconds",
                    "Review rhythm and quality"
                ],
                "measurements": [
                    {"name": "Heart Rate", "code": "HR", "unit": "bpm", "normal_range": {"min": 60, "max": 100}},
                    {"name": "PR Interval", "code": "PR", "unit": "ms", "normal_range": {"min": 120, "max": 200}},
                    {"name": "QRS Duration", "code": "QRS", "unit": "ms", "normal_range": {"max": 120}},
                    {"name": "QT Interval", "code": "QT", "unit": "ms", "normal_range": {"max": 440}},
                ]
            },
            'chest_xray': {
                "preparation": [
                    "Remove all clothing and jewelry from chest area",
                    "Wear hospital gown with opening at back"
                ],
                "procedure_steps": [
                    "Position patient standing against image plate",
                    "Instruct patient to take deep breath and hold",
                    "Take PA view exposure",
                    "Take lateral view if ordered"
                ],
                "measurements": [
                    {"name": "Heart Size", "code": "HEART", "type": "select",
                     "options": ["Normal", "Enlarged", "Small"]},
                    {"name": "Lung Fields", "code": "LUNGS", "type": "text"},
                    {"name": "Impression", "code": "IMP", "type": "text"},
                ]
            },
            'cardiac_echo': {
                "preparation": [
                    "Patient should be fasting for 2 hours",
                    "Remove clothing from chest area"
                ],
                "procedure_steps": [
                    "Position patient in left lateral position",
                    "Apply ultrasound gel to chest",
                    "Perform 2D, M-mode, and Doppler studies",
                    "Measure cardiac chambers and function"
                ],
                "measurements": [
                    {"name": "Ejection Fraction", "code": "EF", "unit": "%", "normal_range": {"min": 50}},
                    {"name": "LV End Diastolic Diameter", "code": "LVEDD", "unit": "cm", "normal_range": {"max": 5.6}},
                    {"name": "Left Atrial Size", "code": "LA", "unit": "cm", "normal_range": {"max": 4.0}},
                    {"name": "Aortic Root", "code": "AO", "unit": "cm", "normal_range": {"max": 3.7}},
                ]
            }
        }

        return presets.get(self.scan_preset, {"measurements": []})


# 8. SCAN SETTINGS
class ScanSettingModel(models.Model):
    """Scan department configuration settings"""
    department_name = models.CharField(max_length=200, default="Diagnostic Imaging")
    department_head = models.CharField(max_length=200, blank=True)

    # Appointment settings
    default_appointment_duration = models.IntegerField(default=30, help_text="Default duration in minutes")
    advance_booking_days = models.IntegerField(default=30, help_text="How many days ahead can appointments be booked")

    # Working hours
    working_hours_start = models.TimeField(default="08:00")
    working_hours_end = models.TimeField(default="17:00")

    # Notifications
    send_appointment_reminders = models.BooleanField(default=True)
    reminder_hours_before = models.IntegerField(default=24)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scan_settings'

    def __str__(self):
        return f"{self.department_name} Settings"