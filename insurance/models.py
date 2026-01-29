from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


# -------------------------------
# Insurance Provider
# -------------------------------
class InsuranceProviderModel(models.Model):
    PROVIDER_TYPES = [('government', 'Government'), ('private', 'Private')]
    STATUS_CHOICES = [('active', 'ACTIVE'), ('inactive', 'INACTIVE')]

    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=20, choices=PROVIDER_TYPES)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return self.name.upper()


# -------------------------------
# HMO
# -------------------------------
class HMOModel(models.Model):
    name = models.CharField(max_length=100, unique=True)
    insurance_provider = models.ForeignKey(InsuranceProviderModel, on_delete=models.SET_NULL, null=True)
    contact_person = models.CharField(max_length=100, blank=True)
    contact_email = models.EmailField(blank=True, default='')
    contact_phone_number = models.CharField(max_length=20, blank=True, default='')
    address = models.TextField(blank=True, default='')
    website = models.URLField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.name


# -------------------------------
# Coverage Plan
# -------------------------------
class HMOCoveragePlanModel(models.Model):
    COVERAGE_CHOICES = [('all', 'All'), ('include_selected', 'Include Selected'), ('exclude_selected', 'Exclude Selected'), ('none', 'None')]

    hmo = models.ForeignKey(HMOModel, on_delete=models.CASCADE, related_name='coverage_plans')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    # Consultation
    consultation_covered = models.BooleanField(default=True)
    consultation_coverage_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=70.00)
    consultation_annual_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Drug coverage
    drug_coverage = models.CharField(max_length=20, choices=COVERAGE_CHOICES, default='all')
    selected_drugs = models.ManyToManyField('pharmacy.DrugModel', blank=True, related_name='insurance_plans')
    drug_coverage_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=50.00)
    drug_annual_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Lab coverage
    lab_coverage = models.CharField(max_length=20, choices=COVERAGE_CHOICES, default='all')
    selected_lab_tests = models.ManyToManyField('laboratory.LabTestTemplateModel', blank=True, related_name='insurance_plans')
    lab_coverage_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=70.00)
    lab_annual_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Radiology coverage
    radiology_coverage = models.CharField(max_length=20, choices=COVERAGE_CHOICES, default='include_selected')
    selected_radiology = models.ManyToManyField('scan.ScanTemplateModel', blank=True, related_name='insurance_plans')
    radiology_coverage_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=60.00)
    radiology_annual_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    surgery_coverage = models.CharField(max_length=20, choices=COVERAGE_CHOICES, default='include_selected')
    selected_surgeries = models.ManyToManyField('inpatient.SurgeryType', blank=True, related_name='insurance_plans')
    surgery_coverage_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=50.00)
    surgery_annual_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    # Admission coverage
    admission_coverage = models.CharField(
        max_length=20,
        choices=COVERAGE_CHOICES,  # Uses existing COVERAGE_CHOICES
        default='include_selected',
        help_text="Coverage type for admission/bed fees"
    )
    selected_admission_types = models.ManyToManyField(
        'inpatient.AdmissionType',
        blank=True,
        related_name='insurance_plans',
        help_text="Which admission types are covered (if include_selected or exclude_selected)"
    )
    admission_coverage_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('70.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Percentage of admission costs covered by insurance"
    )
    admission_annual_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Annual limit for admission-related costs"
    )

    # Administrative
    require_verification = models.BooleanField(default=False)
    require_referral = models.BooleanField(default=False)
    annual_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return f"{self.name} - {self.hmo.name}"

    # Utility functions for coverage logic
    def is_drug_covered(self, drug):
        if self.drug_coverage == 'all':
            return True
        if self.drug_coverage == 'none':
            return False
        if self.drug_coverage == 'include_selected':
            return self.selected_drugs.filter(id=drug.id).exists()
        if self.drug_coverage == 'exclude_selected':
            return not self.selected_drugs.filter(id=drug.id).exists()
        return False

    def is_surgery_covered(self, surgery_type):
        if self.surgery_coverage == 'all':
            return True
        if self.surgery_coverage == 'none':
            return False
        if self.surgery_coverage == 'include_selected':
            return self.selected_surgeries.filter(id=surgery_type.id).exists()
        if self.surgery_coverage == 'exclude_selected':
            return not self.selected_surgeries.filter(id=surgery_type.id).exists()
        return False

    def is_lab_covered(self, lab_test):
        if self.lab_coverage == 'all':
            return True
        if self.lab_coverage == 'none':
            return False
        if self.lab_coverage == 'include_selected':
            return self.selected_lab_tests.filter(id=lab_test.id).exists()
        if self.lab_coverage == 'exclude_selected':
            return not self.selected_lab_tests.filter(id=lab_test.id).exists()
        return False

    def is_radiology_covered(self, scan):
        if self.radiology_coverage == 'all':
            return True
        if self.radiology_coverage == 'none':
            return False
        if self.radiology_coverage == 'include_selected':
            return self.selected_radiology.filter(id=scan.id).exists()
        if self.radiology_coverage == 'exclude_selected':
            return not self.selected_radiology.filter(id=scan.id).exists()
        return False

    def is_admission_type_covered(self, admission_type):
        """Check if a specific admission type is covered by this plan"""
        if self.admission_coverage == 'all':
            return True
        if self.admission_coverage == 'none':
            return False
        if self.admission_coverage == 'include_selected':
            return self.selected_admission_types.filter(id=admission_type.id).exists()
        if self.admission_coverage == 'exclude_selected':
            return not self.selected_admission_types.filter(id=admission_type.id).exists()
        return False


