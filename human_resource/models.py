import uuid
from django.contrib.auth.models import User, Group
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from admin_site.model_info import *
import logging

logger = logging.getLogger(__name__)


class DepartmentModel(models.Model):
    """"""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name'],
                name='unique_dept_name_combo'
            )
        ]

    def __str__(self):
        return self.name.upper()

    def number_of_staff(self):
        return StaffModel.objects.filter(department=self).count()

    def hod(self):
        hod = HODModel.objects.filter(status='active', department=self).first()
        if hod:
            return hod.hod


class HODModel(models.Model):
    """"""
    department = models.ForeignKey(DepartmentModel, on_delete=models.CASCADE)
    hod = models.ForeignKey('StaffModel', on_delete=models.CASCADE)
    deputy_hod = models.ForeignKey('StaffModel', on_delete=models.SET_NULL, blank=True, null=True, related_name='deputy_hod')
    status = models.CharField(max_length=50, choices=[('active', 'ACTIVE'), ('next', 'NEXT'), ('past', 'PAST')])
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        return f"{self.hod.__str__()} - HOD of {self.department.__str__()}"


class PositionModel(models.Model):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(DepartmentModel, on_delete=models.CASCADE, related_name='positions')
    staff_login = models.BooleanField(default=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'department'],
                name='unique_name_and_dept_combo'
            )
        ]

    def __str__(self):
        return self.name.upper()

    def number_of_staff(self):
        return StaffModel.objects.filter(position=self).count()


class StaffModel(models.Model):
    """"""
    first_name = models.CharField(max_length=50)
    middle_name = models.CharField(max_length=50, null=True, blank=True, default='')
    last_name = models.CharField(max_length=50)

    image = models.ImageField(upload_to='images/staff', blank=True, null=True)
    address = models.CharField(max_length=200, blank=True, null=True)
    mobile = models.CharField(max_length=20)
    email = models.EmailField(max_length=100, blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER)
    date_of_birth = models.DateField(null=True, blank=True)
    marital_status = models.CharField(max_length=30, choices=MARITAL_STATUS, null=True, blank=True)
    religion = models.CharField(max_length=30, choices=RELIGION, null=True, blank=True)
    state = models.CharField(max_length=100, null=True, blank=True)
    lga = models.CharField(max_length=100, null=True, blank=True)

    department = models.ForeignKey(DepartmentModel, on_delete=models.CASCADE, related_name='department_staffs', db_index=True)
    position = models.ForeignKey(PositionModel, on_delete=models.CASCADE, related_name='position_staffs')
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
    staff_id = models.CharField(max_length=100, unique=True, blank=True)
    employment_date = models.DateField(blank=True, null=True)
    cv = models.FileField(upload_to='staff/cv', null=True, blank=True)
    contract_type = models.CharField(max_length=50, choices=CONTRACT_TYPE)
    contract_start_date = models.DateField(blank=True, null=True)
    contract_end_date = models.DateField(blank=True, null=True)
    contract_status = models.CharField(max_length=50, choices=ACTIVE_STATUS, default='active')

    blood_group = models.CharField(max_length=20, null=True, choices=BLOOD_GROUP, blank=True)
    genotype = models.CharField(max_length=20, null=True, blank=True, choices=GENOTYPE)
    health_note = models.TextField(null=True, blank=True)

    status = models.CharField(max_length=30, blank=True, default='active', choices=STAFF_ACTIVE_TYPE)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_created_by')
    created_at = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, blank=True, null=True)

    def __str__(self):
        if self.middle_name:
            return "{} {} {}".format(self.first_name, self.middle_name, self.last_name)

        return "{} {}".format(self.first_name, self.last_name)

    def save(self, *args, **kwargs):
        """
        Enhanced save method with better user synchronization.
        Generates staff ID and syncs user data safely.
        """
        # Generate staff ID if not exists
        if not self.staff_id:
            self.staff_id = self.generate_unique_staff_id()

        # Save the staff record first
        super(StaffModel, self).save(*args, **kwargs)

        # Sync with user profile only for existing records (updates)
        if self.pk:
            self._sync_user_profile()

    def _sync_user_profile(self):
        """
        Synchronize staff data with associated user profile.
        Only runs for existing staff records, not new ones.
        """
        try:
            staff_profile = StaffProfileModel.objects.select_related('user').filter(staff=self).first()
            if not staff_profile:
                return  # No user profile exists yet

            user = staff_profile.user
            user_updated = False

            # Update email if changed and provided
            if self.email and user.email != self.email:
                user.email = self.email
                user_updated = True

            # Update names if changed
            if user.first_name != self.first_name:
                user.first_name = self.first_name
                user_updated = True

            if user.last_name != self.last_name:
                user.last_name = self.last_name
                user_updated = True

            # Save user if any changes made
            if user_updated:
                user.save()
                logger.info(f"Updated user profile for staff {self.staff_id}")

            # Update group membership
            if self.group and not user.groups.filter(id=self.group.id).exists():
                self.group.user_set.add(user)

        except Exception as e:
            logger.exception(f"Failed to sync user profile for staff {self.staff_id}: {str(e)}")
            # Don't raise exception to avoid breaking staff updates

    @transaction.atomic
    def generate_unique_staff_id(self):
        """
        Bulletproof staff ID generation with minimal code
        """
        setting = HRSettingModel.objects.first()

        # If manual mode, generate timestamp-based ID
        if not setting or not setting.auto_generate_staff_id:
            return self._generate_manual_fallback()

        # Get or create the counter record
        last_entry, created = StaffIDGeneratorModel.objects.select_for_update().get_or_create(
            id=1,  # Always use same record
            defaults={'last_id': 0, 'last_staff_id': '0000'}
        )

        max_attempts = 20
        for attempt in range(max_attempts):
            # Increment counter
            last_entry.last_id += 1
            new_id = str(last_entry.last_id).zfill(4)

            # Build full staff ID
            full_id = self._build_staff_id(setting, new_id)

            # Check if unique
            if not StaffModel.objects.filter(staff_id=full_id).exists():
                last_entry.last_staff_id = new_id
                last_entry.save()
                return full_id

            # If not unique, continue with next number
            continue

        # Fallback if all attempts failed
        return self._generate_uuid_fallback()

    def _build_staff_id(self, setting, counter):
        """Build staff ID from components"""
        prefix = setting.staff_prefix or 'STF'
        dept_code = None

        if setting.use_dept_prefix_for_id and self.department and self.department.code:
            dept_code = self.department.code

        if dept_code:
            return f"{prefix}-{dept_code}-{counter}"
        else:
            return f"{prefix}-{counter}"

    def _generate_manual_fallback(self):
        """Simple fallback for manual mode"""
        from django.utils import timezone
        timestamp = timezone.now().strftime('%y%m%d%H%M%S')
        return f"STF-{timestamp}"

    def _generate_uuid_fallback(self):
        """Ultimate fallback using short UUID"""
        return f"STF-{str(uuid.uuid4())[:8].upper()}"

    def get_user_account(self):
        user = StaffProfileModel.objects.filter(staff=self).first().user
        return user

    def is_contract_active(self):
        if not self.contract_end_date:
            return True
        return timezone.now().date() <= self.contract_end_date

    def get_active_licenses(self):
        return self.licenses.filter(is_active=True, expiry_date__gte=timezone.now().date())

    def has_valid_license(self):
        return self.get_active_licenses().exists()


