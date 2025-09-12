import datetime
import json

from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from datetime import date
import re

from django.utils import timezone

from .models import *


class ScanCategoryForm(forms.ModelForm):
    class Meta:
        model = ScanCategoryModel
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category Name'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CODE', 'maxlength': '10'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Category name is required.")

        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Category name must be at least 2 characters long.")

        if not re.match(r'^[a-zA-Z0-9\s\-&]+$', name):
            raise ValidationError("Category name contains invalid characters.")

        qs = ScanCategoryModel.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError(f"Category '{name}' already exists.")
        return name

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.strip().upper()
            if not re.match(r'^[A-Z0-9]+$', code):
                raise ValidationError("Code must contain only letters and numbers.")

            qs = ScanCategoryModel.objects.filter(code=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError(f"Code '{code}' already exists.")
        return code


class ScanTemplateForm(forms.ModelForm):
    class Meta:
        model = ScanTemplateModel
        fields = ['name', 'code', 'category', 'scan_parameters', 'expected_images',
                  'price', 'estimated_duration',
                  'fasting_required', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'scan_parameters': forms.Textarea(attrs={'class': 'form-control', 'rows': 8}),
            'expected_images': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'estimated_duration': forms.TextInput(attrs={'class': 'form-control'}),
            'fasting_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise ValidationError("Template name is required.")
        qs = ScanTemplateModel.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Template name already exists.")
        return name

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        if code:
            qs = ScanTemplateModel.objects.filter(code=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Template code already exists.")
        return code

    def clean_scan_parameters(self):
        """Validate JSON format"""
        import json
        data = self.cleaned_data.get('scan_parameters')
        if data:
            try:
                if isinstance(data, str):
                    json.loads(data)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for scan parameters.")
        return data

    def clean_expected_images(self):
        """Validate expected images JSON format"""
        import json
        data = self.cleaned_data.get('expected_images')
        if data:
            try:
                if isinstance(data, str):
                    parsed = json.loads(data)
                    if not isinstance(parsed, list):
                        raise ValidationError("Expected images must be a list.")
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for expected images.")
        return data


class ScanOrderForm(forms.ModelForm):
    """
    Minimal form used on the "Order New Scan" page.
    - DOES NOT include `template` or `patient` (these are set in the view).
    - Validates only user-entered fields and provides helpful widgets.
    """
    class Meta:
        model = ScanOrderModel
        fields = [
            'clinical_indication',
            'special_instructions',
            'scheduled_date',
        ]
        widgets = {
            'clinical_indication': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'special_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'scheduled_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
        }
        labels = {
            'clinical_indication': 'Clinical Indication',
            'special_instructions': 'Special Instructions',
            'scheduled_date': 'Scheduled Date & Time (optional)',
        }

    def clean_scheduled_date(self):
        sd = self.cleaned_data.get('scheduled_date')
        if sd:
            now = timezone.now()
            # Allow small clock skew
            earliest_allowed = now - datetime.timedelta(minutes=5)
            if sd < earliest_allowed:
                raise ValidationError("Scheduled date/time cannot be in the past.")
            # Prevent scheduling ridiculously far in the future
            latest_allowed = now + datetime.timedelta(days=365)
            if sd > latest_allowed:
                raise ValidationError("Scheduled date/time cannot be more than 365 days from now.")
        return sd

    def clean(self):
        """
        Cross-field validation:
         - Must provide at least one of clinical_indication, special_instructions, or scheduled_date.
         - Enforce reasonable max lengths for free-text fields.
         - (Other business rules can be added here.)
        """
        cleaned = super().clean()
        clinical = (cleaned.get('clinical_indication') or '').strip()
        special = (cleaned.get('special_instructions') or '').strip()
        scheduled = cleaned.get('scheduled_date')

        # Require at least one meaningful field to avoid empty orders
        if not clinical and not special and not scheduled:
            raise ValidationError(
                "Please provide at least one of: clinical indication, special instructions, or a scheduled date/time."
            )

        # Reasonable max lengths to protect DB / UI
        MAX_LEN = 2000
        if clinical and len(clinical) > MAX_LEN:
            self.add_error('clinical_indication', f'Clinical indication cannot exceed {MAX_LEN} characters.')

        if special and len(special) > MAX_LEN:
            self.add_error('special_instructions', f'Special instructions cannot exceed {MAX_LEN} characters.')

        return cleaned


class ScanResultForm(forms.ModelForm):
    """
    The CORRECT, focused form for creating or editing a report's content.
    It does NOT include fields that should be set automatically by the system.
    """

    class Meta:
        model = ScanResultModel
        # ✅ The explicit, focused list of fields a user should edit.
        fields = [
            'findings',
            'impression',
            'recommendations',
            'technician_comments',
            'status',
            'report_date',
            'measured_values',
            'radiology_report_image',
        ]

        widgets = {
            'findings': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'impression': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'recommendations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'technician_comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'report_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'measured_values': forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
            'radiology_report_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

    def clean_report_date(self):
        """Ensure the report date is not in the future."""
        report_date = self.cleaned_data.get('report_date')
        if report_date and report_date > timezone.now():
            raise ValidationError("The report date cannot be in the future.")

        # NOTE: The check for `report_date` vs `performed_at` is done in the view,
        # where we have access to the order's `scan_completed_at`.
        return report_date

    def clean_measured_values(self):
        """Validate the JSON format for measured values."""
        data = self.cleaned_data.get('measured_values')
        if not data:
            return {}  # Default to an empty dictionary
        try:
            if isinstance(data, str):
                return json.loads(data)
            return data
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON format for measured values.")

    def clean(self):
        """
        Perform cross-field validation for the report content.
        """
        cleaned_data = super().clean()

        status = cleaned_data.get('status')
        impression = cleaned_data.get('impression')

        # Workflow validation: If the report is being finalized, it must have a conclusion.
        if status == 'finalized' and not impression:
            self.add_error('impression', "An impression is required to finalize a report.")

        return cleaned_data


class ScanImageForm(forms.ModelForm):
    """
    A form for uploading and editing a single scan image and its metadata.
    """

    class Meta:
        model = ScanImageModel
        # Explicitly list all fields a user can edit
        fields = [
            'scan_result',
            'image',
            'view_type',
            'description',
            'sequence_number',
            'image_quality',
            'technical_parameters',
        ]

        widgets = {
            'scan_result': forms.Select(attrs={'class': 'form-select'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'view_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., AP, Lateral, Oblique'}),
            'description': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'e.g., Left knee, anterior view'}),
            'sequence_number': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'image_quality': forms.Select(attrs={'class': 'form-select'}),
            'technical_parameters': forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                                          'placeholder': 'Enter as JSON, e.g., {"kvp": 120, "mas": 100}'}),
        }

        labels = {
            'scan_result': 'Associated Scan Report',
            'view_type': 'View Type / Projection',
            'sequence_number': 'Image Sequence Number',
        }

    def clean_sequence_number(self):
        """Ensure the sequence number is a positive integer."""
        seq_num = self.cleaned_data.get('sequence_number')
        if seq_num is not None and seq_num < 1:
            raise ValidationError("Sequence number must be 1 or greater.")
        return seq_num

    def clean_technical_parameters(self):
        """Validate the JSON format for technical parameters."""
        data = self.cleaned_data.get('technical_parameters')
        if not data:
            return {}  # Default to an empty dictionary if blank

        # If the data is already a dict (from JSONField), it's valid
        if isinstance(data, dict):
            return data

        # If it's a string (from a textarea), try to parse it
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            raise ValidationError("Invalid JSON format for technical parameters.")


