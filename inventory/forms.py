from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import datetime, date
from decimal import Decimal, InvalidOperation
import re
from inventory.models import *
from human_resource.models import DepartmentModel


class UnitForm(forms.ModelForm):
    class Meta:
        model = Unit
        fields = ['name', 'abbreviation']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unit Name'}),
            'abbreviation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Abbr', 'maxlength': '12'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Unit name is required.")

        name = ' '.join(name.strip().split())
        if len(name) < 1:
            raise ValidationError("Unit name must be at least 1 character long.")

        # Check uniqueness (case-insensitive)
        existing = Unit.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Unit '{name}' already exists.")

        return name

    def clean_abbreviation(self):
        abbreviation = self.cleaned_data.get('abbreviation')
        if abbreviation:
            abbreviation = abbreviation.strip()
            if len(abbreviation) > 12:
                raise ValidationError("Abbreviation cannot exceed 12 characters.")

        return abbreviation


class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'phone', 'email', 'address', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Supplier Name'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Person'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone Number'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Address'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Supplier name is required.")

        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Supplier name must be at least 2 characters long.")

        # Check uniqueness (case-insensitive)
        existing = Supplier.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Supplier '{name}' already exists.")

        return name

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            # Remove spaces and special characters
            phone = re.sub(r'[^\d+]', '', phone)
            if phone and not re.match(r'^(\+234|0)[789]\d{9}$', phone):
                raise ValidationError("Enter a valid phone number (e.g., +2348012345678 or 08012345678).")

        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            # Check uniqueness
            existing = Supplier.objects.filter(email__iexact=email)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError("This email is already registered.")

        return email


class InventoryCategoryForm(forms.ModelForm):
    class Meta:
        model = InventoryCategory
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Category Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Description'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Category name is required.")

        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Category name must be at least 2 characters long.")

        # Check uniqueness (case-insensitive)
        existing = InventoryCategory.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"Category '{name}' already exists.")

        return name


class InventoryItemForm(forms.ModelForm):
    class Meta:
        model = InventoryItem
        fields = [
            'name', 'sku', 'category', 'item_type', 'unit', 'department',
            'reorder_level', 'min_level', 'expiry_date', 'batch_number',
            'storage_location', 'is_active'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Item Name'}),
            'sku': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'SKU/Code'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'item_type': forms.Select(attrs={'class': 'form-control'}),
            'unit': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'reorder_level': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'}),
            'min_level': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'batch_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Batch Number'}),
            'storage_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Storage Location'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].queryset = InventoryCategory.objects.filter(is_active=True)
        self.fields['unit'].queryset = Unit.objects.all()
        self.fields['department'].queryset = DepartmentModel.objects.all()

        self.fields['category'].empty_label = "Select Category"
        self.fields['unit'].empty_label = "Select Unit"
        self.fields['department'].empty_label = "Select Department"

    def clean_name(self):
        name = self.cleaned_data.get('name')
        department = self.cleaned_data.get('department')

        if not name:
            raise ValidationError("Item name is required.")

        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Item name must be at least 2 characters long.")

        # Check uniqueness within department
        if department:
            existing = InventoryItem.objects.filter(name__iexact=name, department=department)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"Item '{name}' already exists in {department.name}.")

        return name

    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        if sku:
            sku = sku.upper().strip()

            # Check uniqueness
            existing = InventoryItem.objects.filter(sku=sku)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"SKU '{sku}' already exists.")

        return sku

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')
        if expiry_date:
            if expiry_date <= date.today():
                raise ValidationError("Expiry date must be in the future.")

        return expiry_date

    def clean(self):
        cleaned_data = super().clean()
        reorder_level = cleaned_data.get('reorder_level')
        min_level = cleaned_data.get('min_level')

        if reorder_level and min_level:
            if min_level > reorder_level:
                raise ValidationError("Minimum level cannot be greater than reorder level.")

        return cleaned_data


class StockRecordForm(forms.ModelForm):
    class Meta:
        model = StockRecord
        fields = [
            'item', 'transaction_type', 'quantity', 'supplier', 'reference',
            'department', 'cost', 'batch_number', 'expiry_date'
        ]
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'transaction_type': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001'}),
            'supplier': forms.Select(attrs={'class': 'form-control'}),
            'reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reference/PO Number'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'batch_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Batch Number'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = InventoryItem.objects.filter(is_active=True)
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True)
        self.fields['department'].queryset = DepartmentModel.objects.all()

        self.fields['item'].empty_label = "Select Item"
        self.fields['supplier'].empty_label = "Select Supplier"
        self.fields['department'].empty_label = "Select Department"

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if not quantity or quantity <= 0:
            raise ValidationError("Quantity must be greater than 0.")

        return quantity

    def clean_cost(self):
        cost = self.cleaned_data.get('cost')
        if cost is not None and cost < 0:
            raise ValidationError("Cost cannot be negative.")

        return cost

    def clean(self):
        cleaned_data = super().clean()
        transaction_type = cleaned_data.get('transaction_type')
        supplier = cleaned_data.get('supplier')

        # Require supplier for stock-in transactions
        if transaction_type == StockRecord.TYPE_IN and not supplier:
            raise ValidationError("Supplier is required for stock-in transactions.")

        return cleaned_data


