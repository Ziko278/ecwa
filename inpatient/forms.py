from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone

from consultation.models import ConsultationSessionModel
from human_resource.models import DepartmentModel, StaffProfileModel
from pharmacy.models import DrugOrderModel
from .models import (
    InpatientSettings, Ward, Bed, SurgeryType, SurgeryDrug, SurgeryLab, SurgeryScan, Admission, Surgery, AdmissionType,
 AdmissionTask
)


class InpatientSettingsForm(forms.ModelForm):
    class Meta:
        model = InpatientSettings
        fields = [
            'bed_billing_for_admission', 'bed_billing_for_surgery',
            'admission_billing_type', 'admission_amount',
            'surgery_billing_type', 'surgery_amount', 'bed_daily_cost',
            'compile_surgery_drugs', 'compile_surgery_labs', 'compile_surgery_scans',
            'charge_admission_fee', 'admission_fee_amount', 'default_max_debt'
        ]
        widgets = {
            'bed_billing_for_admission': forms.Select(attrs={'class': 'form-control'}),
            'bed_billing_for_surgery': forms.Select(attrs={'class': 'form-control'}),
            'admission_billing_type': forms.Select(attrs={'class': 'form-control'}),
            'admission_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'surgery_billing_type': forms.Select(attrs={'class': 'form-control'}),
            'surgery_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'bed_daily_cost': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'charge_admission_fee': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'admission_fee_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'default_max_debt': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'compile_admission_drugs': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compile_admission_labs': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compile_admission_scans': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compile_surgery_drugs': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compile_surgery_labs': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'compile_surgery_scans': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class WardForm(forms.ModelForm):
    class Meta:
        model = Ward
        fields = [
            'name', 'description', 'ward_type', 'capacity',
            'location', 'floor', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter ward name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Ward description (optional)'
            }),
            'ward_type': forms.Select(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'Number of beds'
            }),
            'location': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ward location (optional)'
            }),
            'floor': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Floor number (optional)'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity')
        if capacity and capacity < 1:
            raise ValidationError("Ward capacity must be at least 1")
        return capacity


class BedForm(forms.ModelForm):
    class Meta:
        model = Bed
        fields = [
            'ward', 'bed_number', 'bed_type', 'status',
            'daily_rate', 'features', 'is_active'
        ]
        widgets = {
            'ward': forms.Select(attrs={'class': 'form-control'}),
            'bed_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., B001, A-12'
            }),
            'bed_type': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'daily_rate': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Override rate (optional)'
            }),
            'features': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Special features (optional)'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ward'].queryset = Ward.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        ward = cleaned_data.get('ward')
        bed_number = cleaned_data.get('bed_number')

        if ward and bed_number:
            # Check for duplicate bed number in the same ward
            existing_bed = Bed.objects.filter(ward=ward, bed_number=bed_number)
            if self.instance.pk:
                existing_bed = existing_bed.exclude(pk=self.instance.pk)

            if existing_bed.exists():
                raise ValidationError(f"Bed {bed_number} already exists in {ward.name}")

        return cleaned_data


class SurgeryTypeForm(forms.ModelForm):
    class Meta:
        model = SurgeryType
        fields = [
            'name', 'description', 'category', 'base_surgeon_fee',
            'base_anesthesia_fee', 'base_facility_fee', 'estimated_duration_hours',
            'requires_icu', 'typical_stay_days', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Surgery name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Surgery description (optional)'
            }),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'base_surgeon_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'base_anesthesia_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'base_facility_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'estimated_duration_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.25',
                'min': '0',
                'placeholder': 'e.g., 2.5'
            }),
            'requires_icu': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'typical_stay_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': 'Days (optional)'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AdmissionForm(forms.ModelForm):
    class Meta:
        model = Admission
        fields = [
            'patient', 'admission_type', 'chief_complaint',
            'admission_diagnosis', 'bed', 'expected_discharge_date',
            'attending_doctor', 'admission_notes'
        ]
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control'}),
            'admission_type': forms.Select(attrs={'class': 'form-control'}),
            'chief_complaint': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Patient\'s main complaint'
            }),
            'admission_diagnosis': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Admission diagnosis'
            }),
            'bed': forms.Select(attrs={'class': 'form-control'}),
            'expected_discharge_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'attending_doctor': forms.Select(attrs={'class': 'form-control'}),
            'admission_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Additional notes (optional)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show available beds
        self.fields['bed'].queryset = Bed.objects.filter(
            status='available',
            is_active=True,
            ward__is_active=True
        )
        # Only show active staff for attending doctor
        self.fields['attending_doctor'].queryset = User.objects.filter(
            is_active=True
        ).order_by('first_name', 'last_name')

    def clean(self):
        cleaned_data = super().clean()
        bed = cleaned_data.get('bed')
        expected_discharge = cleaned_data.get('expected_discharge_date')

        # Validate bed availability
        if bed and bed.status != 'available':
            raise ValidationError(f"Bed {bed} is not available")

        # Validate expected discharge date
        if expected_discharge and expected_discharge <= timezone.now().date():
            raise ValidationError("Expected discharge date must be in the future")

        return cleaned_data


