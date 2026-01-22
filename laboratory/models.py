from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal
from datetime import date


# 1. LAB TEST CATEGORIES (Simple grouping)
class LabTestCategoryModel(models.Model):
    """Categories like Hematology, Chemistry, Microbiology, etc."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, blank=True)
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lab_test_categories'
        verbose_name_plural = 'Lab Test Categories'
        ordering = ['name']

    def __str__(self):
        return self.name


# 2. LAB TEST TEMPLATES (The Key Simplification!)
class LabTestTemplateModel(models.Model):
    """Pre-built test templates with standard parameters"""
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)
    category = models.ForeignKey(
        LabTestCategoryModel,
        on_delete=models.CASCADE,
        related_name='templates'
    )

    # Test configuration as JSON - this is the magic!
    test_parameters = models.JSONField(
        default=dict,
        help_text="""
        Standard format:
        {
            "parameters": [
                {
                    "name": "Hemoglobin",
                    "code": "HGB", 
                    "unit": "g/dL",
                    "normal_range": {"min": 12.0, "max": 16.0, "gender_specific": true},
                    "type": "numeric"
                },
                {
                    "name": "Blood Group",
                    "code": "BG",
                    "type": "select",
                    "options": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"]
                }
            ]
        }
        """
    )

    # Pricing
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])

    # Sample requirements
    sample_type = models.CharField(
        max_length=50,
        choices=[
            ('blood', 'Blood'),
            ('urine', 'Urine'),
            ('stool', 'Stool'),
            ('sputum', 'Sputum'),
            ('csf', 'CSF'),
            ('other', 'Other'),
        ],
        default='blood'
    )
    sample_volume = models.CharField(max_length=50, blank=True, help_text="e.g., 5ml, 10ml")

    # Status
    is_active = models.BooleanField(default=True)
    reason_for_deactivate = models.CharField(max_length=250, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lab_test_templates'
        ordering = ['category__name', 'name']

    def __str__(self):
        return f"{self.name} ({self.code})"

    @property
    def parameter_names(self):
        """Quick preview of parameters"""
        if self.test_parameters and 'parameters' in self.test_parameters:
            return [param['name'] for param in self.test_parameters['parameters']]
        return []


# 3. LAB TEST ORDERS (When a test is requested)
class LabTestOrderModel(models.Model):
    """Individual test orders for patients"""
    # Using Patient model from your existing system
    # MODIFY existing patient field
    patient = models.ForeignKey(
        'patient.PatientModel',
        on_delete=models.CASCADE,
        null=True,  # ADD: null=True
        blank=True,  # ADD: blank=True
        related_name='lab_orders'
    )

    # ADD: Walk-in customer name
    customer_name = models.CharField(
        max_length=200,
        blank=True,
        default='',
        help_text="Name of walk-in customer (only used when patient is null)"
    )

    # ADD: Source tracking
    SOURCE_CHOICES = [
        ('doctor', 'Doctor Prescribed'),
        ('lab', 'Lab Direct Order'),
        ('admission', 'Admission'),
        ('walkin', 'Walk-in'),  # ADD: New option
    ]

    # MODIFY existing source field
    source = models.CharField(
        max_length=20,
        choices=SOURCE_CHOICES,
        default='walkin',  # CHANGE: Default to 'walkin' for direct sales
        help_text='Source of the test order'
    )
    template = models.ForeignKey(LabTestTemplateModel, on_delete=models.CASCADE, related_name='orders')

    # Order details
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    ordered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='ordered_tests')

    # Status tracking
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid - Awaiting Sample'),
        ('collected', 'Sample Collected'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    status = models.CharField(max_length=20, blank=True, choices=STATUS_CHOICES, default='pending')

    admission = models.ForeignKey(
        'inpatient.Admission',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lab_test_orders',
        help_text="Link to an admission record if applicable"
    )
    consultation = models.ForeignKey(
        'consultation.ConsultationSessionModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lab_consultation_order',
    )
    surgery = models.ForeignKey(
        'inpatient.Surgery',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lab_test_orders',
        help_text="Link to a surgery record if applicable"
    )

    # Payment
    amount_charged = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    payment_status = models.BooleanField(default=True, blank=True)
    payment_date = models.DateTimeField(blank=True, null=True)
    payment_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='processed_payments')

    # Sample collection
    sample_collected_at = models.DateTimeField(blank=True, null=True)
    sample_collected_by = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True,
                                            related_name='collected_samples')
    sample_label = models.CharField(max_length=50, blank=True)

    # Processing
    processed_at = models.DateTimeField(blank=True, null=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_tests')

    # Dates
    ordered_at = models.DateTimeField(auto_now_add=True)
    expected_completion = models.DateTimeField(blank=True, null=True)

    # Notes
    special_instructions = models.TextField(blank=True)
    # Payment tracking
    payment_method = models.CharField(
        max_length=20,
        choices=[
            ('cash', 'Cash'),
            ('card', 'Card'),
            ('transfer', 'Transfer'),
            ('wallet', 'Patient Wallet'),
            ('admission', 'Admission Deposit'),
            ('insurance', 'Insurance'),
        ],
        default='cash',
        blank=True
    )

    class Meta:
        db_table = 'lab_test_orders'
        ordering = ['-ordered_at']
        permissions = [
            ("view_financial_report", "Can view financial reports"),
        ]
        indexes = [
            models.Index(fields=['source', 'status']),
        ]


    @property
    def customer_display(self):
        """Returns patient name or walk-in customer name"""
        if self.patient:
            return str(self.patient)
        return self.customer_name or "Walk-in Customer"

    # MODIFY existing __str__ method
    def __str__(self):
        customer = str(self.patient) if self.patient else self.customer_name or "Walk-in"  # MODIFY
        return f"{self.template.name} - {customer} ({self.order_number})"

    def save(self, *args, **kwargs):
        if not self.order_number:
            # Auto-generate order number
            today = date.today()
            date_str = today.strftime('%Y%m%d')
            last_order = LabTestOrderModel.objects.filter(
                order_number__startswith=f'LAB{date_str}'
            ).order_by('-order_number').first()

            if last_order:
                try:
                    last_num = int(last_order.order_number[-3:])
                    next_num = last_num + 1
                except ValueError:
                    next_num = 1
            else:
                next_num = 1

            self.order_number = f'LAB{date_str}{str(next_num).zfill(3)}'

        if not self.amount_charged:
            self.amount_charged = self.template.price

        super().save(*args, **kwargs)

    @property
    def total_amount(self):
        """Return the amount charged for this lab test"""
        return self.amount_charged or Decimal('0.00')


class ExternalLabTestOrder(models.Model):
    """Lab tests performed externally (template.is_active=False)"""
    patient = models.ForeignKey(
        'patient.PatientModel',
        on_delete=models.CASCADE,
        related_name='external_lab_orders'
    )
    consultation = models.ForeignKey(
        'consultation.ConsultationSessionModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='external_lab_orders',
    )
    ordered_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ordered_external_lab_tests'
    )

    # Template info (stored as text since template might be deactivated)
    test_name = models.CharField(max_length=200)
    test_code = models.CharField(max_length=20, blank=True)
    category_name = models.CharField(max_length=100, blank=True)

    # Instructions
    special_instructions = models.TextField(blank=True)

    # External result file
    result_file = models.FileField(
        upload_to='external_lab_results/%Y/%m/',
        blank=True,
        null=True,
        help_text="Upload external lab report (PDF/Image)"
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
        related_name='uploaded_external_lab_results'
    )

    class Meta:
        db_table = 'external_lab_test_orders'
        ordering = ['-ordered_at']
        verbose_name = 'External Lab Test Order'
        verbose_name_plural = 'External Lab Test Orders'

    def __str__(self):
        return f"External: {self.test_name} - {self.patient} ({self.order_number})"

    def save(self, *args, **kwargs):
        if not self.order_number:
            today = date.today()
            date_str = today.strftime('%Y%m%d')
            last_order = ExternalLabTestOrder.objects.filter(
                order_number__startswith=f'EXTLAB{date_str}'
            ).order_by('-order_number').first()

            if last_order:
                try:
                    last_num = int(last_order.order_number[-3:])
                    next_num = last_num + 1
                except ValueError:
                    next_num = 1
            else:
                next_num = 1

            self.order_number = f'EXTLAB{date_str}{str(next_num).zfill(3)}'

        super().save(*args, **kwargs)

    @property
    def has_result(self):
        return bool(self.result_file)


# 4. LAB TEST RESULTS (The actual results)
class LabTestResultModel(models.Model):
    """Test results - stores the actual values"""
    order = models.OneToOneField(LabTestOrderModel, on_delete=models.CASCADE, related_name='result')

    # Results stored as JSON matching the template structure
    results_data = models.JSONField(
        default=dict,
        help_text="""
        Results in same structure as template:
        {
            "results": [
                {
                    "parameter_code": "HGB",
                    "parameter_name": "Hemoglobin", 
                    "value": "14.5",
                    "unit": "g/dL",
                    "normal_range": "12.0-16.0",
                    "status": "normal"  # normal, high, low, abnormal
                }
            ]
        }
        """
    )

    # Lab technician notes
    technician_comments = models.TextField(blank=True)
    pathologist_comments = models.TextField(blank=True)

    # Quality control
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='verified_results')
    verified_at = models.DateTimeField(blank=True, null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lab_test_results'

        permissions = [
            ("can_verify_lab_result", "Can verify lab test result"),
        ]

    def __str__(self):
        return f"Results: {self.order}"

    @property
    def has_abnormal_values(self):
        """Check if any results are outside normal range"""
        if self.results_data and 'results' in self.results_data:
            return any(
                result.get('status') in ['high', 'low', 'abnormal']
                for result in self.results_data['results']
            )
        return False


# 5. LAB EQUIPMENT (Simplified)
class LabEquipmentModel(models.Model):
    """Basic equipment tracking"""
    name = models.CharField(max_length=200)
    model_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True, unique=True)

    # Which tests can this equipment perform
    supported_templates = models.ManyToManyField(
        LabTestTemplateModel,
        blank=True,
        related_name='equipment'
    )

    # Status
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('maintenance', 'Under Maintenance'),
        ('inactive', 'Inactive'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Basic details
    purchase_date = models.DateField(blank=True, null=True)
    last_maintenance = models.DateField(blank=True, null=True)
    next_maintenance = models.DateField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lab_equipment'
        ordering = ['name']

    def __str__(self):
        return self.name


# 6. LAB REAGENTS (Simplified inventory)
class LabReagentModel(models.Model):
    """Basic reagent/consumable tracking"""
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100, blank=True)
    catalog_number = models.CharField(max_length=100, blank=True)

    # Which tests use this reagent
    used_in_templates = models.ManyToManyField(
        LabTestTemplateModel,
        blank=True,
        related_name='reagents'
    )

    # Stock tracking
    current_stock = models.IntegerField(default=0)
    minimum_stock = models.IntegerField(default=10)
    unit = models.CharField(max_length=50, default='pieces')

    # Expiry tracking
    expiry_date = models.DateField(blank=True, null=True)

    # Status
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'lab_reagents'
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.current_stock <= self.minimum_stock

    @property
    def is_expired(self):
        if self.expiry_date:
            return self.expiry_date <= date.today()
        return False


# 7. TEST TEMPLATE BUILDER (For easy setup)
class LabTestTemplateBuilderModel(models.Model):
    """Helper model for building test templates easily"""
    name = models.CharField(max_length=200)
    category = models.ForeignKey(LabTestCategoryModel, on_delete=models.CASCADE)

    # Common parameter combinations
    parameter_preset = models.CharField(
        max_length=100,
        choices=[
            ('basic_chemistry', 'Basic Chemistry Panel'),
            ('lipid_profile', 'Lipid Profile'),
            ('liver_function', 'Liver Function Tests'),
            ('kidney_function', 'Kidney Function Tests'),
            ('thyroid_function', 'Thyroid Function Tests'),
            ('complete_blood_count', 'Complete Blood Count'),
            ('urinalysis', 'Urinalysis'),
            ('custom', 'Custom Parameters'),
        ]
    )

    # Will auto-populate test_parameters based on preset
    custom_parameters = models.JSONField(default=list, blank=True)

    price = models.DecimalField(max_digits=10, decimal_places=2)
    sample_type = models.CharField(max_length=50, default='blood')

    is_processed = models.BooleanField(default=False)
    created_template = models.ForeignKey(
        LabTestTemplateModel,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'lab_template_builders'

    def __str__(self):
        status = "✓ Built" if self.is_processed else "⏳ Pending"
        return f"{self.name} ({status})"

    def build_template(self):
        """Convert this builder into an actual template"""
        if self.is_processed:
            return {"error": "Template already built"}

        # Get preset parameters or use custom
        if self.parameter_preset != 'custom':
            parameters = self._get_preset_parameters()
        else:
            parameters = self.custom_parameters

        # Create the template
        template = LabTestTemplateModel.objects.create(
            name=self.name,
            code=self.name.upper().replace(' ', '_'),
            category=self.category,
            test_parameters={"parameters": parameters},
            price=self.price,
            sample_type=self.sample_type
        )

        # Mark as processed
        self.is_processed = True
        self.created_template = template
        self.save()

        return {"success": True, "template": template}

    def _get_preset_parameters(self):
        """Get standard parameters for common test types"""
        presets = {
            'complete_blood_count': [
                {"name": "Hemoglobin", "code": "HGB", "unit": "g/dL", "type": "numeric",
                 "normal_range": {"min": 12.0, "max": 16.0}},
                {"name": "Hematocrit", "code": "HCT", "unit": "%", "type": "numeric",
                 "normal_range": {"min": 36.0, "max": 48.0}},
                {"name": "WBC Count", "code": "WBC", "unit": "×10³/µL", "type": "numeric",
                 "normal_range": {"min": 4.0, "max": 11.0}},
                {"name": "Platelet Count", "code": "PLT", "unit": "×10³/µL", "type": "numeric",
                 "normal_range": {"min": 150.0, "max": 450.0}},
            ],
            'lipid_profile': [
                {"name": "Total Cholesterol", "code": "CHOL", "unit": "mg/dL", "type": "numeric",
                 "normal_range": {"max": 200.0}},
                {"name": "LDL Cholesterol", "code": "LDL", "unit": "mg/dL", "type": "numeric",
                 "normal_range": {"max": 100.0}},
                {"name": "HDL Cholesterol", "code": "HDL", "unit": "mg/dL", "type": "numeric",
                 "normal_range": {"min": 40.0}},
                {"name": "Triglycerides", "code": "TRIG", "unit": "mg/dL", "type": "numeric",
                 "normal_range": {"max": 150.0}},
            ],
            'liver_function': [
                {"name": "ALT", "code": "ALT", "unit": "U/L", "type": "numeric", "normal_range": {"max": 40.0}},
                {"name": "AST", "code": "AST", "unit": "U/L", "type": "numeric", "normal_range": {"max": 40.0}},
                {"name": "Total Bilirubin", "code": "TBIL", "unit": "mg/dL", "type": "numeric",
                 "normal_range": {"max": 1.2}},
                {"name": "Alkaline Phosphatase", "code": "ALP", "unit": "U/L", "type": "numeric",
                 "normal_range": {"min": 44.0, "max": 147.0}},
            ]
        }

        return presets.get(self.parameter_preset, [])


# 8. LAB SETTINGS
class LabSettingModel(models.Model):
    """
    A singleton model to hold global settings for the Laboratory module.
    """
    # --- Workflow & Policy Settings (Your Suggestions Included) ---
    lab_name = models.CharField(max_length=200, blank=True, default='')
    mobile = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(max_length=100, blank=True, null=True)
    allow_direct_lab_order = models.BooleanField(
        default=False,
        help_text="Allow patients to order lab tests directly without a consultation (walk-in)."
    )

    # --- Reporting & Printing Settings ---
    allow_result_print_in_lab = models.BooleanField(
        default=True,
        help_text="Allow staff in the laboratory department to print test results."
    )
    allow_result_printing_by_consultant = models.BooleanField(
        default=True,
        help_text="Allow the ordering consultant/doctor to print test results from their dashboard."
    )

    # --- Timestamps ---
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return "Laboratory Settings"

    class Meta:
        verbose_name_plural = "Laboratory Settings"

    def save(self, *args, **kwargs):
        # Enforce a single instance of the settings
        self.pk = 1
        super(LabSettingModel, self).save(*args, **kwargs)