class StockUsageForm(forms.ModelForm):
    class Meta:
        model = StockUsage
        fields = ['patient', 'purpose', 'department', 'usage_date', 'notes']
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-control'}),
            'purpose': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Purpose of usage'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'usage_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Additional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            from patients.models import Patient
            self.fields['patient'].queryset = Patient.objects.all()
        except ImportError:
            # If patients app doesn't exist, hide the field
            self.fields['patient'].widget = forms.HiddenInput()

        self.fields['department'].queryset = DepartmentModel.objects.all()

        self.fields['patient'].empty_label = "Select Patient (Optional)"
        self.fields['department'].empty_label = "Select Department"

    def clean_purpose(self):
        purpose = self.cleaned_data.get('purpose')
        if purpose:
            purpose = purpose.strip()
            if len(purpose) < 3:
                raise ValidationError("Purpose must be at least 3 characters long.")

        return purpose

    def clean_usage_date(self):
        usage_date = self.cleaned_data.get('usage_date')
        if usage_date:
            if usage_date > timezone.now():
                raise ValidationError("Usage date cannot be in the future.")

        return usage_date


class StockUsageItemForm(forms.ModelForm):
    class Meta:
        model = StockUsageItem
        fields = ['item', 'quantity', 'unit_cost', 'notes']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'notes': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = InventoryItem.objects.filter(is_active=True, quantity__gt=0)
        self.fields['item'].empty_label = "Select Item"

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        item = self.cleaned_data.get('item')

        if not quantity or quantity <= 0:
            raise ValidationError("Quantity must be greater than 0.")

        # Check if sufficient stock is available
        if item and quantity > item.quantity:
            raise ValidationError(f"Insufficient stock. Available: {item.quantity} {item.unit}")

        return quantity


class StockDamageForm(forms.ModelForm):
    class Meta:
        model = StockDamage
        fields = ['item', 'quantity', 'reason', 'department', 'cost', 'date_reported']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Reason for damage'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'date_reported': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = InventoryItem.objects.filter(is_active=True)
        self.fields['department'].queryset = DepartmentModel.objects.all()

        self.fields['item'].empty_label = "Select Item"
        self.fields['department'].empty_label = "Select Department"

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if not quantity or quantity <= 0:
            raise ValidationError("Quantity must be greater than 0.")

        return quantity

    def clean_date_reported(self):
        date_reported = self.cleaned_data.get('date_reported')
        if date_reported:
            if date_reported > date.today():
                raise ValidationError("Date reported cannot be in the future.")

        return date_reported


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = [
            'name', 'serial_number', 'asset_tag', 'asset_type', 'department',
            'location', 'purchase_date', 'purchase_cost', 'vendor', 'condition',
            'is_operational', 'warranty_expiry', 'warranty_provider', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asset Name'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Serial Number'}),
            'asset_tag': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Asset Tag'}),
            'asset_type': forms.Select(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Location'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'purchase_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'vendor': forms.Select(attrs={'class': 'form-control'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'is_operational': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'warranty_expiry': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'warranty_provider': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Warranty Provider'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Additional notes'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'] = forms.ModelChoiceField(
            queryset=InventoryCategory.objects.filter(is_active=True),
            empty_label="Select Category",
            widget=forms.Select(attrs={'class': 'form-control'})
        )
        self.fields['vendor'].queryset = Supplier.objects.filter(is_active=True)
        self.fields['department'].queryset = DepartmentModel.objects.all()

        self.fields['vendor'].empty_label = "Select Vendor"
        self.fields['department'].empty_label = "Select Department"

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Asset name is required.")

        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Asset name must be at least 2 characters long.")

        return name

    def clean_asset_tag(self):
        asset_tag = self.cleaned_data.get('asset_tag')
        if asset_tag:
            asset_tag = asset_tag.upper().strip()

            # Check uniqueness
            existing = Asset.objects.filter(asset_tag=asset_tag)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"Asset tag '{asset_tag}' already exists.")

        return asset_tag

    def clean_purchase_date(self):
        purchase_date = self.cleaned_data.get('purchase_date')
        if purchase_date:
            if purchase_date > date.today():
                raise ValidationError("Purchase date cannot be in the future.")

            # Check if too far in the past
            years_ago = date.today().year - purchase_date.year
            if years_ago > 50:
                raise ValidationError("Purchase date seems too far in the past.")

        return purchase_date

    def clean_warranty_expiry(self):
        warranty_expiry = self.cleaned_data.get('warranty_expiry')
        purchase_date = self.cleaned_data.get('purchase_date')

        if warranty_expiry and purchase_date:
            if warranty_expiry <= purchase_date:
                raise ValidationError("Warranty expiry must be after purchase date.")

        return warranty_expiry


class AssetMaintenanceForm(forms.ModelForm):
    class Meta:
        model = AssetMaintenance
        fields = [
            'asset', 'maintenance_type', 'performed_on', 'service_provider',
            'description', 'cost', 'next_due'
        ]
        widgets = {
            'asset': forms.Select(attrs={'class': 'form-control'}),
            'maintenance_type': forms.Select(attrs={'class': 'form-control'}),
            'performed_on': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'service_provider': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Service Provider'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Maintenance description'}),
            'cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'next_due': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['asset'].queryset = Asset.objects.all()
        self.fields['asset'].empty_label = "Select Asset"

    def clean_performed_on(self):
        performed_on = self.cleaned_data.get('performed_on')
        if performed_on:
            if performed_on > date.today():
                raise ValidationError("Maintenance date cannot be in the future.")

        return performed_on

    def clean_next_due(self):
        next_due = self.cleaned_data.get('next_due')
        performed_on = self.cleaned_data.get('performed_on')

        if next_due and performed_on:
            if next_due <= performed_on:
                raise ValidationError("Next due date must be after maintenance date.")

        return next_due