# -------------------------------
# Patient Insurance
# -------------------------------
class PatientInsuranceModel(models.Model):
    patient = models.ForeignKey('patient.PatientModel', on_delete=models.CASCADE, related_name='insurance_policies')
    hmo = models.ForeignKey(HMOModel, on_delete=models.CASCADE)
    coverage_plan = models.ForeignKey(HMOCoveragePlanModel, on_delete=models.CASCADE)

    policy_number = models.CharField(max_length=100)
    enrollee_id = models.CharField(max_length=100, blank=True)
    valid_from = models.DateField()
    valid_to = models.DateField()

    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)
    verification_date = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_insurance_policies')
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_insurance_policies')

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return f"{self.patient} - {self.hmo.name} ({self.policy_number})"

    @property
    def is_valid(self):
        today = timezone.now().date()
        return self.valid_from <= today <= self.valid_to and self.is_active


# -------------------------------
# Insurance Claim
# -------------------------------
class InsuranceClaimModel(models.Model):
    CLAIM_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('partially_approved', 'Partially Approved'),
        ('paid', 'Paid'),
    ]

    CLAIM_TYPE_CHOICES = [
        ('consultation', 'Consultation'),
        ('drug', 'Drug/Medication'),
        ('laboratory', 'Laboratory'),
        ('scan', 'Radiology/Scan'),
        ('surgery', 'Surgery'),
        ('admission', 'Admission'),
        ('services', 'Services'),
        ('ward_round', 'Ward Round'),
    ]

    claim_number = models.CharField(max_length=50, unique=True)
    claim_summary = models.ForeignKey(
        'InsuranceClaimSummary',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='claims',
        help_text="Groups related claims together"
    )
    patient_insurance = models.ForeignKey(PatientInsuranceModel, on_delete=models.CASCADE, related_name='claims')
    claim_type = models.CharField(max_length=20, choices=CLAIM_TYPE_CHOICES)

    # Generic relation to any order type
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object  = GenericForeignKey('content_type', 'object_id')

    # Amounts
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)  # What was claimed
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)  # What HMO approved
    covered_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                         default=0.00)  # What insurance pays (updated after approval)
    patient_amount = models.DecimalField(max_digits=12, decimal_places=2,
                                         default=0.00)  # What patient pays (updated after approval)

    status = models.CharField(max_length=20, choices=CLAIM_STATUS_CHOICES, default='pending')
    service_date = models.DateTimeField()
    claim_date = models.DateTimeField(auto_now_add=True)
    processed_date = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_claims')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='processed_claims')

    notes = models.TextField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.claim_number:
            import uuid
            self.claim_number = f"CLM-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Claim {self.claim_number} - {self.patient_insurance.patient}"

    @property
    def order_reference(self):
        """Returns a string representation of the related order"""
        if self.related_order:
            return str(self.related_order)
        return "No linked order"

    def calculate_initial_coverage(self, coverage_percentage):
        """
        Calculate initial estimated coverage when claim is created
        coverage_percentage: The percentage from the coverage plan
        """
        self.covered_amount = (self.total_amount * Decimal(str(coverage_percentage))) / Decimal('100')
        self.patient_amount = self.total_amount - self.covered_amount
        self.save()

    def process_approval(self, approved_amount, processed_by_user):
        '''
        Process claim approval - updates covered and patient amounts
        approved_amount: The amount HMO actually approved
        '''
        self.approved_amount = Decimal(str(approved_amount))

        # MODIFIED LOGIC: Check if approved amount equals expected covered amount
        if self.approved_amount == self.covered_amount:
            self.status = 'approved'  # Full approval
        elif self.approved_amount > 0:
            self.status = 'partially_approved'  # Partial approval
        else:
            self.status = 'rejected'  # Nothing approved

        self.covered_amount = self.approved_amount  # Insurance pays the approved amount
        self.patient_amount = self.total_amount - self.approved_amount  # Patient pays the difference
        self.processed_date = timezone.now()
        self.processed_by = processed_by_user
        self.save()

        # Update summary if exists
        if self.claim_summary:
            self.claim_summary.recalculate_totals()

    def process_partial_approval(self, approved_amount, processed_by_user, reason=None):
        '''
        Process partial approval
        '''
        self.approved_amount = Decimal(str(approved_amount))
        self.covered_amount = self.approved_amount
        self.patient_amount = self.total_amount - self.approved_amount
        self.status = 'partially_approved'
        self.processed_date = timezone.now()
        self.processed_by = processed_by_user
        if reason:
            self.rejection_reason = reason
        self.save()

        # Update summary if exists
        if self.claim_summary:
            self.claim_summary.recalculate_totals()

    def process_rejection(self, processed_by_user, reason):
        '''
        Process claim rejection - patient pays everything
        '''
        self.approved_amount = Decimal('0.00')
        self.covered_amount = Decimal('0.00')
        self.patient_amount = self.total_amount  # Patient pays full amount
        self.status = 'rejected'
        self.processed_date = timezone.now()
        self.processed_by = processed_by_user
        self.rejection_reason = reason
        self.save()

        # Update summary if exists
        if self.claim_summary:
            self.claim_summary.recalculate_totals()

    def mark_as_paid(self):
        """
        Mark claim as paid by HMO
        """
        if self.status in ['approved', 'partially_approved']:
            self.status = 'paid'
            self.save()
        else:
            raise ValueError("Only approved or partially approved claims can be marked as paid")

    @property
    def variance_amount(self):
        """
        Returns the difference between total claimed and approved
        Useful for reporting on HMO approval patterns
        """
        if self.approved_amount is not None:
            return self.total_amount - self.approved_amount
        return Decimal('0.00')

    @property
    def approval_percentage(self):
        """
        Returns what percentage of the claim was approved
        """
        if self.approved_amount is not None and self.total_amount > 0:
            return (self.approved_amount / self.total_amount) * 100
        return Decimal('0.00')



