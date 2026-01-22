from django import forms
from django.core.exceptions import ValidationError
from datetime import datetime, date
import re
from patient.models import *


class RegistrationFeeForm(forms.ModelForm):
    """Form for managing registration fees"""

    class Meta:
        model = RegistrationFeeModel
        fields = ['title', 'amount', 'patient_type']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Registration Fee'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'patient_type': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if not title:
            raise ValidationError("Title is required.")
        title = title.strip().upper()
        if len(title) < 3:
            raise ValidationError("Title must be at least 3 characters long.")
        return title

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            raise ValidationError("Amount is required.")
        if amount < 0:
            raise ValidationError("Amount cannot be negative.")
        if amount > 1000000:
            raise ValidationError("Amount cannot exceed 1,000,000.")
        return amount


class RegistrationPaymentForm(forms.ModelForm):
    """Form for patient registration payments"""

    class Meta:
        model = RegistrationPaymentModel
        fields = [
            'full_name', 'old_card_number', 'registration_fee', 'amount',
            'transaction_id', 'registration_status',
            'consultation_paid', 'consultation_fee', 'status'
        ]
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'}),
            'old_card_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Old Card Number'}),
            'registration_fee': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'transaction_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Transaction ID'}),
            'registration_status': forms.Select(attrs={'class': 'form-control'}),
            'consultation_paid': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'consultation_fee': forms.Select(attrs={'class': 'form-control'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        consultation_paid = cleaned_data.get('consultation_paid')
        consultation_fee = cleaned_data.get('consultation_fee')
        registration_fee = cleaned_data.get('registration_fee')
        old_card_number = cleaned_data.get('old_card_number')

        # Rule 1: If consultation is paid, fee must be selected
        if consultation_paid and not consultation_fee:
            raise ValidationError(
                {"consultation_fee": "Consultation fee must be selected if consultation is marked as paid."}
            )

        # Rule 2: If patient type is OLD, card number is required
        if registration_fee and registration_fee.patient_type == 'old' and not old_card_number:
            raise ValidationError(
                {"old_card_number": "Old card number is required for existing (OLD) patients."}
            )

        return cleaned_data


class PatientSettingForm(forms.ModelForm):
    """Form for managing patient system settings"""

    class Meta:
        model = PatientSettingModel
        fields = ['auto_generate_patient_id', 'patient_id_prefix', 'generate_new_card_number',
                  'registration_fee']
        widgets = {
            'auto_generate_patient_id': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'patient_id_prefix': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '10'}),
            'generate_new_card_number': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'registration_fee': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
        }

    def clean_patient_id_prefix(self):
        prefix = self.cleaned_data.get('patient_id_prefix')
        if prefix:
            prefix = prefix.upper().strip()

            if not re.match(r'^[A-Z0-9]+$', prefix):
                raise ValidationError("Patient ID prefix must contain only letters and numbers.")

            if len(prefix) < 2 or len(prefix) > 10:
                raise ValidationError("Patient ID prefix must be between 2 and 10 characters.")

        return prefix

    def clean_registration_fee(self):
        fee = self.cleaned_data.get('registration_fee')
        if fee is not None:
            if fee < 0:
                raise ValidationError("Registration fee cannot be negative.")

            if fee > 1000000:  # Reasonable upper limit
                raise ValidationError("Registration fee seems too high.")

        return fee


