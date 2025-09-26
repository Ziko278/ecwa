from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User, Group
from datetime import datetime, date
import re
from human_resource.models import *


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = DepartmentModel
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Department Name'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'DEPT', 'maxlength': '20'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Department name is required.")

        # Remove extra spaces and validate
        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Department name must be at least 2 characters long.")

        # Check for special characters (allow only letters, numbers, spaces, hyphens)
        if not re.match(r'^[a-zA-Z0-9\s\-&]+$', name):
            raise ValidationError("Department name contains invalid characters.")

        # Check uniqueness (case-insensitive)
        existing = DepartmentModel.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Department '{name}' already exists.")

        return name

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper().strip()

            # Validate format
            if not re.match(r'^[A-Z0-9]+$', code):
                raise ValidationError("Department code must contain only letters and numbers.")

            if len(code) < 2 or len(code) > 20:
                raise ValidationError("Department code must be between 2 and 20 characters.")

            # Check uniqueness
            existing = DepartmentModel.objects.filter(code=code)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"Department code '{code}' already exists.")

        return code


class PositionForm(forms.ModelForm):
    class Meta:
        model = PositionModel
        fields = ['name', 'department', 'staff_login', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'staff_login': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = DepartmentModel.objects.all()

    def clean_name(self):
        name = self.cleaned_data.get('name')
        department = self.cleaned_data.get('department')

        if not name:
            raise ValidationError("Position name is required.")

        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Position name must be at least 2 characters long.")

        # Validate format
        if not re.match(r'^[a-zA-Z0-9\s\-&/()]+$', name):
            raise ValidationError("Position name contains invalid characters.")

        # Check uniqueness within department
        if department:
            existing = PositionModel.objects.filter(name__iexact=name, department=department)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"Position '{name}' already exists in {department.name}.")

        return name

    def clean_department(self):
        department = self.cleaned_data.get('department')
        if not department:
            raise ValidationError("Department is required.")
        return department


