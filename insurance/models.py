from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from django.utils import timezone


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
    contact_email = models.EmailField(blank=True, null=True)
    contact_phone_number = models.CharField(max_length=20, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    website = models.URLField(blank=True, null=True)
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
        ('radiology', 'Radiology/Scan'),
        ('multiple', 'Multiple Services'),
    ]

    claim_number = models.CharField(max_length=50, unique=True)
    patient_insurance = models.ForeignKey(PatientInsuranceModel, on_delete=models.CASCADE, related_name='claims')
    claim_type = models.CharField(max_length=20, choices=CLAIM_TYPE_CHOICES)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    covered_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    patient_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=CLAIM_STATUS_CHOICES, default='pending')
    service_date = models.DateTimeField()
    claim_date = models.DateTimeField(auto_now_add=True)
    processed_date = models.DateTimeField(null=True, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_claims')
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_claims')

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

