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


class ScanTemplateModel(models.Model):
    """Pre-built scan templates with standard procedures"""
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)
    category = models.ForeignKey(
        ScanCategoryModel,
        on_delete=models.CASCADE,
        related_name='templates'
    )

    # Scan configuration as JSON - more flexible structure
    scan_parameters = models.JSONField(
        default=dict,
        help_text="""
        Flexible format based on scan type:
        {
            "preparation": [
                "Patient should fast for 12 hours",
                "Remove all metal objects"
            ],
            "procedure_steps": [
                "Position patient supine",
                "Apply electrodes to chest",
                "Record 12-lead ECG"
            ],
            "imaging": {
                "views": [
                    {"name": "AP", "description": "Anterior-Posterior", "required": true},
                    {"name": "Lateral", "description": "Lateral view", "required": true}
                ],
                "contrast": {"required": false, "type": "oral"},
                "technical_factors": {
                    "kvp": 120,
                    "mas": 100
                }
            },
            "measurements": [
                {
                    "name": "Heart Rate",
                    "code": "HR",
                    "unit": "bpm",
                    "normal_range": {"min": 60, "max": 100},
                    "type": "numeric"
                }
            ],
            "monitoring": {
                "duration": "24 hours",
                "frequency": "continuous"
            }
        }
        """
    )

    # Expected images configuration
    expected_images = models.JSONField(
        default=list,
        help_text="""
        Expected images for this scan:
        [
            {"view": "AP", "description": "Chest AP view", "required": true},
            {"view": "Lateral", "description": "Chest Lateral view", "required": true},
            {"view": "Oblique", "description": "Optional oblique view", "required": false}
        ]
        """
    )

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    # Duration and preparation
    estimated_duration = models.CharField(max_length=50, blank=True, help_text="e.g., 30 minutes, 1 hour")
    fasting_required = models.BooleanField(default=False)

    # Keep it simple - add more fields later as needed

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
        """Quick preview of measurements (for ECG-type scans)"""
        if self.scan_parameters and 'measurements' in self.scan_parameters:
            return [param['name'] for param in self.scan_parameters['measurements']]
        return []

    @property
    def image_views(self):
        """Quick preview of expected image views"""
        return [img['view'] for img in self.expected_images]

    @property
    def required_images_count(self):
        """Count of required images"""
        return len([img for img in self.expected_images if img.get('required', True)])


class ScanImageModel(models.Model):
    """Individual images from scan results"""
    scan_result = models.ForeignKey(
        'ScanResultModel',  # Your actual scan execution
        on_delete=models.CASCADE,
        related_name='images'
    )
    image = models.ImageField(upload_to='scan_images/%Y/%m/')
    view_type = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=200, blank=True)
    sequence_number = models.PositiveIntegerField(default=1)

    # Image metadata
    image_quality = models.CharField(
        max_length=20,
        choices=[
            ('excellent', 'Excellent'),
            ('good', 'Good'),
            ('fair', 'Fair'),
            ('poor', 'Poor'),
        ],
        default='good'
    )

    # Technical parameters (optional)
    technical_parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="kVp, mAs, exposure time, etc."
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scan_images'
        ordering = ['scan_result', 'sequence_number']
        unique_together = ['scan_result', 'sequence_number']

    def __str__(self):
        return f"{self.scan_result} - {self.view_type} #{self.sequence_number}"