class StaffIDGeneratorModel(models.Model):
    id = models.AutoField(primary_key=True)  # Make it explicit
    last_id = models.BigIntegerField(default=0)
    last_staff_id = models.CharField(max_length=100, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class StaffProfileModel(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, blank=True, related_name='user_staff_profile')
    staff = models.OneToOneField(StaffModel, on_delete=models.CASCADE, null=True, related_name='staff_profile')

    def __str__(self):
        return self.staff.__str__()


class HRSettingModel(models.Model):
    auto_generate_staff_id = models.BooleanField(default=True)
    staff_prefix = models.CharField(max_length=10, blank=True, null=True, default='stf')
    use_dept_prefix_for_id = models.BooleanField(default=False)
    allow_profile_edit = models.BooleanField(default=False)


class StaffLeaveModel(models.Model):
    staff = models.ForeignKey('StaffModel', on_delete=models.CASCADE, related_name='leaves')
    leave_type = models.CharField(max_length=50, choices=LEAVE_TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    applied_days = models.PositiveIntegerField()
    approved_days = models.PositiveIntegerField(null=True, blank=True)
    reason = models.TextField(null=True, blank=True)
    approval_status = models.CharField(max_length=30, choices=LEAVE_STATUS, default='pending', blank=True)
    status = models.CharField(max_length=20, default='Pending', choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')])
    applied_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='leave_appliers')
    approved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='leave_approvals')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Leave request for {self.staff} ({self.leave_type})"


DOCUMENT_TYPES = [
        ('Certificate', 'Certificate'),
        ('Licence', 'Licence'),
        ('others', 'OTHERS')
    ]


class StaffDocumentModel(models.Model):
    staff = models.ForeignKey('StaffModel', on_delete=models.CASCADE, related_name='staff_documents')
    title = models.CharField(max_length=250, blank=True, default="")
    document_type = models.CharField(max_length=50, choices=DOCUMENT_TYPES)
    document = models.FileField(upload_to='staff/document')
    uploaded_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='staff_doc_uploader')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title if self.title else f'{self.staff.__str__()} {self.document_type} Document'


