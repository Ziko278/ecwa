from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils import timezone
from insurance.models import (
    InsuranceProviderModel, HMOModel, HMOCoveragePlanModel,
    PatientInsuranceModel, InsuranceClaimModel
)


# -------------------------------
# Insurance Provider Form
# -------------------------------
class InsuranceProviderForm(forms.ModelForm):
    class Meta:
        model = InsuranceProviderModel
        fields = ['name', 'provider_type', 'description', 'status']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Provider Name'}),
            'provider_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Provider name is required.")

        name = name.strip().title()
        qs = InsuranceProviderModel.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"Insurance provider '{name}' already exists.")
        return name


# -------------------------------
# HMO Form
# -------------------------------
class HMOForm(forms.ModelForm):
    class Meta:
        model = HMOModel
        fields = ['name', 'insurance_provider', 'contact_person', 'contact_email',
                  'contact_phone_number', 'address', 'website']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'insurance_provider': forms.Select(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'website': forms.URLInput(attrs={'class': 'form-control'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("HMO name is required.")
        name = name.strip().title()
        qs = HMOModel.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"HMO '{name}' already exists.")
        return name


# -------------------------------
# HMO Coverage Plan Form
# -------------------------------
class HMOCoveragePlanForm(forms.ModelForm):
    class Meta:
        model = HMOCoveragePlanModel
        fields = '__all__'
        widgets = {
            'hmo': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'consultation_covered': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'consultation_coverage_percentage': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'consultation_annual_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'drug_coverage': forms.Select(attrs={'class': 'form-control'}),
            'selected_drugs': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'drug_coverage_percentage': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'drug_annual_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'lab_coverage': forms.Select(attrs={'class': 'form-control'}),
            'selected_lab_tests': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'lab_coverage_percentage': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'lab_annual_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'radiology_coverage': forms.Select(attrs={'class': 'form-control'}),
            'selected_radiology': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'radiology_coverage_percentage': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'radiology_annual_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            # FIXED: These should be widgets, not field definitions
            'surgery_coverage': forms.Select(attrs={'class': 'form-control'}),
            'selected_surgeries': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'surgery_coverage_percentage': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'surgery_annual_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'admission_coverage': forms.Select(attrs={'class': 'form-control'}),
            'admission_coverage_percentage': forms.NumberInput(
                attrs={'class': 'form-control', 'min': '0', 'max': '100'}),
            'admission_annual_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'require_verification': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_referral': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'annual_limit': forms.NumberInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        hmo = self.cleaned_data.get('hmo')
        if not name:
            raise ValidationError("Plan name is required.")
        name = name.strip().title()
        qs = HMOCoveragePlanModel.objects.filter(name__iexact=name, hmo=hmo)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"Coverage plan '{name}' already exists for this HMO.")
        return name


# -------------------------------
# Patient Insurance Form
# -------------------------------
class PatientInsuranceForm(forms.ModelForm):
    class Meta:
        model = PatientInsuranceModel
        fields = ['patient', 'hmo', 'coverage_plan', 'policy_number', 'enrollee_id',
                  'valid_from', 'valid_to', 'is_active', 'is_verified', 'verification_date', 'notes']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control'}),
            'hmo': forms.Select(attrs={'class': 'form-control'}),
            'coverage_plan': forms.Select(attrs={'class': 'form-control'}),
            'policy_number': forms.TextInput(attrs={'class': 'form-control'}),
            'enrollee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'valid_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'valid_to': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_verified': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'verification_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_policy_number(self):
        policy_number = self.cleaned_data.get('policy_number')
        if not policy_number:
            raise ValidationError("Policy number is required.")
        policy_number = policy_number.strip().upper()
        qs = PatientInsuranceModel.objects.filter(policy_number__iexact=policy_number)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(f"Policy number '{policy_number}' is already in use.")
        return policy_number

    def clean(self):
        cleaned_data = super().clean()
        valid_from = cleaned_data.get('valid_from')
        valid_to = cleaned_data.get('valid_to')

        if valid_from and valid_to and valid_to <= valid_from:
            raise ValidationError("Valid To date must be after Valid From date.")
        return cleaned_data

    def form_invalid(self, form):
        if not form.cleaned_data.get('patient'):
            messages.error(self.request, 'Please verify a patient using their card number')
        return super().form_invalid(form)


# -------------------------------
# Insurance Claim Form
# -------------------------------
class InsuranceClaimForm(forms.ModelForm):
    class Meta:
        model = InsuranceClaimModel
        fields = ['patient_insurance', 'claim_type', 'total_amount', 'covered_amount',
                  'patient_amount', 'status', 'service_date', 'processed_date', 'notes', 'rejection_reason']
        widgets = {
            'patient_insurance': forms.Select(attrs={'class': 'form-control'}),
            'claim_type': forms.Select(attrs={'class': 'form-control'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'covered_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'patient_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'service_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'processed_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'rejection_reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        total = cleaned_data.get('total_amount') or 0
        covered = cleaned_data.get('covered_amount') or 0
        patient_share = cleaned_data.get('patient_amount') or 0

        if (covered + patient_share) != total:
            raise ValidationError("Covered amount + Patient amount must equal Total amount.")

        return cleaned_data