class AssetDamageForm(forms.ModelForm):
    class Meta:
        model = AssetDamage
        fields = [
            'asset', 'date_reported', 'description', 'severity',
            'repair_cost', 'is_total_loss', 'repair_completed', 'repair_date'
        ]
        widgets = {
            'asset': forms.Select(attrs={'class': 'form-control'}),
            'date_reported': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Damage description'}),
            'severity': forms.Select(attrs={'class': 'form-control'}),
            'repair_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'is_total_loss': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'repair_completed': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'repair_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['asset'].queryset = Asset.objects.all()
        self.fields['asset'].empty_label = "Select Asset"

    def clean_date_reported(self):
        date_reported = self.cleaned_data.get('date_reported')
        if date_reported:
            if date_reported > date.today():
                raise ValidationError("Date reported cannot be in the future.")

        return date_reported

    def clean_repair_date(self):
        repair_date = self.cleaned_data.get('repair_date')
        date_reported = self.cleaned_data.get('date_reported')

        if repair_date:
            if repair_date > date.today():
                raise ValidationError("Repair date cannot be in the future.")

            if date_reported and repair_date < date_reported:
                raise ValidationError("Repair date cannot be before damage report date.")

        return repair_date

    def clean(self):
        cleaned_data = super().clean()
        is_total_loss = cleaned_data.get('is_total_loss')
        repair_completed = cleaned_data.get('repair_completed')

        if is_total_loss and repair_completed:
            raise ValidationError("Asset cannot be both total loss and repaired.")

        return cleaned_data


# Quick Stock In/Out Forms (simplified for common operations)
class QuickStockInForm(forms.Form):
    item = forms.ModelChoiceField(
        queryset=InventoryItem.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Item"
    )
    quantity = forms.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal('0.001'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001'})
    )
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Supplier"
    )
    cost = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal('0.00'),
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'})
    )
    reference = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'PO/Invoice Reference'})
    )

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if not quantity or quantity <= 0:
            raise ValidationError("Quantity must be greater than 0.")
        return quantity


class QuickStockOutForm(forms.Form):
    item = forms.ModelChoiceField(
        queryset=InventoryItem.objects.filter(is_active=True, quantity__gt=0),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Item"
    )
    quantity = forms.DecimalField(
        max_digits=14,
        decimal_places=3,
        min_value=Decimal('0.001'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001', 'min': '0.001'})
    )
    department = forms.ModelChoiceField(
        queryset=DepartmentModel.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Department"
    )
    reference = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Request/Reference Number'})
    )

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        item = self.cleaned_data.get('item')

        if not quantity or quantity <= 0:
            raise ValidationError("Quantity must be greater than 0.")

        # Check if sufficient stock is available
        if item and quantity > item.quantity:
            raise ValidationError(f"Insufficient stock. Available: {item.quantity} {item.unit}")

        return quantity