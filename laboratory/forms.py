from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import date
import re
from .models import *


class LabTestCategoryForm(forms.ModelForm):
    class Meta:
        model = LabTestCategoryModel
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

        qs = LabTestCategoryModel.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise ValidationError(f"Category '{name}' already exists.")

        return name

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper().strip()
            if not re.match(r'^[A-Z0-9]+$', code):
                raise ValidationError("Code must contain only letters and numbers.")

            if len(code) < 2 or len(code) > 10:
                raise ValidationError("Code must be between 2 and 10 characters.")

            qs = LabTestCategoryModel.objects.filter(code=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if qs.exists():
                raise ValidationError(f"Code '{code}' already exists.")
        return code


class LabTestTemplateForm(forms.ModelForm):
    class Meta:
        model = LabTestTemplateModel
        fields = ['name', 'code', 'category', 'test_parameters', 'price',
                  'sample_type', 'sample_volume', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'test_parameters': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sample_type': forms.Select(attrs={'class': 'form-control'}),
            'sample_volume': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Template name is required.")
        name = name.strip()
        qs = LabTestTemplateModel.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("Template name already exists.")
        return name

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            code = code.strip().upper()
            qs = LabTestTemplateModel.objects.filter(code=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise ValidationError("Template code already exists.")
        return code


class LabTestOrderForm(forms.ModelForm):
    class Meta:
        model = LabTestOrderModel
        fields = ['patient', 'template', 'ordered_by', 'status',
                  'payment_status', 'payment_date', 'payment_by',
                  'sample_collected_at', 'sample_collected_by', 'sample_label',
                  'expected_completion', 'special_instructions']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control'}),
            'template': forms.Select(attrs={'class': 'form-control'}),
            'ordered_by': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'payment_status': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'payment_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'payment_by': forms.Select(attrs={'class': 'form-control'}),
            'sample_collected_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'sample_collected_by': forms.Select(attrs={'class': 'form-control'}),
            'sample_label': forms.TextInput(attrs={'class': 'form-control'}),
            'expected_completion': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'special_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class LabTestOrderCreateForm(forms.ModelForm):
    """
    For the create view only: exclude 'template' so we can create multiple orders
    (one per selected template) in the view.
    """
    class Meta:
        model = LabTestOrderModel
        exclude = ['template', 'order_number', 'amount_charged', 'ordered_at']
        widgets = {
            'payment_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'sample_collected_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'expected_completion': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'special_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class LabTestResultForm(forms.ModelForm):
    class Meta:
        model = LabTestResultModel
        fields = ['order', 'results_data', 'technician_comments',
                  'pathologist_comments', 'is_verified', 'verified_by', 'verified_at']
        widgets = {
            'order': forms.Select(attrs={'class': 'form-control'}),
            'results_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'technician_comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'pathologist_comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'verified_by': forms.Select(attrs={'class': 'form-control'}),
            'verified_at': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }


class LabEquipmentForm(forms.ModelForm):
    class Meta:
        model = LabEquipmentModel
        fields = ['name', 'model_number', 'serial_number', 'supported_templates',
                  'status', 'purchase_date', 'last_maintenance', 'next_maintenance']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'model_number': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'supported_templates': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'last_maintenance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'next_maintenance': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class LabReagentForm(forms.ModelForm):
    class Meta:
        model = LabReagentModel
        fields = ['name', 'brand', 'catalog_number', 'used_in_templates',
                  'current_stock', 'minimum_stock', 'unit', 'expiry_date', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'brand': forms.TextInput(attrs={'class': 'form-control'}),
            'catalog_number': forms.TextInput(attrs={'class': 'form-control'}),
            'used_in_templates': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'current_stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'minimum_stock': forms.NumberInput(attrs={'class': 'form-control'}),
            'unit': forms.TextInput(attrs={'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class LabTestTemplateBuilderForm(forms.ModelForm):
    class Meta:
        model = LabTestTemplateBuilderModel
        fields = ['name', 'category', 'parameter_preset', 'custom_parameters',
                  'price', 'sample_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'parameter_preset': forms.Select(attrs={'class': 'form-control'}),
            'custom_parameters': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'sample_type': forms.TextInput(attrs={'class': 'form-control'}),
        }


class LabSettingForm(forms.ModelForm):
    """
    Form for updating the global Laboratory Settings.
    """
    class Meta:
        model = LabSettingModel
        fields = [
            'lab_name', 'mobile', 'email',
            'allow_direct_lab_order',
            'allow_result_print_in_lab',
            'allow_result_printing_by_consultant',
        ]
        widgets = {
            'lab_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Official name of the laboratory'
            }),
            'mobile': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'email': forms.TextInput(attrs={
                'class': 'form-control',
            }),
            'allow_direct_lab_order': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_result_print_in_lab': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'allow_result_printing_by_consultant': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