class AdmissionUpdateForm(forms.ModelForm):
    class Meta:
        model = Admission
        fields = [
            'status', 'actual_discharge_date', 'discharge_notes',
            'attending_doctor', 'admission_notes'
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'actual_discharge_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'discharge_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Discharge notes and instructions'
            }),
            'attending_doctor': forms.Select(attrs={'class': 'form-control'}),
            'admission_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Additional notes'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['attending_doctor'].queryset = User.objects.filter(
            is_active=True
        ).order_by('first_name', 'last_name')

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        actual_discharge_date = cleaned_data.get('actual_discharge_date')
        discharge_notes = cleaned_data.get('discharge_notes')

        # Require discharge date and notes for discharged patients
        if status == 'discharged':
            if not actual_discharge_date:
                raise ValidationError("Actual discharge date is required for discharged patients")
            if not discharge_notes:
                raise ValidationError("Discharge notes are required for discharged patients")

        # Validate discharge date is not in future
        if actual_discharge_date and actual_discharge_date > timezone.now():
            raise ValidationError("Actual discharge date cannot be in the future")

        return cleaned_data


class UserFullNameModelChoiceField(forms.ModelChoiceField):
    """A ModelChoiceField that displays the user's full name from their staff profile."""

    def label_from_instance(self, obj):
        # obj is a User instance
        try:
            # Use the relationship provided to get the full name from the StaffModel's __str__ method
            if hasattr(obj, 'user_staff_profile') and obj.user_staff_profile.staff:
                return str(obj.user_staff_profile.staff)
        except (StaffProfileModel.DoesNotExist, AttributeError):
            # Fallback if profile or staff link is broken
            pass
        # Final fallback to username if no full name is found
        return obj.username