# -------------------------------
# Insurance Claim Summary
# -------------------------------
class InsuranceClaimSummary(models.Model):
    """
    Groups related insurance claims together for easier processing.
    One summary per consultation/admission/surgery session.
    """
    summary_number = models.CharField(max_length=50, unique=True, blank=True)

    # Link to source (one of these will be filled)
    consultation = models.ForeignKey(
        'consultation.ConsultationSessionModel',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='claim_summaries'
    )
    admission = models.ForeignKey(
        'inpatient.Admission',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='claim_summaries'
    )
    surgery = models.ForeignKey(
        'inpatient.Surgery',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='claim_summaries'
    )

    patient_insurance = models.ForeignKey(
        'PatientInsuranceModel',
        on_delete=models.CASCADE,
        related_name='claim_summaries'
    )

    # Aggregated amounts (calculated from child claims)
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_covered_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_patient_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    total_approved_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        null=True,
        blank=True
    )

    # Status (calculated from children)
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('partially_approved', 'Partially Approved'),
    ]
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )

    # Claim type (calculated from children)
    claim_type = models.CharField(
        max_length=50,
        default='mixed',
        help_text="Type of claims: drug, lab, scan, surgery, or mixed"
    )

    # Tracking
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_claim_summaries'
    )

    class Meta:
        ordering = ['-last_updated_at']
        verbose_name_plural = "Insurance Claim Summaries"

    def save(self, *args, **kwargs):
        if not self.summary_number:
            import uuid
            self.summary_number = f"SUM-{uuid.uuid4().hex[:10].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        source = self.consultation or self.admission or self.surgery
        return f"Claim Summary {self.summary_number} - {source}"

    def recalculate_totals(self):
        """Recalculate all totals and status from child claims"""
        claims = self.claims.all()

        if not claims.exists():
            self.total_amount = Decimal('0.00')
            self.total_covered_amount = Decimal('0.00')
            self.total_patient_amount = Decimal('0.00')
            self.total_approved_amount = Decimal('0.00')
            self.status = 'pending'
            self.claim_type = 'mixed'
            self.save()
            return

        # Calculate totals
        self.total_amount = sum(claim.total_amount for claim in claims)
        self.total_covered_amount = sum(claim.covered_amount for claim in claims)
        self.total_patient_amount = sum(claim.patient_amount for claim in claims)

        # Calculate approved amount (only for approved/partially approved claims)
        approved_claims = claims.filter(status__in=['approved', 'partially_approved', 'paid'])
        self.total_approved_amount = sum(
            claim.approved_amount for claim in approved_claims
            if claim.approved_amount is not None
        ) or Decimal('0.00')

        # Calculate status
        statuses = set(claims.values_list('status', flat=True))

        if len(statuses) == 1:
            # All claims have same status
            self.status = statuses.pop()
        elif 'rejected' in statuses and len(statuses) == 2 and 'pending' in statuses:
            # Some rejected, rest pending
            self.status = 'partially_approved'
        elif all(s in ['approved', 'paid'] for s in statuses):
            # All approved or paid
            self.status = 'approved'
        elif 'rejected' in statuses and any(s in ['approved', 'partially_approved', 'paid'] for s in statuses):
            # Mix of approved and rejected
            self.status = 'partially_approved'
        elif any(s in ['approved', 'partially_approved', 'paid'] for s in statuses):
            # At least one approved
            self.status = 'partially_approved'
        elif all(s == 'rejected' for s in statuses):
            # All rejected
            self.status = 'rejected'
        else:
            # Default to pending
            self.status = 'pending'

        # Calculate claim type
        claim_types = set(claims.values_list('claim_type', flat=True))

        if len(claim_types) == 1:
            # All claims are same type
            self.claim_type = claim_types.pop()
        else:
            # Mixed types
            self.claim_type = 'mixed'

        self.save()

    @property
    def patient(self):
        """Get patient from the source"""
        if self.consultation:
            return self.consultation.patient
        elif self.admission:
            return self.admission.patient
        elif self.surgery:
            return self.surgery.patient
        return None

    @property
    def source_display(self):
        """Display the source of claims"""
        if self.consultation:
            return f"Consultation - {self.consultation.created_at.strftime('%Y-%m-%d')}"
        elif self.admission:
            return f"Admission - {self.admission.admission_number}"
        elif self.surgery:
            return f"Surgery - {self.surgery.surgery_number}"
        return "Unknown"

    @property
    def claims_count(self):
        """Count of child claims"""
        return self.claims.count()

    @property
    def get_claim_type_display(self):
        """Display claim type in proper format"""
        type_map = {
            'consultation': 'Consultation',
            'drug': 'Drug/Medication',
            'laboratory': 'Laboratory',
            'scan': 'Radiology/Scan',
            'surgery': 'Surgery',
            'admission': 'Admission',
            'services': 'Services',
            'ward_round': 'Ward Round',
            'mixed': 'Mixed'
        }
        return type_map.get(self.claim_type, self.claim_type.title())

