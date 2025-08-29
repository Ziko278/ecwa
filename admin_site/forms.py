from django.contrib.auth.forms import UserCreationForm
from django.forms import ModelForm, Select, TextInput, Textarea, CheckboxSelectMultiple, DateInput
from django.contrib.auth.models import User
from django import forms
from django.core.exceptions import ValidationError
from admin_site.models import *


class SiteInfoForm(ModelForm):
    """
    Form for managing site info settings with validation.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    class Meta:
        model = SiteInfoModel
        fields = '__all__'
        widgets = {
            'logo': forms.FileInput(attrs={'class': 'form-control'}),
        }

    # Validate mobile number format
    def clean_mobile_1(self):
        mobile = self.cleaned_data.get('mobile_1')
        if not mobile.isdigit():
            raise ValidationError("Primary mobile number must contain digits only.")
        if len(mobile) < 7:
            raise ValidationError("Primary mobile number is too short.")
        return mobile

    def clean_mobile_2(self):
        mobile = self.cleaned_data.get('mobile_2')
        if mobile and not mobile.isdigit():
            raise ValidationError("Secondary mobile number must contain digits only.")
        return mobile

    # Validate social handles (example: no spaces allowed)
    def clean_facebook_handle(self):
        fb = self.cleaned_data.get('facebook_handle')
        if fb and " " in fb:
            raise ValidationError("Facebook handle cannot contain spaces.")
        return fb

    # Cross-field validation
    def clean(self):
        cleaned_data = super().clean()
        mobile_1 = cleaned_data.get('mobile_1')
        mobile_2 = cleaned_data.get('mobile_2')

        if mobile_1 and mobile_2 and mobile_1 == mobile_2:
            raise ValidationError("Primary and secondary mobile numbers cannot be the same.")

        return cleaned_data


