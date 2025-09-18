from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, date
from decimal import Decimal
import re

from patient.models import PatientModel
from .models import *
from human_resource.models import DepartmentModel, StaffModel


class FinanceSettingForm(forms.ModelForm):
    """
    A form for creating and updating the singleton FinanceSettingModel instance.
    """
    class Meta:
        model = FinanceSettingModel
        fields = [
            'minimum_funding',
            'maximum_funding',
            'allow_negative_balance',
        ]
        widgets = {
            'minimum_funding': forms.NumberInput(attrs={'class': 'form-control'}),
            'maximum_funding': forms.NumberInput(attrs={'class': 'form-control'}),
            'allow_negative_balance': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# -------------------- EXPENSE MANAGEMENT FORMS --------------------

class ExpenseCategoryForm(forms.ModelForm):
    class Meta:
        model = ExpenseCategory
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category Name'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CODE', 'maxlength': '20'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Category name is required.")

        # Remove extra spaces and validate
        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Category name must be at least 2 characters long.")

        # Check for special characters
        if not re.match(r'^[a-zA-Z0-9\s\-&]+$', name):
            raise ValidationError("Category name contains invalid characters.")

        # Check uniqueness (case-insensitive)
        existing = ExpenseCategory.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Category '{name}' already exists.")

        return name

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if not code:
            raise ValidationError("Category code is required.")

        code = code.upper().strip()

        # Validate format
        if not re.match(r'^[A-Z0-9]+$', code):
            raise ValidationError("Category code must contain only letters and numbers.")

        if len(code) < 2 or len(code) > 20:
            raise ValidationError("Category code must be between 2 and 20 characters.")

        # Check uniqueness
        existing = ExpenseCategory.objects.filter(code=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Category code '{code}' already exists.")

        return code


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            'expense_number', 'title', 'description', 'category',
            'department', 'amount', 'date', 'paid_by',
            'invoice_reference', 'payment_method'
        ]
        widgets = {
            'expense_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'EXP-XXXX'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'paid_by': forms.Select(attrs={'class': 'form-control'}),
            'invoice_reference': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_method': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Cash, Bank Transfer, etc.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = ExpenseCategory.objects.all()
        self.fields['department'].queryset = DepartmentModel.objects.all()
        self.fields['paid_by'].queryset = User.objects.filter(is_active=True)

        # Set empty labels
        self.fields['category'].empty_label = "Select Category"
        self.fields['department'].empty_label = "Select Department"
        self.fields['paid_by'].empty_label = "Select Staff"

    def clean_expense_number(self):
        expense_number = self.cleaned_data.get('expense_number')
        if not expense_number:
            return

        expense_number = expense_number.upper().strip()

        # Validate format
        if not re.match(r'^[A-Z0-9\-\/]+$', expense_number):
            raise ValidationError("Expense number contains invalid characters.")

        if len(expense_number) < 3:
            raise ValidationError("Expense number must be at least 3 characters long.")

        # Check uniqueness
        existing = Expense.objects.filter(expense_number=expense_number)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Expense number '{expense_number}' already exists.")

        return expense_number

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if not title:
            raise ValidationError("Title is required.")

        title = ' '.join(title.strip().split())
        if len(title) < 3:
            raise ValidationError("Title must be at least 3 characters long.")

        return title

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if not amount or amount <= 0:
            raise ValidationError("Amount must be greater than 0.")

        if amount > Decimal('999999999.99'):
            raise ValidationError("Amount is too large.")

        return amount

    def clean_date(self):
        expense_date = self.cleaned_data.get('date')
        if not expense_date:
            raise ValidationError("Date is required.")

        if expense_date > date.today():
            raise ValidationError("Expense date cannot be in the future.")

        # Check if too far in the past (1 year)
        days_ago = (date.today() - expense_date).days
        if days_ago > 365:
            raise ValidationError("Expense date cannot be more than 1 year ago.")

        return expense_date


# -------------------- INCOME MANAGEMENT FORMS --------------------

class IncomeCategoryForm(forms.ModelForm):
    class Meta:
        model = IncomeCategory
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category Name'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'CODE', 'maxlength': '20'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Category name is required.")

        # Remove extra spaces and validate
        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Category name must be at least 2 characters long.")

        # Check for special characters
        if not re.match(r'^[a-zA-Z0-9\s\-&]+$', name):
            raise ValidationError("Category name contains invalid characters.")

        # Check uniqueness (case-insensitive)
        existing = IncomeCategory.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Category '{name}' already exists.")

        return name

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if not code:
            raise ValidationError("Category code is required.")

        code = code.upper().strip()

        # Validate format
        if not re.match(r'^[A-Z0-9]+$', code):
            raise ValidationError("Category code must contain only letters and numbers.")

        if len(code) < 2 or len(code) > 20:
            raise ValidationError("Category code must be between 2 and 20 characters.")

        # Check uniqueness
        existing = IncomeCategory.objects.filter(code=code)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Category code '{code}' already exists.")

        return code


class IncomeForm(forms.ModelForm):
    class Meta:
        model = Income
        fields = [
            'income_number', 'title', 'description', 'category',
            'department', 'amount', 'date', 'received_by',
            'source', 'receipt_number', 'payment_method'
        ]
        widgets = {
            'income_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'INC-XXXX'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'received_by': forms.Select(attrs={'class': 'form-control'}),
            'source': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Patient, Insurance, etc.'}),
            'receipt_number': forms.TextInput(attrs={'class': 'form-control'}),
            'payment_method': forms.TextInput(
                attrs={'class': 'form-control', 'placeholder': 'Cash, Card, Transfer, etc.'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = IncomeCategory.objects.all()
        self.fields['department'].queryset = DepartmentModel.objects.all()
        self.fields['received_by'].queryset = User.objects.filter(is_active=True)

        # Set empty labels
        self.fields['category'].empty_label = "Select Category"
        self.fields['department'].empty_label = "Select Department"
        self.fields['received_by'].empty_label = "Select Staff"

    def clean_income_number(self):
        income_number = self.cleaned_data.get('income_number')
        if not income_number:
            return

        income_number = income_number.upper().strip()

        # Validate format
        if not re.match(r'^[A-Z0-9\-\/]+$', income_number):
            raise ValidationError("Income number contains invalid characters.")

        if len(income_number) < 3:
            raise ValidationError("Income number must be at least 3 characters long.")

        # Check uniqueness
        existing = Income.objects.filter(income_number=income_number)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Income number '{income_number}' already exists.")

        return income_number

    def clean_title(self):
        title = self.cleaned_data.get('title')
        if not title:
            raise ValidationError("Title is required.")

        title = ' '.join(title.strip().split())
        if len(title) < 3:
            raise ValidationError("Title must be at least 3 characters long.")

        return title

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if not amount or amount <= 0:
            raise ValidationError("Amount must be greater than 0.")

        if amount > Decimal('999999999.99'):
            raise ValidationError("Amount is too large.")

        return amount

    def clean_date(self):
        income_date = self.cleaned_data.get('date')
        if not income_date:
            raise ValidationError("Date is required.")

        if income_date > date.today():
            raise ValidationError("Income date cannot be in the future.")

        # Check if too far in the past (1 year)
        days_ago = (date.today() - income_date).days
        if days_ago > 365:
            raise ValidationError("Income date cannot be more than 1 year ago.")

        return income_date


class OtherPaymentServiceForm(forms.ModelForm):
    class Meta:
        model = OtherPaymentService
        fields = [
            'name', 'description', 'category', 'default_amount',
            'is_fixed_amount', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Medical Report Fee'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'default_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_fixed_amount': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set empty label for the category dropdown
        self.fields['category'].empty_label = "Select Category"

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Service name is required.")

        # Sanitize input by removing leading/trailing space and collapsing internal spaces
        name = ' '.join(name.strip().split())

        if len(name) < 3:
            raise ValidationError("Service name must be at least 3 characters long.")

        # Check for uniqueness (case-insensitive)
        existing = OtherPaymentService.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"A service with the name '{name}' already exists.")

        return name

    def clean_default_amount(self):
        amount = self.cleaned_data.get('default_amount')

        # This field is optional, so only validate if a value is provided
        if amount is not None:
            if amount < 0:
                raise ValidationError("Amount cannot be negative.")
            if amount > Decimal('9999999.99'):
                raise ValidationError("Amount is too large.")

        return amount


class OtherPaymentForm(forms.Form):
    # REMOVED: The 'patient' field is no longer here.
    other_service = forms.ModelChoiceField(
        queryset=OtherPaymentService.objects.filter(is_active=True),
        empty_label="--- Select a Service ---",
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )
    amount = forms.DecimalField(
        max_digits=10, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control form-control-lg', 'step': '0.01'})
    )



#------------------- SALARY MANAGEMENT FORMS --------------------

class StaffBankDetailForm(forms.ModelForm):
    class Meta:
        model = StaffBankDetail
        fields = ['staff', 'bank_name', 'account_number', 'account_name', 'sort_code', 'is_active']
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-control'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control'}),
            'account_name': forms.TextInput(attrs={'class': 'form-control'}),
            'sort_code': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['staff'].queryset = StaffModel.objects.filter(status='active')
        self.fields['staff'].empty_label = "Select Staff"

    def clean_bank_name(self):
        bank_name = self.cleaned_data.get('bank_name')
        if not bank_name:
            raise ValidationError("Bank name is required.")

        bank_name = ' '.join(bank_name.strip().split())
        if len(bank_name) < 3:
            raise ValidationError("Bank name must be at least 3 characters long.")

        return bank_name

    def clean_account_number(self):
        account_number = self.cleaned_data.get('account_number')
        if not account_number:
            raise ValidationError("Account number is required.")

        account_number = re.sub(r'[^\d]', '', account_number)  # Remove non-digits

        if len(account_number) < 10:
            raise ValidationError("Account number must be at least 10 digits.")

        if len(account_number) > 20:
            raise ValidationError("Account number is too long.")

        return account_number

    def clean_account_name(self):
        account_name = self.cleaned_data.get('account_name')
        if not account_name:
            raise ValidationError("Account name is required.")

        account_name = ' '.join(account_name.strip().split())
        if len(account_name) < 3:
            raise ValidationError("Account name must be at least 3 characters long.")

        return account_name


class SalaryStructureForm(forms.ModelForm):
    class Meta:
        model = SalaryStructure
        fields = [
            'staff', 'basic_salary', 'housing_allowance', 'transport_allowance',
            'medical_allowance', 'other_allowances', 'tax_rate', 'pension_rate',
            'effective_from', 'is_active'
        ]
        widgets = {
            'staff': forms.Select(attrs={'class': 'form-control'}),
            'basic_salary': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'housing_allowance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'transport_allowance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'medical_allowance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'other_allowances': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'tax_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'pension_rate': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'effective_from': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['staff'].queryset = StaffModel.objects.filter(status='active')
        self.fields['staff'].empty_label = "Select Staff"

    def clean_basic_salary(self):
        basic_salary = self.cleaned_data.get('basic_salary')
        if not basic_salary or basic_salary <= 0:
            raise ValidationError("Basic salary must be greater than 0.")

        if basic_salary > Decimal('99999999.99'):
            raise ValidationError("Basic salary is too large.")

        return basic_salary

    def clean_tax_rate(self):
        tax_rate = self.cleaned_data.get('tax_rate')
        if tax_rate and (tax_rate < 0 or tax_rate > 100):
            raise ValidationError("Tax rate must be between 0 and 100 percent.")

        return tax_rate or Decimal('0.00')

    def clean_pension_rate(self):
        pension_rate = self.cleaned_data.get('pension_rate')
        if pension_rate and (pension_rate < 0 or pension_rate > 100):
            raise ValidationError("Pension rate must be between 0 and 100 percent.")

        return pension_rate or Decimal('0.00')

    def clean_effective_from(self):
        effective_from = self.cleaned_data.get('effective_from')
        if not effective_from:
            raise ValidationError("Effective from date is required.")

        # Allow backdated salary structures but warn if too far back
        days_ago = (date.today() - effective_from).days
        if days_ago > 1095:  # 3 years
            raise ValidationError("Effective date cannot be more than 3 years ago.")

        return effective_from


class PaysheetRowForm(forms.ModelForm):
    """
    This form represents a single editable row in the interactive paysheet.
    It only includes the fields that a user can manually adjust during a payroll run.
    """
    class Meta:
        model = SalaryRecord
        # These are the only fields the user can edit in the table.
        # All other fields (like basic_salary, allowances, etc.) are treated as read-only.
        fields = [
            'bonus',
            'other_deductions',
            'notes',
            'amount_paid'
        ]
        widgets = {
            # We add a custom 'editable-field' class to easily attach JS listeners for live calculation.
            'bonus': forms.NumberInput(attrs={'class': 'form-control form-control-sm editable-field', 'step': '0.01'}),
            'other_deductions': forms.NumberInput(attrs={'class': 'form-control form-control-sm editable-field', 'step': '0.01'}),
            'notes': forms.TextInput(attrs={'class': 'form-control form-control-sm'}),
            'amount_paid': forms.NumberInput(attrs={'class': 'form-control form-control-sm editable-field', 'step': '0.01'}),
        }


class PatientTransactionForm(forms.ModelForm):
    """
    A form specifically for creating a consultation payment from the UI.
    It validates the patient and the selected fee structure.
    """

    class Meta:
        model = PatientTransactionModel
        # We now include 'fee_structure' directly, as it's a ForeignKey on the model.
        # Django's ModelForm will handle the validation against the FeeStructureModel.
        fields = ['patient', 'fee_structure']

        # Both fields will be populated by JavaScript and should not be visible to the user.
        widgets = {
            'patient': forms.HiddenInput(),
            'fee_structure': forms.HiddenInput(),
        }


class UserChoiceFieldWithStaffFallback(forms.ModelChoiceField):
    """
    A custom ModelChoiceField that displays a user's full staff name if available,
    otherwise falls back to their user's full name or username.
    """
    def label_from_instance(self, obj):
        # Try to get the full name from the related StaffModel via the profile
        if hasattr(obj, 'user_staff_profile') and obj.user_staff_profile and obj.user_staff_profile.staff:
            return obj.user_staff_profile.staff.__str__().title()
        # Fallback to the User model's full name if it exists
        elif obj.get_full_name():
            return obj.get_full_name().title()
        # Final fallback to the username
        else:
            return obj.username


class MoneyRemittanceForm(forms.ModelForm):
    """
    Form for an admin/accountant to record a remittance from a staff member.
    """
    # Use the new custom field for 'remitted_by'
    remitted_by = UserChoiceFieldWithStaffFallback(
        queryset=User.objects.none(),  # The view will populate this queryset
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Staff Member Remitting Funds"
    )

    class Meta:
        model = MoneyRemittance
        # 'remitted_by' is now included
        fields = [
            'remitted_by',
            'amount_remitted_cash',
            'notes'
        ]
        widgets = {
            'amount_remitted_cash': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }
        labels = {
            'amount_remitted_cash': 'Actual Cash Amount Being Remitted',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set an empty label for better user experience
        self.fields['remitted_by'].empty_label = "Select a Staff Member..."