class ScanOrderModel(models.Model):
    """Individual scan orders for patients"""
    # Using Patient model from your existing system
    patient = models.ForeignKey(
        'patient.PatientModel',
        on_delete=models.CASCADE,
        related_name='scan_orders'
    )

    # Template remains required at DB level (you set it when creating orders programmatically)
    template = models.ForeignKey(
        'ScanTemplateModel',
        on_delete=models.CASCADE,
        related_name='orders'
    )

    # Order details
    order_number = models.CharField(max_length=20, unique=True, blank=True)

    # ordered_by: allow blank in forms and be nullable so admin/tools can leave it empty
    ordered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordered_scans'
    )

    # Status tracking
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid - Scheduled'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    # blank=True so ModelForm won't require it; default keeps behavior if omitted
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', blank=True)

    admission = models.ForeignKey(
        'inpatient.Admission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scan_orders',
        help_text="Link to an admission record if applicable"
    )
    surgery = models.ForeignKey(
        'inpatient.Surgery',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scan_orders',
        help_text="Link to a surgery record if applicable"
    )
    consultation = models.ForeignKey(
        'consultation.ConsultationSessionModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scan_consultation_order',
    )

    # Payment
    amount_charged = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    payment_status = models.BooleanField(default=False)
    payment_date = models.DateTimeField(blank=True, null=True)
    payment_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_scan_payments'
    )

    # Scheduling
    scheduled_date = models.DateTimeField(blank=True, null=True)
    scheduled_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scheduled_scans'
    )

    # Execution
    scan_started_at = models.DateTimeField(blank=True, null=True)
    scan_completed_at = models.DateTimeField(blank=True, null=True)
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='performed_scans'
    )

    # Dates
    ordered_at = models.DateTimeField(auto_now_add=True)

    # Notes
    clinical_indication = models.TextField(blank=True, help_text="Why this scan was ordered")
    special_instructions = models.TextField(blank=True)

    class Meta:
        db_table = 'scan_orders'
        ordering = ['-ordered_at']
        permissions = [
            ("view_financial_report", "Can view scan financial reports"),
        ]

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

    @property
    def total_amount(self):
        """Return the amount charged for this scan"""
        return self.amount_charged or Decimal('0.00')


class ExternalScanOrder(models.Model):
    """Scans/Imaging performed externally (template.is_active=False)"""
    patient = models.ForeignKey(
        'patient.PatientModel',
        on_delete=models.CASCADE,
        related_name='external_scan_orders'
    )
    consultation = models.ForeignKey(
        'consultation.ConsultationSessionModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='external_scan_orders',
    )
    ordered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ordered_external_scans'
    )

    # Template info (stored as text since template might be deactivated)
    scan_name = models.CharField(max_length=200)
    scan_code = models.CharField(max_length=20, blank=True)
    category_name = models.CharField(max_length=100, blank=True)

    # Instructions
    clinical_indication = models.TextField(blank=True)
    special_instructions = models.TextField(blank=True)

    # External result file
    result_file = models.FileField(
        upload_to='external_scan_results/%Y/%m/',
        blank=True,
        null=True,
        help_text="Upload external scan/radiology report (PDF/Image)"
    )

    # Tracking
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    ordered_at = models.DateTimeField(auto_now_add=True)
    result_uploaded_at = models.DateTimeField(blank=True, null=True)
    result_uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_external_scan_results'
    )

    class Meta:
        db_table = 'external_scan_orders'
        ordering = ['-ordered_at']
        verbose_name = 'External Scan Order'
        verbose_name_plural = 'External Scan Orders'

    def __str__(self):
        return f"External: {self.scan_name} - {self.patient} ({self.order_number})"

    def save(self, *args, **kwargs):
        if not self.order_number:
            today = date.today()
            date_str = today.strftime('%Y%m%d')
            last_order = ExternalScanOrder.objects.filter(
                order_number__startswith=f'EXTSCN{date_str}'
            ).order_by('-order_number').first()

            if last_order:
                try:
                    last_num = int(last_order.order_number[-3:])
                    next_num = last_num + 1
                except ValueError:
                    next_num = 1
            else:
                next_num = 1

            self.order_number = f'EXTSCN{date_str}{str(next_num).zfill(3)}'

        super().save(*args, **kwargs)

    @property
    def has_result(self):
        return bool(self.result_file)