class SurgeryForm(forms.ModelForm):
    # This new field will be visible to the user for searching
    surgery_type_search = forms.CharField(
        label="Type of Surgery",
        required=True,
        widget=forms.TextInput(
            attrs={'class': 'form-control', 'placeholder': 'Search for a surgery type...', 'autocomplete': 'off'}),
    )

    # Explicitly define surgeon fields to use the custom field class
    primary_surgeon = UserFullNameModelChoiceField(
        queryset=User.objects.none(), required=False,
        widget=forms.Select(attrs={'class': 'form-control'}), label="Primary Surgeon"
    )
    assistant_surgeon = UserFullNameModelChoiceField(
        queryset=User.objects.none(), required=False,
        widget=forms.Select(attrs={'class': 'form-control'}), label="Assistant Surgeon"
    )
    anesthesiologist = UserFullNameModelChoiceField(
        queryset=User.objects.none(), required=False,
        widget=forms.Select(attrs={'class': 'form-control'}), label="Anesthesiologist"
    )

    class Meta:
        model = Surgery
        # Remove 'admission' from the fields list
        # Add 'surgery_type_search' to the beginning of the list to control its position
        fields = [
            'surgery_type_search', 'patient', 'surgery_type', 'scheduled_date',
            'primary_surgeon', 'assistant_surgeon', 'anesthesiologist',
            'pre_op_diagnosis', 'custom_surgeon_fee', 'custom_anesthesia_fee',
            'custom_facility_fee'
        ]
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control'}),
            # The actual model field is now hidden, it will be populated by JavaScript
            'surgery_type': forms.HiddenInput(),
            'scheduled_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            # These are now defined above as custom fields, so they can be removed from here
            # 'primary_surgeon': forms.Select(attrs={'class': 'form-control'}),
            # 'assistant_surgeon': forms.Select(attrs={'class': 'form-control'}),
            # 'anesthesiologist': forms.Select(attrs={'class': 'form-control'}),
            'pre_op_diagnosis': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Pre-operative diagnosis'
            }),
            # Add 'readonly' attribute to fee fields
            'custom_surgeon_fee': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0',
                'placeholder': 'Auto-filled from surgery type', 'readonly': True
            }),
            'custom_anesthesia_fee': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0',
                'placeholder': 'Auto-filled from surgery type', 'readonly': True
            }),
            'custom_facility_fee': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0',
                'placeholder': 'Auto-filled from surgery type', 'readonly': True
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # This line caused the error and has been removed.
        # self.fields.move_to_end('surgery_type_search', last=False)
        self.fields['surgery_type'].required = False

        # Filter staff to only those in the 'Consultation' department
        try:
            consultation_dept = DepartmentModel.objects.get(name__iexact="Consultation")
            # Get User IDs from StaffModel -> StaffProfileModel -> User
            staff_user_ids = consultation_dept.department_staffs.values_list('staff_profile__user_id', flat=True)
            # Optimize query with select_related to prevent N+1 issues when rendering names
            staff_qs = User.objects.filter(pk__in=staff_user_ids, is_active=True).select_related(
                'user_staff_profile__staff'
            ).order_by('user_staff_profile__staff__first_name', 'user_staff_profile__staff__last_name')
        except DepartmentModel.DoesNotExist:
            staff_qs = User.objects.none()

        self.fields['primary_surgeon'].queryset = staff_qs
        self.fields['assistant_surgeon'].queryset = staff_qs
        self.fields['anesthesiologist'].queryset = staff_qs

    def clean(self):
        cleaned_data = super().clean()
        scheduled_date = cleaned_data.get('scheduled_date')
        primary_surgeon = cleaned_data.get('primary_surgeon')
        assistant_surgeon = cleaned_data.get('assistant_surgeon')

        # Check if surgery_type was selected via JavaScript
        if not cleaned_data.get('surgery_type'):
            self.add_error('surgery_type_search', 'You must search for and select a valid surgery type.')

        # Validate scheduled date is in future
        if scheduled_date and scheduled_date <= timezone.now():
            self.add_error('scheduled_date', "Surgery must be scheduled in the future")

        # Validate surgeon assignments
        if primary_surgeon and assistant_surgeon and primary_surgeon == assistant_surgeon:
            self.add_error('assistant_surgeon', "Primary surgeon and assistant surgeon cannot be the same person")

        return cleaned_data