class PatientForm(forms.ModelForm):
    """Comprehensive form for patient registration with validation"""

    class Meta:
        model = PatientModel
        fields = [
            'first_name', 'middle_name', 'last_name', 'card_number', 'date_of_birth', 'gender',
            'occupation', 'address', 'image', 'mobile', 'email', 'marital_status', 'religion',
            'state', 'lga', 'blood_group', 'genotype', 'medical_note',
            'next_of_kin_name', 'next_of_kin_number', 'next_of_kin_address'
        ]

        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Middle Name (Optional)'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'card_number': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Auto-generated if empty'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Occupation'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Residential Address'}),
            'image': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., +2348012345678'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'marital_status': forms.Select(attrs={'class': 'form-control'}),
            'religion': forms.Select(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'State of Origin'}),
            'lga': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Local Government Area'}),
            'blood_group': forms.Select(attrs={'class': 'form-control'}),
            'genotype': forms.Select(attrs={'class': 'form-control'}),
            'medical_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 3,
                                                  'placeholder': 'Any medical conditions, allergies, or notes'}),
            'next_of_kin_name': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Next of Kin Full Name'}),
            'next_of_kin_number': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Next of Kin Phone Number'}),
            'next_of_kin_address': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Next of Kin Address'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make card_number read-only for new patients
        if not self.instance.pk:
            self.fields['card_number'].required = False

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

    def clean_card_number(self):
        card_number = self.cleaned_data.get('card_number')
        if card_number:
            # Check uniqueness for existing card numbers
            existing = PatientModel.objects.filter(card_number=card_number)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError("This patient ID already exists.")

        return card_number

    def clean_mobile(self):
        mobile = self.cleaned_data.get('mobile')
        if mobile:
            # Remove spaces and special characters
            mobile = re.sub(r'[^\d+]', '', mobile)

            # Validate format (Nigerian format - adjust for your country)
            if not re.match(r'^(\+234|0)[789]\d{9}$', mobile):
                raise ValidationError("Enter a valid mobile number (e.g., +2348012345678 or 08012345678).")

            # Check uniqueness
            existing = PatientModel.objects.filter(mobile=mobile)
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
            existing = PatientModel.objects.filter(email__iexact=email)
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

            if age > 150:
                raise ValidationError("Please verify the date of birth (age appears to be over 150).")

        return dob

    def clean_next_of_kin_number(self):
        kin_number = self.cleaned_data.get('next_of_kin_number')
        if kin_number:
            # Remove spaces and special characters
            kin_number = re.sub(r'[^\d+]', '', kin_number)

            # Validate format
            if not re.match(r'^(\+234|0)[789]\d{9}$', kin_number):
                raise ValidationError("Enter a valid next of kin mobile number.")

        return kin_number

    def clean_next_of_kin_name(self):
        kin_name = self.cleaned_data.get('next_of_kin_name')
        if kin_name:
            kin_name = kin_name.strip().title()
            if len(kin_name) < 3:
                raise ValidationError("Next of kin name must be at least 3 characters long.")

            if not re.match(r'^[a-zA-Z\s\-\']+$', kin_name):
                raise ValidationError("Next of kin name contains invalid characters.")

        return kin_name

    def clean_occupation(self):
        occupation = self.cleaned_data.get('occupation')
        if occupation:
            occupation = occupation.strip().title()
            if len(occupation) < 2:
                raise ValidationError("Occupation must be at least 2 characters long.")

            if not re.match(r'^[a-zA-Z0-9\s\-&/(),.]+$', occupation):
                raise ValidationError("Occupation contains invalid characters.")

        return occupation

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

    def clean(self):
        cleaned_data = super().clean()
        mobile = cleaned_data.get('mobile')
        kin_number = cleaned_data.get('next_of_kin_number')

        # Ensure mobile and next of kin numbers are different
        if mobile and kin_number and mobile == kin_number:
            raise ValidationError("Patient mobile and next of kin mobile cannot be the same.")

        return cleaned_data


class PatientEditForm(PatientForm):
    """Form for editing existing patients - inherits all validation from PatientForm"""

    class Meta(PatientForm.Meta):
        # Use all fields except registration_payment
        exclude = ['registration_payment', 'created_by']

        # Optionally redefine widgets if needed
        widgets = PatientForm.Meta.widgets


class PatientSearchForm(forms.Form):
    """Form for searching patients"""

    search_query = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search by name, card number, or mobile...',
            'autocomplete': 'off'
        })
    )

    gender = forms.ChoiceField(
        choices=GENDER,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    blood_group = forms.ChoiceField(
        choices=BLOOD_GROUP,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to:
            if date_to < date_from:
                raise ValidationError("End date must be after start date.")

        return cleaned_data


class PatientWalletTopUpForm(forms.Form):
    """Form for adding funds to patient wallet"""

    amount = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01',
            'placeholder': '0.00'
        })
    )

    payment_method = forms.ChoiceField(
        choices=[
            ('cash', 'Cash'),
            ('card', 'Card Payment'),
            ('transfer', 'Bank Transfer'),
            ('mobile', 'Mobile Money')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    reference = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Payment reference (optional)'
        })
    )

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount:
            if amount > 1000000:  # 1 million limit
                raise ValidationError("Amount cannot exceed 1,000,000.")

            if amount < 0.01:
                raise ValidationError("Minimum amount is 0.01.")

        return amount


class ConsultationDocumentForm(forms.ModelForm):
    class Meta:
        model = ConsultationDocument
        fields = ['document', 'title', 'description']
        widgets = {
            'document': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.jpg,.jpeg,.png,.doc,.docx'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Document title (optional)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Document description (optional)'
            })
        }