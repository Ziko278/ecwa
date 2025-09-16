from datetime import date

from django import forms
from django.core.exceptions import ValidationError
from django.forms import modelformset_factory
from django.utils import timezone
from django.contrib.auth.models import User
import re
import json

# Import your service models
from service.models import (
    ServiceCategory, Service, ServiceItem, PatientServiceTransaction,
    ServiceItemStockMovement, ServiceResult, ServiceItemBatch
)
from patient.models import PatientModel


class ServiceCategoryForm(forms.ModelForm):
    class Meta:
        model = ServiceCategory
        fields = ['name', 'description', 'show_as_record_column', 'category_type', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Laboratory Services'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'category_type': forms.Select(attrs={'class': 'form-control'}),
            'show_as_record_column': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Category name is required.")

        # Sanitize input
        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Category name must be at least 2 characters long.")

        # Check for invalid characters
        if not re.match(r'^[a-zA-Z0-9\s\-&/]+$', name):
            raise ValidationError("Category name contains invalid characters.")

        # Check for uniqueness (case-insensitive)
        existing = ServiceCategory.objects.filter(name__iexact=name)
        if self.instance.pk:
            existing = existing.exclude(pk=self.instance.pk)

        if existing.exists():
            raise ValidationError(f"A service category named '{name}' already exists.")

        return name


class ServiceForm(forms.ModelForm):
    result_template = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Enter JSON template for results'}),
        help_text="JSON template for recording results (only if service has results)"
    )

    class Meta:
        model = Service
        fields = ['category', 'name', 'description', 'price', 'has_results', 'result_template', 'is_active']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Full Blood Count'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'has_results': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter categories to active ones suitable for services
        self.fields['category'].queryset = ServiceCategory.objects.filter(
            is_active=True, category_type__in=['service', 'mixed']
        )
        self.fields['category'].empty_label = "Select a Category"

        # Pre-populate result_template if editing
        if self.instance.pk and self.instance.result_template:
            self.fields['result_template'].initial = json.dumps(self.instance.result_template, indent=2)

    def clean_name(self):
        name = self.cleaned_data.get('name')
        category = self.cleaned_data.get('category')

        if not name:
            raise ValidationError("Service name is required.")

        name = ' '.join(name.strip().split())
        if len(name) < 2:
            raise ValidationError("Service name must be at least 2 characters long.")

        # Check for uniqueness within the same category
        if category:
            existing = Service.objects.filter(name__iexact=name, category=category)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"The service '{name}' already exists in the '{category.name}' category.")

        return name

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise ValidationError("Price cannot be negative.")
        return price

    def clean_result_template(self):
        result_template = self.cleaned_data.get('result_template')
        has_results = self.cleaned_data.get('has_results')

        if has_results and result_template:
            try:
                # Validate JSON format
                json.loads(result_template)
                return json.loads(result_template)
            except json.JSONDecodeError:
                raise ValidationError("Result template must be valid JSON format.")

        return None if not has_results else result_template

    def clean(self):
        cleaned_data = super().clean()
        has_results = cleaned_data.get('has_results')
        result_template = cleaned_data.get('result_template')

        if has_results and not result_template:
            self.add_error('result_template', "Result template is required when service has results.")

        return cleaned_data