class StaffForm(forms.ModelForm):
    class Meta:
        model = StaffModel
        fields = [
            'first_name', 'middle_name', 'last_name', 'image', 'address', 'mobile', 'email',
            'gender', 'date_of_birth', 'marital_status', 'religion', 'state', 'lga',
            'department', 'position', 'group', 'employment_date', 'cv',
            'contract_type', 'contract_start_date', 'contract_end_date',
            'blood_group', 'genotype', 'health_note'
        ]

        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'marital_status': forms.Select(attrs={'class': 'form-control'}),
            'religion': forms.Select(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'lga': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'position': forms.Select(attrs={'class': 'form-control'}),
            'group': forms.Select(attrs={'class': 'form-control'}),
            'employment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'cv': forms.FileInput(attrs={'class': 'form-control', 'accept': '.pdf,.doc,.docx'}),
            'contract_type': forms.Select(attrs={'class': 'form-control'}),
            'contract_start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'contract_end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'blood_group': forms.Select(attrs={'class': 'form-control'}),
            'genotype': forms.Select(attrs={'class': 'form-control'}),
            'health_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = DepartmentModel.objects.all()
        self.fields['position'].queryset = PositionModel.objects.all()
        self.fields['group'].queryset = Group.objects.all()

        # Set empty labels
        self.fields['department'].empty_label = "Select Department"
        self.fields['position'].empty_label = "Select Position"

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        if not first_name:
            raise ValidationError("First name is required.")

        first_name = first_name.strip().title()
        if len(first_name) < 2:
            raise ValidationError("First name must be at least 2 characters long.")

        if not re.match(r'^[a-zA-Z\s\-\']+$', first_name):
            raise ValidationError("First name contains invalid characters.")

        return first_name

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        if not last_name:
            raise ValidationError("Last name is required.")

        last_name = last_name.strip().title()
        if len(last_name) < 2:
            raise ValidationError("Last name must be at least 2 characters long.")

        if not re.match(r'^[a-zA-Z\s\-\']+$', last_name):
            raise ValidationError("Last name contains invalid characters.")

        return last_name

    def clean_middle_name(self):
        middle_name = self.cleaned_data.get('middle_name')
        if middle_name:
            middle_name = middle_name.strip().title()
            if not re.match(r'^[a-zA-Z\s\-\']+$', middle_name):
                raise ValidationError("Middle name contains invalid characters.")
        return middle_name or ''

    def clean_mobile(self):
        mobile = self.cleaned_data.get('mobile')
        if not mobile:
            raise ValidationError("Mobile number is required.")

        # Remove spaces and special characters
        mobile = re.sub(r'[^\d+]', '', mobile)

        # Validate format (Nigerian format example - adjust for your country)
        if not re.match(r'^(\+234|0)[789]\d{9}$', mobile):
            raise ValidationError("Enter a valid mobile number (e.g., +2348012345678 or 08012345678).")

        # Check uniqueness
        existing = StaffModel.objects.filter(mobile=mobile)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError("This mobile number is already registered.")

        return mobile

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()

            # Check uniqueness
            existing = StaffModel.objects.filter(email__iexact=email)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError("This email is already registered.")

        return email

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = date.today()
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

            if dob >= today:
                raise ValidationError("Date of birth cannot be in the future.")

            if age < 16:
                raise ValidationError("Staff must be at least 16 years old.")

            if age > 80:
                raise ValidationError("Please verify the date of birth (age appears to be over 80).")

        return dob

    def clean_employment_date(self):
        emp_date = self.cleaned_data.get('employment_date')
        if emp_date:
            if emp_date > date.today():
                raise ValidationError("Employment date cannot be in the future.")

            # Check if too far in the past
            years_ago = date.today().year - emp_date.year
            if years_ago > 50:
                raise ValidationError("Employment date seems too far in the past.")

        return emp_date

    def clean_contract_start_date(self):
        start_date = self.cleaned_data.get('contract_start_date')
        if start_date:
            # Can be in future for upcoming contracts
            years_ago = abs(date.today().year - start_date.year)
            if years_ago > 10:
                raise ValidationError("Contract start date seems unrealistic.")

        return start_date

    def clean_contract_end_date(self):
        end_date = self.cleaned_data.get('contract_end_date')
        start_date = self.cleaned_data.get('contract_start_date')

        if end_date and start_date:
            if end_date <= start_date:
                raise ValidationError("Contract end date must be after start date.")

            # Check for reasonable contract length
            days_diff = (end_date - start_date).days
            if days_diff > 3650:  # 10 years
                raise ValidationError("Contract period seems too long (over 10 years).")

            if days_diff < 30:  # 1 month
                raise ValidationError("Contract period seems too short (less than 1 month).")

        return end_date

    def clean_position(self):
        position = self.cleaned_data.get('position')
        department = self.cleaned_data.get('department')

        if position and department:
            if position.department != department:
                raise ValidationError("Selected position does not belong to the selected department.")

        return position

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if image:
            # Check file size (2MB limit)
            if image.size > 2 * 1024 * 1024:
                raise ValidationError("Image file size should not exceed 2MB.")

            # Check file type
            allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif']
            if image.content_type not in allowed_types:
                raise ValidationError("Please upload a valid image file (JPEG, PNG, GIF).")

        return image

    def clean_cv(self):
        cv = self.cleaned_data.get('cv')
        if cv:
            # Check file size (5MB limit)
            if cv.size > 5 * 1024 * 1024:
                raise ValidationError("CV file size should not exceed 5MB.")

            # Check file type
            allowed_types = ['application/pdf', 'application/msword',
                             'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
            if cv.content_type not in allowed_types:
                raise ValidationError("Please upload a valid CV file (PDF, DOC, DOCX).")

        return cv


class StaffLeaveForm(forms.ModelForm):
    class Meta:
        model = StaffLeaveModel
        fields = ['staff', 'leave_type', 'start_date', 'end_date', 'applied_days', 'reason']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-control'}),
            'leave_type': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'applied_days': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['staff'].queryset = StaffModel.objects.filter(status='active')
        self.fields['staff'].empty_label = "Select Staff"

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if not start_date:
            raise ValidationError("Start date is required.")

        # Allow leave applications for today and future dates
        if start_date < date.today():
            raise ValidationError("Leave start date cannot be in the past.")

        return start_date

    def clean_end_date(self):
        end_date = self.cleaned_data.get('end_date')
        start_date = self.cleaned_data.get('start_date')

        if not end_date:
            raise ValidationError("End date is required.")

        if start_date and end_date <= start_date:
            raise ValidationError("End date must be after start date.")

        return end_date

    def clean_applied_days(self):
        applied_days = self.cleaned_data.get('applied_days')
        start_date = self.cleaned_data.get('start_date')
        end_date = self.cleaned_data.get('end_date')

        if applied_days and applied_days <= 0:
            raise ValidationError("Applied days must be greater than 0.")

        if start_date and end_date and applied_days:
            # Calculate actual working days
            actual_days = (end_date - start_date).days + 1

            if applied_days > actual_days:
                raise ValidationError(f"Applied days ({applied_days}) cannot be more than actual days ({actual_days}).")

            if applied_days > 365:
                raise ValidationError("Applied days cannot exceed 365 days.")

        return applied_days

    def clean(self):
        cleaned_data = super().clean()
        staff = cleaned_data.get('staff')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if staff and start_date and end_date:
            # Check for overlapping leave applications
            overlapping = StaffLeaveModel.objects.filter(
                staff=staff,
                start_date__lte=end_date,
                end_date__gte=start_date,
                status__in=['pending', 'approved']
            )

            if self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)

            if overlapping.exists():
                raise ValidationError("This staff has overlapping leave applications in the selected period.")

        return cleaned_data


class StaffDocumentForm(forms.ModelForm):
    class Meta:
        model = StaffDocumentModel
        fields = ['staff', 'title', 'document_type', 'document']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'document_type': forms.Select(attrs={'class': 'form-control'}),
            'document': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['staff'].queryset = StaffModel.objects.all()
        self.fields['staff'].empty_label = "Select Staff"

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if title:
            title = title.strip()
            if len(title) < 3:
                raise ValidationError("Document title must be at least 3 characters long.")

            if len(title) > 250:
                raise ValidationError("Document title is too long (max 250 characters).")

        return title

    def clean_document(self):
        document = self.cleaned_data.get('document')
        if not document:
            raise ValidationError("Document file is required.")

        # Check file size (10MB limit)
        if document.size > 10 * 1024 * 1024:
            raise ValidationError("Document file size should not exceed 10MB.")

        # Check file type
        allowed_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'image/jpeg', 'image/jpg', 'image/png'
        ]

        if document.content_type not in allowed_types:
            raise ValidationError("Please upload a valid document file (PDF, DOC, DOCX, JPG, PNG).")

        return document


