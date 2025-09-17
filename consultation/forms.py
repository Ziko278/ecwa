import re

from django.forms import ModelForm, Select, TextInput, DateInput, TimeInput, NumberInput, Textarea, CheckboxInput, \
    CheckboxSelectMultiple, ClearableFileInput, HiddenInput
from django.core.exceptions import ValidationError
from consultation.models import *
from django import forms


class ConsultationBlockForm(ModelForm):
    """Form for consultation blocks"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    class Meta:
        model = ConsultationBlockModel
        fields = '__all__'
        widgets = {
            'description': Textarea(attrs={
                'rows': 3,
                'placeholder': 'Enter block description...'
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip().lower()
            if len(name) < 2:
                raise ValidationError("Block name must be at least 2 characters long.")
        return name


class ConsultationRoomForm(ModelForm):
    """Form for consultation rooms"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'is_active':
                self.fields[field].widget.attrs.update({
                    'class': 'form-control',
                    'autocomplete': 'off'
                })

    class Meta:
        model = ConsultationRoomModel
        fields = '__all__'
        widgets = {
            'capacity': NumberInput(attrs={
                'min': '1',
                'max': '10',
                'placeholder': 'Number of doctors'
            }),
        }

    def clean_capacity(self):
        capacity = self.cleaned_data.get('capacity')
        if capacity and capacity < 1:
            raise ValidationError("Capacity must be at least 1.")
        return capacity


