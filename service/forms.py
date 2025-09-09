from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
import re

# Import your service models
from .models import ServiceCategory, Service, ServiceItem


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
    class Meta:
        model = Service
        fields = ['category', 'name', 'description', 'price', 'has_results', 'is_active']
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


class ServiceItemForm(forms.ModelForm):
    class Meta:
        model = ServiceItem
        fields = [
            'category', 'name', 'description', 'model_number', 'price', 'cost_price',
            'stock_quantity', 'minimum_stock_level', 'unit_of_measure',
            'expiry_date', 'is_prescription_required', 'is_active'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Panadol Extra'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'model_number': forms.TextInput(attrs={'class': 'form-control'}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'cost_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'stock_quantity': forms.NumberInput(attrs={'class': 'form-control'}),
            'minimum_stock_level': forms.NumberInput(attrs={'class': 'form-control'}),
            'unit_of_measure': forms.Select(attrs={'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_prescription_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
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
        price = cleaned_data.get('price')
        cost_price = cleaned_data.get('cost_price')

        if price is not None and cost_price is not None:
            if price < cost_price:
                self.add_error('price', "Selling price cannot be less than the cost price.")

        return cleaned_data