class SurgeryUpdateForm(forms.ModelForm):
    # Apply the same custom field and filtering logic to the update form
    primary_surgeon = UserFullNameModelChoiceField(
        queryset=User.objects.none(), required=False,
        widget=forms.Select(attrs={'class': 'form-control'}), label="Primary Surgeon"
    )
    assistant_surgeon = UserFullNameModelChoiceField(
        queryset=User.objects.none(), required=False,
        widget=forms.Select(attrs={'class': 'form-control'}), label="Assistant Surgeon"
    )
    anesthesiologist = UserFullNameModelChoiceField(
        queryset=User.objects.none(), required=False,
        widget=forms.Select(attrs={'class': 'form-control'}), label="Anesthesiologist"
    )

    class Meta:
        model = Surgery
        fields = [
            'status', 'primary_surgeon', 'assistant_surgeon', 'anesthesiologist',
            'actual_start_time', 'actual_end_time',
            'post_op_diagnosis', 'procedure_notes', 'complications'
        ]
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'actual_start_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'actual_end_time': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'post_op_diagnosis': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Post-operative diagnosis'
            }),
            'procedure_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Procedure notes and findings'
            }),
            'complications': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any complications (if none, leave blank)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try:
            consultation_dept = DepartmentModel.objects.get(name__iexact="Consultation")
            staff_user_ids = consultation_dept.department_staffs.values_list('staff_profile__user_id', flat=True)
            staff_qs = User.objects.filter(pk__in=staff_user_ids, is_active=True).select_related(
                'user_staff_profile__staff'
            ).order_by('user_staff_profile__staff__first_name', 'user_staff_profile__staff__last_name')
        except DepartmentModel.DoesNotExist:
            staff_qs = User.objects.none()

        self.fields['primary_surgeon'].queryset = staff_qs
        self.fields['assistant_surgeon'].queryset = staff_qs
        self.fields['anesthesiologist'].queryset = staff_qs

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        actual_start_time = cleaned_data.get('actual_start_time')
        actual_end_time = cleaned_data.get('actual_end_time')
        post_op_diagnosis = cleaned_data.get('post_op_diagnosis')
        procedure_notes = cleaned_data.get('procedure_notes')
        primary_surgeon = cleaned_data.get('primary_surgeon')
        assistant_surgeon = cleaned_data.get('assistant_surgeon')

        if status == 'completed':
            if not actual_start_time:
                self.add_error('actual_start_time', "Start time is required for completed surgeries")
            if not actual_end_time:
                self.add_error('actual_end_time', "End time is required for completed surgeries")
            if not post_op_diagnosis:
                self.add_error('post_op_diagnosis', "Post-operative diagnosis is required for completed surgeries")
            if not procedure_notes:
                self.add_error('procedure_notes', "Procedure notes are required for completed surgeries")

        if actual_start_time and actual_end_time:
            if actual_end_time <= actual_start_time:
                self.add_error('actual_end_time', "End time must be after start time")

        now = timezone.now()
        if actual_start_time and actual_start_time > now:
            self.add_error('actual_start_time', "Start time cannot be in the future")
        if actual_end_time and actual_end_time > now:
            self.add_error('actual_end_time', "End time cannot be in the future")

        if primary_surgeon and assistant_surgeon and primary_surgeon == assistant_surgeon:
            self.add_error('assistant_surgeon', "Primary surgeon and assistant surgeon cannot be the same person")

        return cleaned_data



class SurgeryDrugForm(forms.ModelForm):
    class Meta:
        model = SurgeryDrug
        fields = ['surgery', 'drug', 'quantity', 'is_optional', 'timing']
        widgets = {
            'surgery': forms.Select(attrs={'class': 'form-control'}),
            'drug': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'is_optional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'timing': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Pre-op, Post-op'
            }),
        }


class SurgeryLabForm(forms.ModelForm):
    class Meta:
        model = SurgeryLab
        fields = ['surgery', 'lab', 'is_optional', 'timing']
        widgets = {
            'surgery': forms.Select(attrs={'class': 'form-control'}),
            'lab': forms.Select(attrs={'class': 'form-control'}),
            'is_optional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'timing': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Pre-op, Day 1'
            }),
        }


class SurgeryScanForm(forms.ModelForm):
    class Meta:
        model = SurgeryScan
        fields = ['surgery', 'scan', 'is_optional', 'timing']
        widgets = {
            'surgery': forms.Select(attrs={'class': 'form-control'}),
            'scan': forms.Select(attrs={'class': 'form-control'}),
            'is_optional': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'timing': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Intra-op, Follow-up'
            }),
        }


# ============================================
# NEW FORMS FOR ADMISSION TYPES, WARD ROUNDS, AND TASKS
# ============================================