class SpecializationForm(ModelForm):
    """Form for medical specializations."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set a common class and autocomplete for all fields
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

        # Customize the group field's widget
        self.fields['group'].widget.attrs.update({
            'class': 'form-control select2'  # Use select2 for a better UI
        })

    class Meta:
        model = SpecializationModel
        fields = '__all__'
        widgets = {
            'code': TextInput(attrs={
                'placeholder': 'e.g., CAR for Cardiology',
                'maxlength': '10'
            }),
            'description': Textarea(attrs={
                'rows': 3,
                'placeholder': 'Enter specialization description...'
            }),
            'base_consultation_fee': NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),
        }

    def clean_base_consultation_fee(self):
        fee = self.cleaned_data.get('base_consultation_fee')
        if fee is not None and fee < 0:
            raise ValidationError("Consultation fee cannot be negative.")
        return fee

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Specialization name is required.")

        # Remove extra spaces and validate
        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Specialization name must be at least 2 characters long.")

        # Check for special characters (allow only letters, numbers, spaces, hyphens, and ampersands)
        if not re.match(r'^[a-zA-Z0-9\s\-&]+$', name):
            raise ValidationError("Specialization name contains invalid characters.")

        # Check uniqueness (case-insensitive)
        existing = SpecializationModel.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Specialization '{name}' already exists.")

        return name


class SpecializationGroupForm(ModelForm):
    """Form for medical specialization groups."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    class Meta:
        model = SpecializationGroupModel
        fields = ['name']
        widgets = {
            'name': TextInput(attrs={
                'placeholder': 'e.g., General Practice'
            }),

        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Group name is required.")

        # Strip extra spaces and ensure length
        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Group name must be at least 2 characters long.")

        existing = SpecializationGroupModel.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Specialization Group '{name}' already exists.")

        return name


class ConsultantForm(ModelForm):
    """Form for consultant doctors"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if not field in ['is_available_for_consultation']:
                self.fields[field].widget.attrs.update({
                    'class': 'form-control',
                    'autocomplete': 'off'
                })

        # Filter staff to only show doctors/medical staff
        try:
            from human_resource.models import StaffModel
            self.fields['staff'].queryset = StaffModel.objects.filter(
                is_active=True
            ).select_related('user')
        except Exception:
            pass

    class Meta:
        model = ConsultantModel
        fields = '__all__'
        widgets = {
            'default_consultation_duration': NumberInput(attrs={
                'min': '10',
                'max': '120',
                'placeholder': 'Minutes'
            }),
            'max_daily_patients': NumberInput(attrs={
                'min': '1',
                'max': '500',
                'placeholder': 'Max patients per day'
            }),
            'consultation_days': TextInput(attrs={
                'placeholder': 'e.g., mon,tue,wed,thu,fri'
            }),
            'consultation_start_time': TimeInput(attrs={
                'type': 'time'
            }),
            'consultation_end_time': TimeInput(attrs={
                'type': 'time'
            }),
            'is_available_for_consultation': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_consultation_days(self):
        days = self.cleaned_data.get('consultation_days', '')
        valid_days = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

        if days:
            day_list = [day.strip().lower() for day in days.split(',')]
            invalid_days = [day for day in day_list if day not in valid_days]

            if invalid_days:
                raise ValidationError(f"Invalid days: {', '.join(invalid_days)}. Use: {', '.join(valid_days)}")

        return days

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('consultation_start_time')
        end_time = cleaned_data.get('consultation_end_time')
        staff = cleaned_data.get('staff')
        specialization = cleaned_data.get('specialization')

        # --- Time validation ---
        if start_time and end_time:
            if start_time >= end_time:
                raise ValidationError("Start time must be before end time.")

        # --- Unique Staff and Specialization validation ---
        if staff and specialization:
            # Check if a consultant with this staff and specialization already exists
            queryset = ConsultantModel.objects.filter(
                staff=staff,
                specialization=specialization
            )

            # If updating an existing instance, exclude it from the uniqueness check
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                # Add error specifically to the 'staff' field
                self.add_error(
                    'staff',  # Target the 'staff' field
                    "This staff member is already assigned to this specialization as a consultant. "
                )

        return cleaned_data


class ConsultationFeeForm(ModelForm):
    """Form for consultation fees"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if not field in ['is_active']:
                self.fields[field].widget.attrs.update({
                    'class': 'form-control',
                    'autocomplete': 'off'
                })

    class Meta:
        model = ConsultationFeeModel
        fields = '__all__'
        widgets = {
            'amount': NumberInput(attrs={
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00'
            }),

            'validity_in_days': NumberInput(attrs={
                'min': '1'
            }),

            'is_active': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount < 0:
            raise ValidationError("Amount cannot be less than zero.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        specialization = cleaned_data.get('specialization')
        patient_category = cleaned_data.get('patient_category')
        insurance = cleaned_data.get('insurance')
        amount = cleaned_data.get('amount')

        # Validate amount is not less than zero (from clean_amount, but good to have a final check)
        if amount is not None and amount < 0:
            self.add_error('amount', "Amount cannot be less than zero.")

        # Rule 1: If patient_category is 'regular', insurance should not be selected
        if patient_category == 'regular' and insurance:
            self.add_error('insurance', "Insurance cannot be selected for 'Regular Patient' category.")

        # Rule 2: Ensure uniqueness based on patient_category logic
        if specialization and patient_category:
            queryset = ConsultationFeeModel.objects.filter(
                specialization=specialization,
                patient_category=patient_category,
            )

            if patient_category == 'regular':
                # For 'regular' patients, insurance must be null for uniqueness
                queryset = queryset.filter(insurance__isnull=True)
            else:
                # For 'insurance' patients, insurance must be selected and unique
                if not insurance:
                    self.add_error('insurance', "Insurance must be selected for 'Insurance Patient' category.")
                queryset = queryset.filter(insurance=insurance)

            # Exclude the current instance if it's an update
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                if patient_category == 'regular':
                    self.add_error(
                        None,  # Non-field error as it involves multiple fields
                        f"A consultation fee for '{specialization}' and 'Regular Patient' (without insurance) already exists."
                    )
                else:
                    self.add_error(
                        None,  # Non-field error as it involves multiple fields
                        f"A consultation fee for '{specialization}' with insurance '{insurance}' already exists."
                    )

        return cleaned_data

    def clean_validity_in_days(self):
        days = self.cleaned_data.get('validity_in_days')
        if days is not None and days < 1:
            raise ValidationError("Validity period must be at least 1 day.")
        return days


class PatientQueueForm(ModelForm):
    """Form for patient queue management"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

        # Filter active consultants
        try:
            self.fields['consultant'].queryset = ConsultantModel.objects.filter(
                is_available_for_consultation=True
            ).select_related('staff', 'specialization')
        except Exception:
            pass

    class Meta:
        model = PatientQueueModel
        fields = ['patient', 'payment', 'consultant', 'is_emergency', 'priority_level', 'notes']
        widgets = {
            'priority_level': NumberInput(attrs={
                'min': '0',
                'max': '2',
                'placeholder': '0=Normal, 1=High, 2=Emergency'
            }),
            'is_emergency': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notes': Textarea(attrs={
                'rows': 3,
                'placeholder': 'Additional notes...'
            }),
        }

    def clean_priority_level(self):
        priority = self.cleaned_data.get('priority_level')
        if priority is not None and priority not in [0, 1, 2]:
            raise ValidationError("Priority level must be 0, 1, or 2.")
        return priority


class PatientVitalsForm(ModelForm):
    """Form for patient vitals"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    class Meta:
        model = PatientVitalsModel
        fields = [
            'temperature', 'blood_pressure_systolic', 'blood_pressure_diastolic',
            'pulse_rate', 'respiratory_rate', 'oxygen_saturation', 'extra_note',
            'height', 'weight', 'general_appearance', 'chief_complaint', 'notes'
        ]
        widgets = {
            'temperature': NumberInput(attrs={
                'step': '0.1',
                'min': '30',
                'max': '45',
                'placeholder': '°C'
            }),
            'blood_pressure_systolic': NumberInput(attrs={
                'min': '60',
                'max': '250',
                'placeholder': 'Systolic'
            }),
            'blood_pressure_diastolic': NumberInput(attrs={
                'min': '40',
                'max': '150',
                'placeholder': 'Diastolic'
            }),
            'pulse_rate': NumberInput(attrs={
                'min': '40',
                'max': '200',
                'placeholder': 'BPM'
            }),
            'respiratory_rate': NumberInput(attrs={
                'min': '8',
                'max': '50',
                'placeholder': 'per minute'
            }),
            'oxygen_saturation': NumberInput(attrs={
                'min': '30',
                'max': '100',
                'placeholder': 'SpO2 %'
            }),
            'height': NumberInput(attrs={
                'step': '0.01',
                'min': '50',
                'max': '250',
                'placeholder': 'cm'
            }),
            'weight': NumberInput(attrs={
                'step': '0.01',
                'min': '1',
                'max': '300',
                'placeholder': 'kg'
            }),
            'general_appearance': Textarea(attrs={
                'rows': 2,
                'placeholder': 'General appearance observations...'
            }),
            'chief_complaint': Textarea(attrs={
                'rows': 3,
                'placeholder': 'What is the patient complaining of?'
            }),
            'notes': Textarea(attrs={
                'rows': 2,
                'placeholder': 'Additional notes...'
            }),
        }

    def clean_blood_pressure_systolic(self):
        systolic = self.cleaned_data.get('blood_pressure_systolic')
        if systolic and (systolic < 60 or systolic > 250):
            raise ValidationError("Systolic BP must be between 60-250 mmHg.")
        return systolic

    def clean_blood_pressure_diastolic(self):
        diastolic = self.cleaned_data.get('blood_pressure_diastolic')
        if diastolic and (diastolic < 10 or diastolic > 300):
            raise ValidationError("Diastolic BP must be between 40-150 mmHg.")
        return diastolic

    def clean(self):
        cleaned_data = super().clean()
        systolic = cleaned_data.get('blood_pressure_systolic')
        diastolic = cleaned_data.get('blood_pressure_diastolic')

        if systolic and diastolic:
            if diastolic >= systolic:
                raise ValidationError("Diastolic BP must be lower than Systolic BP.")

        return cleaned_data


class ConsultationSessionForm(ModelForm):
    """Form for consultation sessions"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

        # Show diagnosis fields only for NEW consultations
        if self.instance and self.instance.consultation_type == 'follow_up':
            self.fields['primary_diagnosis'].widget = HiddenInput()
            self.fields['other_diagnosis_text'].widget = HiddenInput()

    class Meta:
        model = ConsultationSessionModel
        fields = [
            'assessment', 'chief_complaint', 'diagnosis',
            'primary_diagnosis',
            'other_diagnosis_text',
            'case_status',
            'voice_recording'
        ]
        widgets = {
            'consultation_notes': Textarea(attrs={
                'rows': 8,
                'placeholder': 'Comprehensive consultation notes (chief complaint, examination, assessment, treatment plan, etc.)...',
                'class': 'tinymce-editor'  # If using TinyMCE
            }),
            'primary_diagnosis': Select(attrs={
                'placeholder': 'Select primary diagnosis...'
            }),
            'other_diagnosis_text': TextInput(attrs={
                'placeholder': 'Specify other diagnosis if not in list above...',
                'maxlength': 500
            }),
            'case_status': Select(attrs={
                'help_text': 'Mark as completed to make next visit a NEW consultation'
            }),
            'voice_recording': ClearableFileInput(attrs={
                'accept': 'audio/*',
                'help_text': 'Optional voice note (max 5 minutes)'
            }),
        }

    def clean_consultation_notes(self):
        notes = self.cleaned_data.get('consultation_notes')
        if not notes or len(notes.strip()) < 10:
            raise ValidationError("Consultation notes must be at least 10 characters long.")
        return notes

    def clean_primary_diagnosis(self):
        """Validate primary diagnosis for NEW consultations"""
        primary_diagnosis = self.cleaned_data.get('primary_diagnosis')
        other_diagnosis_text = self.cleaned_data.get('other_diagnosis_text')

        # Only validate for NEW consultations
        if (self.instance and self.instance.consultation_type == 'new' and
                not primary_diagnosis and not other_diagnosis_text):
            raise ValidationError("Primary diagnosis is required for new consultations.")

        return primary_diagnosis

    def clean_other_diagnosis_text(self):
        other_diagnosis = self.cleaned_data.get('other_diagnosis_text')
        if other_diagnosis and len(other_diagnosis.strip()) < 3:
            raise ValidationError("Other diagnosis must be at least 3 characters long.")
        return other_diagnosis

    def clean_voice_recording(self):
        """Validate voice recording file"""
        voice_file = self.cleaned_data.get('voice_recording')
        if voice_file:
            # Check file size (max 10MB)
            if voice_file.size > 10 * 1024 * 1024:
                raise ValidationError("Voice recording must be less than 10MB.")

            # Check file type
            if not voice_file.name.lower().endswith(('.mp3', '.wav', '.m4a', '.ogg')):
                raise ValidationError("Voice recording must be an audio file (mp3, wav, m4a, ogg).")

        return voice_file


class DoctorScheduleForm(ModelForm):
    """Form for doctor schedules"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    class Meta:
        model = DoctorScheduleModel
        fields = '__all__'
        widgets = {
            'date': DateInput(attrs={
                'type': 'date'
            }),
            'start_time': TimeInput(attrs={
                'type': 'time'
            }),
            'end_time': TimeInput(attrs={
                'type': 'time'
            }),
            'max_patients': NumberInput(attrs={
                'min': '1',
                'max': '500',
                'placeholder': 'Max patients'
            }),
            'current_bookings': NumberInput(attrs={
                'min': '0',
                'readonly': True
            }),
            'is_available': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'notes': Textarea(attrs={
                'rows': 2,
                'placeholder': 'Schedule notes...'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        date = cleaned_data.get('date')

        if start_time and end_time:
            if start_time >= end_time:
                raise ValidationError("Start time must be before end time.")

        if date:
            from datetime import date as dt_date
            if date < dt_date.today():
                raise ValidationError("Cannot create schedule for past dates.")

        return cleaned_data


class ConsultationSettingsForm(ModelForm):
    """Form for consultation settings"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    class Meta:
        model = ConsultationSettingsModel
        fields = '__all__'
        widgets = {
            'auto_assign_queue_numbers': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'max_queue_size_per_doctor': NumberInput(attrs={
                'min': '10',
                'max': '200',
                'placeholder': 'Max queue size'
            }),
            'default_consultation_duration': NumberInput(attrs={
                'min': '5',
                'max': '120',
                'placeholder': 'Minutes'
            }),
            'vitals_timeout_minutes': NumberInput(attrs={
                'min': '10',
                'max': '120',
                'placeholder': 'Minutes'
            }),
            'consultation_timeout_hours': NumberInput(attrs={
                'min': '1',
                'max': '12',
                'placeholder': 'Hours'
            }),
            'default_insurance_coverage_percent': NumberInput(attrs={
                'min': '0',
                'max': '100',
                'placeholder': 'Percentage'
            }),
            'send_queue_notifications': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'send_vitals_reminders': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_default_insurance_coverage_percent(self):
        percent = self.cleaned_data.get('default_insurance_coverage_percent')
        if percent is not None and (percent < 0 or percent > 100):
            raise ValidationError("Coverage percentage must be between 0-100%.")
        return percent


# Quick forms for status updates
class QueueStatusUpdateForm(forms.Form):
    """Quick form for updating queue status"""
    queue_id = forms.IntegerField(widget=forms.HiddenInput())
    status = forms.ChoiceField(
        choices=PatientQueueModel.QUEUE_STATUS,
        widget=Select(attrs={'class': 'form-control'})
    )
    notes = forms.CharField(
        required=False,
        widget=Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Status update notes...'
        })
    )


class ConsultantStatusForm(forms.Form):
    """Quick form for updating consultant availability"""
    consultant_id = forms.IntegerField(widget=forms.HiddenInput())
    is_available_for_consultation = forms.BooleanField(
        required=False,
        widget=CheckboxInput(attrs={'class': 'form-check-input'})
    )
    notes = forms.CharField(
        required=False,
        widget=TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Availability notes...'
        })
    )


class AllergyForm(forms.ModelForm):
    class Meta:
        model = Allergy
        fields = ['details']
        widgets = {
            'details': forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}),
        }