class ScanResultModel(models.Model):
    """Actual scan execution results - Enhanced with report handling"""
    order = models.OneToOneField(ScanOrderModel, on_delete=models.CASCADE, related_name='result')

    # === CORE FINDINGS ===
    findings = models.TextField(blank=True, help_text="Primary scan findings")
    impression = models.TextField(blank=True, help_text="Clinical impression/diagnosis")
    recommendations = models.TextField(blank=True, help_text="Follow-up recommendations")
    technician_comments = models.TextField(blank=True, help_text="Technical notes")
    radiologist_comments = models.TextField(blank=True,
                                            help_text="Interpretation and comments from the verifying radiologist")

    # === TIMING ===
    performed_at = models.DateTimeField()
    report_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When report was finalized"
    )

    # === STAFF TRACKING ===
    performed_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='performed_scan_results'
    )

    # === STATUS MANAGEMENT ===
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_review', 'Pending Review'),
        ('reviewed', 'Reviewed'),
        ('finalized', 'Finalized'),
        ('amended', 'Amended'),
    ]
    status = models.CharField(
        max_length=20,
        blank=True,
        choices=STATUS_CHOICES,
        default='draft'
    )

    # === VERIFICATION ===
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_scan_results'
    )
    verified_at = models.DateTimeField(blank=True, null=True)

    # === REPORT IMAGE HANDLING ===
    radiology_report_image = models.ImageField(
        upload_to='radiology_reports/%Y/%m/',
        blank=True,
        null=True,
        help_text="Uploaded radiology report image"
    )

    # === EXTRACTED/STRUCTURED DATA ===
    # Template-based measurements (matching ScanTemplateModel.scan_parameters)
    measured_values = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        Actual measured values matching template structure:
        {
            "measurements": [
                {
                    "code": "HR",
                    "value": 85,
                    "unit": "bpm", 
                    "normal": true,
                    "comment": "Within normal limits"
                }
            ],
            "technical_factors": {
                "kvp": 120,
                "mas": 100,
                "exposure_time": "0.5s"
            }
        }
        """
    )

    # Free-form extracted data from report images
    extracted_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="""
        Key findings extracted from report image:
        {
            "key_findings": ["Heart size normal", "Lung fields clear"],
            "abnormalities": [],
            "follow_up_required": false
        }
        """
    )

    # === EXTRACTION TRACKING ===
    report_extracted = models.BooleanField(default=False)
    extracted_by = models.ForeignKey(
        'human_resource.StaffModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='extracted_scan_reports'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'scan_results'
        ordering = ['-performed_at']

        permissions = [
            ("can_verify_scan_result", "Can verify Image result"),
        ]

    def __str__(self):
        return f"{self.order.template.name} - {self.performed_at.date()}"

    # === HELPER METHODS ===
    def get_readable_findings(self):
        """Get findings - from extracted data or original text"""
        if self.extracted_data and 'key_findings' in self.extracted_data:
            return self.extracted_data['key_findings']
        return self.findings

    def has_report_image(self):
        """Check if radiology report image was uploaded"""
        return bool(self.radiology_report_image)

    @property
    def measurements_data(self):
        """
        Backwards-compatible accessor for measured values.
        Returns a dict with at least a 'measurements' key containing a list.
        """
        # measured_values is a JSONField with default=dict
        mv = self.measured_values or {}
        # Return a copy so callers can't accidentally mutate the stored JSON without using the model
        data = dict(mv)
        if 'measurements' not in data:
            data['measurements'] = []
        return data

    def needs_extraction(self):
        """Check if report image exists but extraction not done"""
        return self.has_report_image() and not self.report_extracted


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
    scan_name = models.CharField(max_length=200, blank=True, default='')
    mobile = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(max_length=100, blank=True, null=True)
    allow_direct_scan_order = models.BooleanField(
        default=False,
        help_text="Allow patients to order lab tests directly without a consultation (walk-in)."
    )

    # --- Reporting & Printing Settings ---
    allow_result_print_in_scan = models.BooleanField(
        default=True,
        help_text="Allow staff in the scan department to print test results."
    )
    allow_result_printing_by_consultant = models.BooleanField(
        default=True,
        help_text="Allow the ordering consultant/doctor to print test results from their dashboard."
    )

    # --- Timestamps ---
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'scan_settings'

    def __str__(self):
        return f"{self.scan_name} Settings"

