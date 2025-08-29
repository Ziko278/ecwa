from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from datetime import date
import re
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
        fields = ['name', 'code', 'category', 'scan_parameters', 'price',
                  'scan_type', 'estimated_duration', 'preparation_required',
                  'fasting_required', 'equipment_required', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'scan_parameters': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'scan_type': forms.Select(attrs={'class': 'form-control'}),
            'estimated_duration': forms.TextInput(attrs={'class': 'form-control'}),
            'preparation_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'fasting_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'equipment_required': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
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


class ScanOrderForm(forms.ModelForm):
    class Meta:
        model = ScanOrderModel
        fields = ['patient', 'template', 'ordered_by', 'status',
                  'payment_status', 'payment_date', 'payment_by',
                  'scheduled_date', 'scheduled_by',
                  'scan_started_at', 'scan_completed_at', 'performed_by',
                  'clinical_indication', 'special_instructions']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control'}),
            'template': forms.Select(attrs={'class': 'form-control'}),
            'ordered_by': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'payment_status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'payment_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'payment_by': forms.Select(attrs={'class': 'form-control'}),
            'scheduled_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'scheduled_by': forms.Select(attrs={'class': 'form-control'}),
            'scan_started_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'scan_completed_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'performed_by': forms.Select(attrs={'class': 'form-control'}),
            'clinical_indication': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'special_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ScanResultForm(forms.ModelForm):
    class Meta:
        model = ScanResultModel
        fields = ['order', 'measurements_data', 'findings', 'impression',
                  'recommendations', 'scan_images', 'scan_files',
                  'is_verified', 'verified_by', 'verified_at',
                  'technician_notes', 'doctor_interpretation']
        widgets = {
            'order': forms.Select(attrs={'class': 'form-control'}),
            'measurements_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'findings': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'impression': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'recommendations': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'scan_images': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'scan_files': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'verified_by': forms.Select(attrs={'class': 'form-control'}),
            'verified_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'technician_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'doctor_interpretation': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


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
                  'price', 'scan_type', 'estimated_duration']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'scan_preset': forms.Select(attrs={'class': 'form-control'}),
            'custom_parameters': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'scan_type': forms.TextInput(attrs={'class': 'form-control'}),
            'estimated_duration': forms.TextInput(attrs={'class': 'form-control'}),
        }


class ScanSettingForm(forms.ModelForm):
    class Meta:
        model = ScanSettingModel
        fields = ['department_name', 'department_head',
                  'default_appointment_duration', 'advance_booking_days',
                  'working_hours_start', 'working_hours_end',
                  'send_appointment_reminders', 'reminder_hours_before']
        widgets = {
            'department_name': forms.TextInput(attrs={'class': 'form-control'}),
            'department_head': forms.TextInput(attrs={'class': 'form-control'}),
            'default_appointment_duration': forms.NumberInput(attrs={'class': 'form-control'}),
            'advance_booking_days': forms.NumberInput(attrs={'class': 'form-control'}),
            'working_hours_start': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'working_hours_end': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'send_appointment_reminders': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reminder_hours_before': forms.NumberInput(attrs={'class': 'form-control'}),
        }