class ScanEquipmentForm(forms.ModelForm):
    class Meta:
        model = ScanEquipmentModel
        fields = ['name', 'equipment_type', 'model_number', 'serial_number',
                  'manufacturer', 'supported_templates', 'location',
                  'status', 'last_maintenance', 'next_maintenance',
                  'last_calibration', 'next_calibration',
                  'purchase_date', 'warranty_expires']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'equipment_type': forms.Select(attrs={'class': 'form-control'}),
            'model_number': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'manufacturer': forms.TextInput(attrs={'class': 'form-control'}),
            'supported_templates': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'last_maintenance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'next_maintenance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'last_calibration': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'next_calibration': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'warranty_expires': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class ScanAppointmentForm(forms.ModelForm):
    class Meta:
        model = ScanAppointmentModel
        fields = ['scan_order', 'equipment', 'appointment_date',
                  'estimated_duration', 'status', 'technician',
                  'patient_prepared', 'preparation_notes']
        widgets = {
            'scan_order': forms.Select(attrs={'class': 'form-control'}),
            'equipment': forms.Select(attrs={'class': 'form-control'}),
            'appointment_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'estimated_duration': forms.NumberInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'technician': forms.Select(attrs={'class': 'form-control'}),
            'patient_prepared': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'preparation_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ScanTemplateBuilderForm(forms.ModelForm):
    class Meta:
        model = ScanTemplateBuilderModel
        fields = ['name', 'category', 'scan_preset', 'custom_parameters',
                  'price', 'estimated_duration']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'scan_preset': forms.Select(attrs={'class': 'form-control'}),
            'custom_parameters': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'estimated_duration': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ScanSettingForm(forms.ModelForm):
    """
    Form for updating the global Laboratory Settings.
    """
    class Meta:
        model = ScanSettingModel
        fields = [
            'scan_name', 'mobile', 'email',
            'allow_direct_scan_order',
            'allow_result_print_in_scan',
            'allow_result_printing_by_consultant',
        ]
        widgets = {
            'scan_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Official name of the laboratory'
            }),
            'mobile': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'email': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'allow_direct_scan_order': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_result_print_in_scan': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_result_printing_by_consultant': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