class ServiceItemForm(forms.ModelForm):
    class Meta:
        model = ServiceItem
        fields = [
            'category', 'name', 'description', 'price', 'cost_price',
            'stock_quantity', 'minimum_stock_level', 'unit_of_measure',
            'expiry_date', 'is_active'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Panadol Extra'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'minimum_stock_level': forms.NumberInput(attrs={'class': 'form-control'}),
            'unit_of_measure': forms.Select(attrs={'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter categories to active ones suitable for items
        self.fields['category'].queryset = ServiceCategory.objects.filter(
            is_active=True, category_type__in=['item', 'mixed']
        )
        self.fields['category'].empty_label = "Select a Category"

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not name:
            raise ValidationError("Item name is required.")
        return ' '.join(name.strip().split())

    def clean_price(self):
        price = self.cleaned_data.get('price')
        if price is not None and price < 0:
            raise ValidationError("Price cannot be negative.")
        return price

    def clean_cost_price(self):
        cost_price = self.cleaned_data.get('cost_price')
        if cost_price is not None and cost_price < 0:
            raise ValidationError("Cost price cannot be negative.")
        return cost_price

    def clean_stock_quantity(self):
        stock = self.cleaned_data.get('stock_quantity')
        if stock is not None and stock < 0:
            raise ValidationError("Stock quantity cannot be negative.")
        return stock

    def clean_minimum_stock_level(self):
        min_stock = self.cleaned_data.get('minimum_stock_level')
        if min_stock is not None and min_stock < 0:
            raise ValidationError("Minimum stock level cannot be negative.")
        return min_stock

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')
        if expiry_date and expiry_date < timezone.now().date():
            raise ValidationError("Expiry date cannot be in the past.")
        return expiry_date

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        name = cleaned_data.get('name')
        price = cleaned_data.get('price')
        cost_price = cleaned_data.get('cost_price')

        # Check uniqueness
        if category and name:
            existing = ServiceItem.objects.filter(
                category=category,
                name__iexact=name,
            )
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError("This item already exists in this category.")

        # Price validation
        if price is not None and cost_price is not None:
            if price < cost_price:
                self.add_error('price', "Selling price cannot be less than the cost price.")

        return cleaned_data


class ServiceItemBatchForm(forms.ModelForm):
    """Form for service item batches"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply 'form-control' and autocomplete 'off' to all fields
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    class Meta:
        model = ServiceItemBatch
        fields = ['name', 'date']
        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date'
            }),
        }
        help_texts = {
            'name': 'Optional. Leave blank to auto-generate a name like BATCH-0001.',
        }

    def clean_date(self):
        batch_date = self.cleaned_data.get('date')
        if batch_date and batch_date > date.today():
            raise ValidationError("Batch date cannot be in the future.")
        return batch_date

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            # Clean and normalize the manually entered name
            name = name.strip().upper() # Changed to upper to match __str__
            if len(name) < 2:
                raise ValidationError("Batch name must be at least 2 characters long.")

            # Check uniqueness if manually provided
            # Replaced DrugBatchModel with ServiceItemBatch
            existing = ServiceItemBatch.objects.filter(name=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"Batch '{name}' already exists.")

        return name


class PatientServiceTransactionForm(forms.ModelForm):
    patient = forms.ModelChoiceField(
        queryset=PatientModel.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Patient"
    )

    class Meta:
        model = PatientServiceTransaction
        # UPDATED: Replaced 'payment_status' and removed 'amount_paid'
        fields = [
            'patient', 'service', 'service_item', 'quantity', 'unit_price', 'discount',
            'status', 'consultation', 'admission', 'surgery',
            'performed_by', 'notes'
        ]
        widgets = {
            'service': forms.Select(attrs={'class': 'form-control'}),
            'service_item': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'discount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}), # Replaced payment_status
            'consultation': forms.HiddenInput(), # Assuming these are set programmatically
            'admission': forms.HiddenInput(),
            'surgery': forms.HiddenInput(),
            'performed_by': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter active services and items
        self.fields['service'].queryset = Service.objects.filter(is_active=True)
        self.fields['service_item'].queryset = ServiceItem.objects.filter(is_active=True)
        self.fields['performed_by'].queryset = User.objects.filter(is_active=True)

        # Make service and service_item not required (one will be selected)
        self.fields['service'].required = False
        self.fields['service_item'].required = False
        self.fields['service'].empty_label = "Select Service"
        self.fields['service_item'].empty_label = "Select Item"
        self.fields['performed_by'].empty_label = "Select Performer"

    # clean_quantity, clean_unit_price, and clean_discount methods remain the same

    def clean(self):
        cleaned_data = super().clean()
        service = cleaned_data.get('service')
        service_item = cleaned_data.get('service_item')
        quantity = cleaned_data.get('quantity')
        unit_price = cleaned_data.get('unit_price')
        discount = cleaned_data.get('discount')

        # Ensure either service or service_item is selected
        if not service and not service_item:
            raise ValidationError("Please select either a service or an item.")
        if service and service_item:
            raise ValidationError("Please select either a service or an item, not both.")

        # Check stock availability for items
        if service_item and quantity:
            # Note: With the new workflow, stock isn't deducted on creation,
            # but checking availability here is still good practice to prevent billing for out-of-stock items.
            if service_item.stock_quantity < quantity:
                self.add_error('quantity',
                               f"Only {service_item.stock_quantity} {service_item.get_unit_of_measure_display()}(s) available in stock.")

        # Validate pricing
        if unit_price is not None and discount is not None and quantity:
            subtotal = unit_price * quantity
            if discount > subtotal:
                self.add_error('discount', "Discount cannot be greater than the subtotal.")

        # REMOVED: The old validation for payment_status and amount_paid is no longer needed here.

        return cleaned_data


class ServiceItemStockMovementForm(forms.ModelForm):
    class Meta:
        model = ServiceItemStockMovement
        fields = [
            'service_item', 'movement_type', 'quantity', 'unit_cost',
            'reference_type', 'reference_id', 'batch_number', 'expiry_date', 'notes'
        ]
        widgets = {
            'service_item': forms.Select(attrs={'class': 'form-control'}),
            'movement_type': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'reference_type': forms.Select(attrs={'class': 'form-control'}),
            'reference_id': forms.NumberInput(attrs={'class': 'form-control'}),
            'batch_number': forms.TextInput(attrs={'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service_item'].queryset = ServiceItem.objects.filter(is_active=True)
        self.fields['service_item'].empty_label = "Select Item"
        self.fields['reference_type'].required = False
        self.fields['reference_id'].required = False

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        movement_type = self.cleaned_data.get('movement_type')

        if quantity == 0:
            raise ValidationError("Quantity cannot be zero.")

        # For stock_out movements, quantity should be negative
        if movement_type in ['stock_out', 'sale', 'expired'] and quantity > 0:
            quantity = -quantity
        # For stock_in movements, quantity should be positive
        elif movement_type in ['stock_in', 'return'] and quantity < 0:
            quantity = abs(quantity)

        return quantity

    def clean_unit_cost(self):
        unit_cost = self.cleaned_data.get('unit_cost')
        movement_type = self.cleaned_data.get('movement_type')

        if movement_type == 'stock_in' and not unit_cost:
            raise ValidationError("Unit cost is required for stock-in movements.")

        if unit_cost is not None and unit_cost < 0:
            raise ValidationError("Unit cost cannot be negative.")

        return unit_cost

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')
        if expiry_date and expiry_date < timezone.now().date():
            raise ValidationError("Expiry date cannot be in the past.")
        return expiry_date

    def clean(self):
        cleaned_data = super().clean()
        service_item = cleaned_data.get('service_item')
        quantity = cleaned_data.get('quantity')
        movement_type = cleaned_data.get('movement_type')

        # Check if there's enough stock for outbound movements
        if service_item and quantity and movement_type in ['stock_out', 'sale', 'expired']:
            available_stock = service_item.stock_quantity
            required_quantity = abs(quantity)

            if required_quantity > available_stock:
                self.add_error('quantity',
                               f"Only {available_stock} {service_item.unit_of_measure}(s) available in stock.")

        return cleaned_data


class ServiceResultForm(forms.ModelForm):
    result_data = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 6}),
        help_text="Enter result data in JSON format or use the service template"
    )

    class Meta:
        model = ServiceResult
        fields = ['transaction', 'result_data', 'result_file', 'is_abnormal', 'interpretation']
        widgets = {
            'transaction': forms.Select(attrs={'class': 'form-control'}),
            'result_file': forms.FileInput(attrs={'class': 'form-control'}),
            'is_abnormal': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'interpretation': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show transactions for services that have results
        self.fields['transaction'].queryset = PatientServiceTransaction.objects.filter(
            service__has_results=True,
            service__isnull=False
        ).select_related('service', 'patient')

        # Pre-populate with service template if available
        if self.instance.pk and self.instance.result_data:
            self.fields['result_data'].initial = json.dumps(self.instance.result_data, indent=2)

    def clean_result_data(self):
        result_data = self.cleaned_data.get('result_data')
        try:
            return json.loads(result_data)
        except json.JSONDecodeError:
            raise ValidationError("Result data must be valid JSON format.")

class QuickTransactionForm(forms.Form):
    """Simplified form for quick service/item transactions"""
    patient = forms.ModelChoiceField(
        queryset=PatientModel.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Patient"
    )
    category = forms.ModelChoiceField(
        queryset=ServiceCategory.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Category"
    )
    item_type = forms.ChoiceField(
        choices=[('service', 'Service'), ('item', 'Item')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    service_or_item = forms.CharField(
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Will be populated based on category and type selection"
    )
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    # REMOVED: The payment_status field is no longer needed here.
    # The view will handle setting the status to 'pending_payment'.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['service_or_item'].widget = forms.Select(attrs={'class': 'form-control'})


class BulkTransactionForm(forms.Form):
    """Form for processing multiple transactions at once"""
    patient = forms.ModelChoiceField(
        queryset=PatientModel.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Patient"
    )
    consultation_id = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    services = forms.ModelMultipleChoiceField(
        queryset=Service.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    items_data = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        help_text="JSON data for items and their quantities"
    )

    notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False
    )

    def clean_items_data(self):
        items_data = self.cleaned_data.get('items_data')
        if items_data:
            try:
                return json.loads(items_data)
            except json.JSONDecodeError:
                raise ValidationError("Invalid items data format.")
        return []


class AddStockToBatchForm(forms.ModelForm):
    """A single form for adding one item to a stock-in batch."""
    class Meta:
        model = ServiceItemStockMovement
        fields = [
            'service_item', 'quantity', 'unit_cost',
            'batch_number', 'expiry_date', 'notes'
        ]
        widgets = {
            'service_item': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control'}),
            'batch_number': forms.TextInput(attrs={'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 1}),
        }


# Create a FormSet using the form above
ServiceItemStockMovementFormSet = modelformset_factory(
    ServiceItemStockMovement,
    form=AddStockToBatchForm,
    extra=1, # Start with one empty form
    can_delete=False
)