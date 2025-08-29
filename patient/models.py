import os
import uuid
from datetime import date
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models, transaction
from admin_site.model_info import *
from consultation.models import ConsultationPaymentModel, ConsultationFeeModel

REGISTRATION_STATUS = (
    ('pending', 'PENDING'), ('completed', 'COMPLETED'), ('cancelled', 'CANCELLED')
)

PAYMENT_METHODS = (
    ("cash", "Cash"),
    ("transfer", "Transfer"),
)


class RegistrationFeeModel(models.Model):
    """"""
    title = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    PATIENT_TYPE = (('old', 'OLD'), ('new', 'NEW'))
    patient_type = models.CharField(max_length=10, choices=PATIENT_TYPE)
    created_at = models.DateTimeField(auto_now_add=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='reg_fee_created_by', null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='reg_fee_updated_by', null=True, blank=True)

    class Meta:
        ordering = ['id']
        unique_together = ('title', 'patient_type')

    def __str__(self):
        return f"{self.title.upper()} ({self.patient_type.upper()})"


class RegistrationPaymentModel(models.Model):
    """Enhanced Registration Payment Model with auto-generated transaction ID"""
    full_name = models.CharField(max_length=200)
    old_card_number = models.CharField(max_length=200, blank=True)
    registration_fee = models.ForeignKey('RegistrationFeeModel', on_delete=models.SET_NULL, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    transaction_id = models.CharField(max_length=100, blank=True, null=True, unique=True)
    registration_status = models.CharField(max_length=50, choices=REGISTRATION_STATUS, blank=True, default='pending')
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS, default="cash")
    consultation_paid = models.BooleanField(blank=True, default=False)
    consultation_fee = models.ForeignKey('consultation.ConsultationFeeModel', related_name='reg_consultation_fee', blank=True, on_delete=models.SET_NULL, null=True)
    consultation_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True, blank=True)
    date = models.DateField(auto_now_add=True, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reg_payment_created_by')

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return f"{self.full_name.upper()} - {self.transaction_id}"

    def generate_transaction_id(self):
        """Generate unique transaction ID with REG prefix"""
        if not self.transaction_id:
            # Generate until we get a unique one
            while True:
                new_id = f"REG{uuid.uuid4().hex[:8].upper()}"
                if not RegistrationPaymentModel.objects.filter(transaction_id=new_id).exists():
                    return new_id

    def save(self, *args, **kwargs):
        # Auto-generate transaction ID if not provided
        if not self.transaction_id:
            self.transaction_id = self.generate_transaction_id()

        # Calculate amounts if not provided
        if self.registration_fee and not self.amount:
            self.amount = self.registration_fee.amount

        if self.consultation_paid and self.consultation_fee:
            self.consultation_amount = self.consultation_fee.amount
            # Add consultation amount to total if not already included
            if self.registration_fee:
                self.amount = self.registration_fee.amount + self.consultation_amount

        super(RegistrationPaymentModel, self).save(*args, **kwargs)

    @property
    def is_old_patient(self):
        """Check if this is an old patient based on registration fee type"""
        return self.registration_fee and self.registration_fee.patient_type == 'old'

    @property
    def total_services_amount(self):
        """Calculate total amount for all services"""
        total = self.registration_fee.amount if self.registration_fee else 0
        if self.consultation_paid and self.consultation_amount:
            total += self.consultation_amount
        return total


class PatientModel(models.Model):
    """This model handles patient"""
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, null=True, blank=True, default='')
    last_name = models.CharField(max_length=50)
    card_number = models.CharField(max_length=50, unique=True, blank=True, null=True, db_index=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDER)
    occupation = models.CharField(max_length=100, blank=True, null=True, default='')
    address = models.CharField(max_length=250, null=True, blank=True, default='')

    image = models.FileField(blank=True, null=True, upload_to='images/patient')
    mobile = models.CharField(max_length=20, null=True, blank=True, default='')
    email = models.EmailField(max_length=100, null=True, blank=True, default='')

    marital_status = models.CharField(max_length=30, choices=MARITAL_STATUS, null=True, blank=True, default='')
    religion = models.CharField(max_length=30, choices=RELIGION, null=True, blank=True, default='')
    state = models.CharField(max_length=100, null=True, blank=True, default='')
    lga = models.CharField(max_length=100, null=True, blank=True, default='')

    blood_group = models.CharField(max_length=20, choices=BLOOD_GROUP, null=True, blank=True, default='')
    genotype = models.CharField(max_length=20, choices=GENOTYPE, null=True, blank=True, default='')
    medical_note = models.TextField(null=True, blank=True, default='')

    next_of_kin_name = models.CharField(max_length=200, null=True, blank=True, default='')
    next_of_kin_number = models.CharField(max_length=20, null=True, blank=True, default='')
    next_of_kin_address = models.CharField(max_length=250, null=True, blank=True, default='')

    registration_date = models.DateField(auto_now_add=True, blank=True, null=True)
    status = models.CharField(max_length=15, blank=True, default='active')
    registration_payment = models.OneToOneField(RegistrationPaymentModel, related_name='patient', null=True, on_delete=models.SET_NULL)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='patient_created_by')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        if self.middle_name:
            return "{} {} {}".format(self.first_name, self.middle_name, self.last_name)
        else:
            return "{} {}".format(self.first_name, self.last_name)

    def save(self, *args, **kwargs):
        # Validate required fields
        if not self.first_name or not self.last_name:
            from django.core.exceptions import ValidationError
            raise ValidationError("First name and last name are required")

        # Only generate ID if it doesn't exist
        if not self.card_number:
            self.card_number = self.generate_unique_patient_id()

        super(PatientModel, self).save(*args, **kwargs)

    @transaction.atomic
    def generate_unique_patient_id(self):
        """
        Bulletproof patient ID generation following HR model pattern
        """
        try:
            setting = PatientSettingModel.objects.first()

            # If manual mode or no settings, generate timestamp-based ID
            if not setting or not setting.auto_generate_patient_id:
                return self._generate_manual_fallback()

            # Get or create the counter record
            last_entry, created = PatientIDGeneratorModel.objects.select_for_update().get_or_create(
                id=1,  # Always use same record
                defaults={'last_id': 0, 'last_patient_id': '0000'}
            )

            max_attempts = 50  # Increased for production
            for attempt in range(max_attempts):
                # Increment counter
                last_entry.last_id += 1
                new_id = str(last_entry.last_id).zfill(4)

                # Build full patient ID
                full_id = self._build_patient_id(setting, new_id)

                # Check if unique
                if not PatientModel.objects.filter(card_number=full_id).exists():
                    last_entry.last_patient_id = new_id
                    last_entry.status = 's'  # Success
                    last_entry.save()
                    return full_id

                # If not unique, continue with next number
                continue

            # Fallback if all attempts failed
            return self._generate_uuid_fallback()

        except Exception as e:
            # Log the error in production
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Patient ID generation failed: {str(e)}")
            return self._generate_uuid_fallback()

    def _build_patient_id(self, setting, counter):
        """Build patient ID from components"""
        prefix = setting.patient_id_prefix or 'PAT'
        return f"{prefix}{counter}"

    def _generate_manual_fallback(self):
        """Simple fallback for manual mode"""
        from django.utils import timezone
        timestamp = timezone.now().strftime('%y%m%d%H%M%S')
        return f"PAT-{timestamp}"

    def _generate_uuid_fallback(self):
        """Ultimate fallback using short UUID"""
        return f"PAT-{str(uuid.uuid4())[:8].upper()}"

    def age(self):
        """Calculate patient age safely"""

        if self.date_of_birth:
            try:
                today = date.today()
                return today.year - self.date_of_birth.year - (
                        (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
                )
            except (AttributeError, TypeError):
                return ''
        return ''


class PatientIDGeneratorModel(models.Model):
    id = models.AutoField(primary_key=True)  # Make it explicit
    last_id = models.BigIntegerField(default=0)  # Change to BigIntegerField for consistency
    last_patient_id = models.CharField(max_length=100, null=True, blank=True)
    STATUS = (
        ('s', 'SUCCESS'),
        ('f', 'FAIL')
    )
    status = models.CharField(max_length=10, choices=STATUS, blank=True, default='f')
    updated_at = models.DateTimeField(auto_now=True)  # Add timestamp for debugging

    class Meta:
        # Ensure only one record exists
        constraints = [
            models.CheckConstraint(check=models.Q(id=1), name='single_patient_generator_record')
        ]


class PatientSettingModel(models.Model):
    """This model handles all setting related to patient"""
    auto_generate_patient_id = models.BooleanField(default=True)
    patient_id_prefix = models.CharField(max_length=10, blank=True, null=True, default='PAT')
    generate_new_card_number = models.BooleanField(default=False)
    registration_fee = models.FloatField(default=0.0)

    def save(self, *args, **kwargs):
        # Ensure only one settings record exists
        if not self.pk and PatientSettingModel.objects.exists():
            raise ValidationError("Only one patient settings record is allowed")
        super().save(*args, **kwargs)


class PatientRegistrationPriceHistoryModel(models.Model):
    """
    Keeps a historical record of changes in patient registration price.
    """
    old_price = models.DecimalField(max_digits=10, decimal_places=2)
    new_price = models.DecimalField(max_digits=10, decimal_places=2)
    change_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-change_date']
        verbose_name_plural = "Price History"

    def __str__(self):
        return f"{self.old_price} -> {self.new_price} on {self.change_date.date()}"


class PatientWalletModel(models.Model):
    patient = models.OneToOneField(PatientModel, on_delete=models.CASCADE, related_name='wallet')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.patient} - {self.amount:.2f}"

    def add_funds(self, amount):
        """Safely add funds to wallet"""
        if amount > 0:
            self.amount += amount
            self.save()

    def deduct_funds(self, amount):
        """Safely deduct funds from wallet"""
        if amount > 0 and self.amount >= amount:
            self.amount -= amount
            self.save()
            return True
        return False


def consultation_document_path(instance, filename):
    """Generate file path for consultation documents"""
    return f'consultation_docs/{instance.patient.id}/{filename}'


class ConsultationDocument(models.Model):
    patient = models.ForeignKey('PatientModel', on_delete=models.CASCADE, related_name='consultation_documents')
    document = models.FileField(upload_to=consultation_document_path)
    title = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.patient} - {self.title or self.document.name}"

    @property
    def filename(self):
        return os.path.basename(self.document.name)