class HODForm(forms.ModelForm):
    class Meta:
        model = HODModel
        fields = ['department', 'hod', 'deputy_hod', 'status', 'start_date', 'end_date']
        widgets = {
            'department': forms.Select(attrs={'class': 'form-control'}),
            'hod': forms.Select(attrs={'class': 'form-control'}),
            'deputy_hod': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].queryset = DepartmentModel.objects.all()
        self.fields['hod'].queryset = StaffModel.objects.filter(status='active')
        self.fields['deputy_hod'].queryset = StaffModel.objects.filter(status='active')

        self.fields['department'].empty_label = "Select Department"
        self.fields['hod'].empty_label = "Select HOD"
        self.fields['deputy_hod'].empty_label = "Select Deputy HOD"

    def clean(self):
        cleaned_data = super().clean()
        hod = cleaned_data.get('hod')
        deputy_hod = cleaned_data.get('deputy_hod')
        department = cleaned_data.get('department')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if hod and deputy_hod and hod == deputy_hod:
            raise ValidationError("HOD and Deputy HOD cannot be the same person.")

        if department and hod:
            if hod.department != department:
                raise ValidationError("HOD must be from the selected department.")

        if department and deputy_hod:
            if deputy_hod.department != department:
                raise ValidationError("Deputy HOD must be from the selected department.")

        if start_date and end_date:
            if end_date <= start_date:
                raise ValidationError("End date must be after start date.")

        return cleaned_data


class HRSettingForm(forms.ModelForm):
    class Meta:
        model = HRSettingModel
        fields = ['auto_generate_staff_id', 'staff_prefix', 'use_dept_prefix_for_id', 'allow_profile_edit']
        widgets = {
            'auto_generate_staff_id': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'staff_prefix': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '10'}),
            'use_dept_prefix_for_id': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_profile_edit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_staff_prefix(self):
        staff_prefix = self.cleaned_data.get('staff_prefix')
        if staff_prefix:
            staff_prefix = staff_prefix.upper().strip()

            if not re.match(r'^[A-Z0-9]+$', staff_prefix):
                raise ValidationError("Staff prefix must contain only letters and numbers.")

            if len(staff_prefix) < 2 or len(staff_prefix) > 10:
                raise ValidationError("Staff prefix must be between 2 and 10 characters.")

        return staff_prefix


class GroupForm(forms.ModelForm):
    """Form for creating and updating user permission groups."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    def clean_name(self):
        name = self.cleaned_data['name']
        qs = Group.objects.filter(name__iexact=name)

        # Exclude current instance when editing
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError("A Permission Group with this name already exists.")
        return name

    class Meta:
        model = Group
        fields = '__all__'

        