class AdmissionTypeForm(forms.ModelForm):
    """Form for creating/editing admission types"""

    class Meta:
        model = AdmissionType
        fields = [
            'name', 'description', 'bed_daily_fee', 'consultation_fee',
            'consultation_fee_duration_days', 'requires_deposit',
            'minimum_deposit_amount', 'max_debt_allowed', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., General Ward, ICU, Private Room'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description of this admission type (optional)'
            }),
            'bed_daily_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Daily bed charge'
            }),
            'consultation_fee': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Fee per ward round'
            }),
            'consultation_fee_duration_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'placeholder': 'How many days this fee covers'
            }),
            'requires_deposit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'minimum_deposit_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Minimum deposit required'
            }),
            'max_debt_allowed': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': 'Maximum debt before blocking services'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class WardRoundForm(forms.ModelForm):
    class Meta:
        model = ConsultationSessionModel  # Changed from WardRound
        fields = [
            'admission',           # Keep this
            'chief_complaint',     # Already exists in ConsultationSessionModel
            'assessment',          # Already exists
            'diagnosis',           # Use this instead of 'plan'
        ]
        widgets = {
            'admission': forms.Select(attrs={'class': 'form-control'}),
            'chief_complaint': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Patient\'s current complaints'
            }),
            'assessment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Clinical assessment and findings'
            }),
            'diagnosis': forms.Textarea(attrs={  # Changed from 'plan'
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Diagnosis and treatment plan'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active admissions
        self.fields['admission'].queryset = Admission.objects.filter(
            status='active'
        ).select_related('patient', 'bed__ward')


class AdmissionTaskForm(forms.ModelForm):
    """Form for creating/editing admission tasks"""

    class Meta:
        model = AdmissionTask
        fields = [
            'admission', 'task_type', 'drug_order', 'description',
            'scheduled_datetime', 'assigned_to', 'priority', 'notes'
        ]
        widgets = {
            'admission': forms.Select(attrs={'class': 'form-control'}),
            'task_type': forms.Select(attrs={'class': 'form-control'}),
            'drug_order': forms.Select(attrs={
                'class': 'form-control',
                'required': False
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'What needs to be done?'
            }),
            'scheduled_datetime': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'assigned_to': forms.Select(attrs={'class': 'form-control'}),
            'priority': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional instructions (optional)'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only show active admissions
        self.fields['admission'].queryset = Admission.objects.filter(
            status='active'
        ).select_related('patient')

        # Only show pending drug orders for the admission (if admission is set)
        if self.instance and self.instance.admission:
            self.fields['drug_order'].queryset = DrugOrderModel.objects.filter(
                admission=self.instance.admission,
                status__in=['pending', 'paid']
            ).select_related('drug')
        else:
            self.fields['drug_order'].queryset = DrugOrderModel.objects.none()

        # Only show active staff for assignment
        self.fields['assigned_to'].queryset = User.objects.filter(
            is_active=True
        ).order_by('first_name', 'last_name')

        # Make drug_order optional
        self.fields['drug_order'].required = False


class AdmissionDepositForm(forms.Form):
    """Form for receiving admission deposit payments"""
    deposit_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Enter deposit amount'
        }),
        label='Deposit Amount'
    )
    payment_method = forms.ChoiceField(
        choices=[
            ('cash', 'Cash'),
            ('card', 'Card'),
            ('transfer', 'Bank Transfer'),
            ('pos', 'POS'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Payment Method'
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Additional notes (optional)'
        }),
        label='Notes'
    )


class DischargeForm(forms.ModelForm):
    """Form for discharging a patient"""

    class Meta:
        model = Admission
        fields = ['actual_discharge_date', 'discharge_notes']
        widgets = {
            'actual_discharge_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local',
                'value': timezone.now().strftime('%Y-%m-%dT%H:%M')  # Default to now
            }),
            'discharge_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 5,
                'placeholder': 'Discharge summary, instructions, medications, follow-up appointments, etc.'
            }),
        }

    def clean_actual_discharge_date(self):
        discharge_date = self.cleaned_data.get('actual_discharge_date')

        # Cannot discharge in the future
        if discharge_date and discharge_date > timezone.now():
            raise ValidationError("Discharge date cannot be in the future")

        # Cannot discharge before admission
        if discharge_date and self.instance.admission_date:
            if discharge_date < self.instance.admission_date:
                raise ValidationError("Discharge date cannot be before admission date")

        return discharge_date

    def clean_discharge_notes(self):
        notes = self.cleaned_data.get('discharge_notes')
        if not notes or notes.strip() == '':
            raise ValidationError("Discharge notes are required")
        return notes
