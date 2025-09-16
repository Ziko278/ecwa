import re
import json
from django.forms import ModelForm, Select, TextInput, DateInput, TimeInput, NumberInput, Textarea, CheckboxInput, \
    CheckboxSelectMultiple, FileInput, HiddenInput, modelformset_factory
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from datetime import date, datetime
from django import forms
from pharmacy.models import *


class DrugCategoryForm(ModelForm):
    """Form for drug categories"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    class Meta:
        model = DrugCategoryModel
        fields = '__all__'
        widgets = {
            'description': Textarea(attrs={
                'rows': 3,
                'placeholder': 'Enter category description...'
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = ' '.join(name.strip().split())
            if len(name) < 2:
                raise ValidationError("Category name must be at least 2 characters long.")

            # Check uniqueness (case-insensitive)
            existing = DrugCategoryModel.objects.filter(name__iexact=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"Category '{name}' already exists.")

        return name


class GenericDrugForm(ModelForm):
    """Form for generic drugs"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'is_prescription_only':
                self.fields[field].widget.attrs.update({
                    'class': 'form-control',
                    'autocomplete': 'off'
                })

    class Meta:
        model = GenericDrugModel
        fields = '__all__'
        widgets = {
            'atc_code': TextInput(attrs={
                'placeholder': 'e.g., N02BE01',
                'maxlength': '10'
            }),
            'is_prescription_only': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_generic_name(self):
        name = self.cleaned_data.get('generic_name')
        if name:
            name = ' '.join(name.strip().split())
            if len(name) < 2:
                raise ValidationError("Generic name must be at least 2 characters long.")

            # Check uniqueness (case-insensitive)
            existing = GenericDrugModel.objects.filter(generic_name__iexact=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"Generic drug '{name}' already exists.")

        return name

    # def clean_atc_code(self):
    #     code = self.cleaned_data.get('atc_code')
    #     if code:
    #         code = code.upper().strip()
    #         # Basic ATC code validation (letter + 2 digits + letter + letter + 2 digits)
    #         if not re.match(r'^[A-Z]\d{2}[A-Z]{2}\d{2}$', code):
    #             raise ValidationError("Invalid ATC code format. Expected format: A10BA02")
    #     return code


class DrugFormulationForm(ModelForm):
    """Form for drug formulations"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    class Meta:
        model = DrugFormulationModel
        fields = '__all__'
        widgets = {
            'strength': TextInput(attrs={
                'placeholder': 'e.g., 500mg, 250mg/5ml'
            }),
        }

    def clean_strength(self):
        strength = self.cleaned_data.get('strength')
        if strength:
            strength = strength.strip()
            if len(strength) < 2:
                raise ValidationError("Strength must be at least 2 characters long.")
        return strength

    def clean(self):
        cleaned_data = super().clean()
        generic_drug = cleaned_data.get('generic_drug')
        form_type = cleaned_data.get('form_type')
        strength = cleaned_data.get('strength')

        # Check uniqueness
        if generic_drug and form_type and strength:
            queryset = DrugFormulationModel.objects.filter(
                generic_drug=generic_drug,
                form_type=form_type,
                strength=strength
            )

            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                raise ValidationError(f"Formulation '{generic_drug} {strength} {form_type}' already exists.")

        return cleaned_data


class ManufacturerForm(ModelForm):
    """Form for manufacturers"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'is_approved':
                self.fields[field].widget.attrs.update({
                    'class': 'form-control',
                    'autocomplete': 'off'
                })

    class Meta:
        model = ManufacturerModel
        fields = '__all__'
        widgets = {
            'is_approved': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = ' '.join(name.strip().split())
            if len(name) < 2:
                raise ValidationError("Manufacturer name must be at least 2 characters long.")

            # Check uniqueness (case-insensitive)
            existing = ManufacturerModel.objects.filter(name__iexact=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"Manufacturer '{name}' already exists.")

        return name


class DrugOrderForm(ModelForm):
    """
    Form for creating new drug orders for patients.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply form-control to most fields
        for field_name in self.fields:
            # Skip specific fields if they need different styling or are read-only
            if field_name in ['ordered_by', 'patient', 'drug', 'status']:
                self.fields[field_name].widget.attrs.update({
                    'class': 'form-control',
                })
            elif field_name not in ['quantity_dispensed', 'dispensed_at', 'dispensed_by', 'order_number', 'ordered_at']:
                self.fields[field_name].widget.attrs.update({
                    'class': 'form-control',
                    'autocomplete': 'off'
                })

        # Customize widgets for specific fields
        self.fields['dosage_instructions'].widget = Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'e.g., Take 1 tablet twice daily after meals for 7 days.'
        })
        self.fields['notes'].widget = Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add any special notes or instructions here...'
        })
        self.fields['quantity_ordered'].widget = NumberInput(attrs={
            'class': 'form-control',
            'min': '0.01', # Ensure positive quantity
            'step': 'any' # Allow decimal quantities
        })
        self.fields['duration'].widget = TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 7 days, until finished, PRN'
        })
        # Set initial choices for User fields if needed, or let Django handle it
        # For 'ordered_by', you might filter users if only certain roles can order
        # self.fields['ordered_by'].queryset = User.objects.filter(is_staff=True) # Example filter

        # Make auto-generated/auto-updated fields read-only or exclude them
        # For a creation form, these fields are usually not present or are read-only
        if 'order_number' in self.fields:
            self.fields['order_number'].widget.attrs['readonly'] = True
        if 'ordered_at' in self.fields:
            self.fields['ordered_at'].widget.attrs['readonly'] = True
        if 'quantity_dispensed' in self.fields:
            self.fields['quantity_dispensed'].widget.attrs['readonly'] = True
        if 'dispensed_by' in self.fields:
            self.fields['dispensed_by'].widget.attrs['readonly'] = True
        if 'dispensed_at' in self.fields:
            self.fields['dispensed_at'].widget.attrs['readonly'] = True
        if 'status' in self.fields:
            self.fields['status'].widget.attrs['readonly'] = True

    class Meta:
        model = DrugOrderModel
        fields = [
            'patient',
            'drug',
            'quantity_ordered',
            'dosage_instructions',
            'consultation',
            'duration',
            'ordered_by', # Assuming this is manually assigned from a list of users
            'notes',
        ]
        # Exclude fields that are auto-generated or updated in separate steps
        # 'order_number', 'ordered_at', 'quantity_dispensed', 'dispensed_by', 'dispensed_at', 'status'

    def clean_quantity_ordered(self):
        quantity = self.cleaned_data.get('quantity_ordered')
        if quantity is not None and quantity <= 0:
            raise ValidationError("Quantity ordered must be a positive value.")
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        quantity_ordered = cleaned_data.get('quantity_ordered')
        drug = cleaned_data.get('drug')

        # Example of a more complex validation (e.g., checking available stock)
        # This might be more robustly done in the view/service layer during dispense.
        if drug and quantity_ordered:
            # You might want to check total_quantity on the DrugModel
            # However, for an *order*, the immediate stock isn't a hard blocker,
            # but it's a good place to warn or flag.
            # if drug.total_quantity < quantity_ordered:
            #     # This might be too strict for just an order form,
            #     # as stock can be replenished before dispense.
            #     # Consider this more for a 'dispense' form.
            #     self.add_error('quantity_ordered', "Ordered quantity exceeds available drug stock.")
            pass # Keep it simple for an order form
        return cleaned_data


class DrugForm(ModelForm):
    """Form for drug products"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Apply default widget attrs for most fields
        for field_name, field in self.fields.items():
            if field_name != 'is_active': # Skip is_active for default styling, it has its own widget
                if isinstance(field.widget, (TextInput, NumberInput)):
                    field.widget.attrs.update({
                        'class': 'form-control',
                        'autocomplete': 'off'
                    })
                elif isinstance(field.widget, forms.Select):
                    field.widget.attrs.update({
                        'class': 'form-control'
                    })
            # CheckboxInput for 'is_active' is handled by widgets dict

        # Filter active formulations and manufacturers
        try:
            self.fields['formulation'].queryset = DrugFormulationModel.objects.filter(
                status='active'
            ).select_related('generic_drug').order_by('generic_drug__generic_name', 'form_type', 'strength')

            self.fields['manufacturer'].queryset = ManufacturerModel.objects.filter(
                is_approved=True
            ).order_by('name')
        except Exception:
            # Handle cases where related models/objects might not exist yet (e.g., initial migration/run)
            pass

        # --- Conditional field removal for update operations ---
        if self.instance and self.instance.pk: # This is an update scenario
            if 'store_quantity' in self.fields:
                del self.fields['store_quantity']
            if 'pharmacy_quantity' in self.fields:
                del self.fields['pharmacy_quantity']
            # You might also want to remove 'created_by' here if it's set in form_valid
            # and not meant for direct editing.

    class Meta:
        model = DrugModel
        fields = '__all__' # Use '__all__' initially, then remove fields dynamically
        widgets = {
            'store_quantity': NumberInput(attrs={
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'pharmacy_quantity': NumberInput(attrs={
                'min': '0',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'minimum_stock_level': NumberInput(attrs={
                'min': '0',
                'placeholder': '10'
            }),
            'is_active': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def clean_sku(self):
        sku = self.cleaned_data.get('sku')
        if sku:
            sku = sku.strip().upper()
            if len(sku) < 3:
                raise ValidationError("SKU must be at least 3 characters long.")

            # Check uniqueness
            existing = DrugModel.objects.filter(sku=sku)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"SKU '{sku}' already exists.")

        return sku

    def clean_store_quantity(self):
        # This clean method will only be called if 'store_quantity' is in self.fields
        quantity = self.cleaned_data.get('store_quantity')
        if quantity is not None and quantity < 0:
            raise ValidationError("Store quantity cannot be negative.")
        return quantity

    def clean_pharmacy_quantity(self):
        # This clean method will only be called if 'pharmacy_quantity' is in self.fields
        quantity = self.cleaned_data.get('pharmacy_quantity')
        if quantity is not None and quantity < 0:
            raise ValidationError("Pharmacy quantity cannot be negative.")
        return quantity

    def clean_minimum_stock_level(self):
        level = self.cleaned_data.get('minimum_stock_level')
        if level is not None and level < 0:
            raise ValidationError("Minimum stock level cannot be negative.")
        return level

    def clean(self):
        cleaned_data = super().clean()
        formulation = cleaned_data.get('formulation')
        manufacturer = cleaned_data.get('manufacturer')

        # Check unique combination of formulation and manufacturer
        if formulation and manufacturer:
            queryset = DrugModel.objects.filter(
                formulation=formulation,
                manufacturer=manufacturer
            )

            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)

            if queryset.exists():
                # Add a non-field error for unique combination constraint
                self.add_error(
                    None,
                    f"A drug product with formulation '{formulation}' and manufacturer '{manufacturer}' already exists."
                )

        return cleaned_data


class DrugBatchForm(ModelForm):
    """Form for drug batches"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    class Meta:
        model = DrugBatchModel
        fields = ['name', 'date']
        widgets = {
            'date': DateInput(attrs={
                'type': 'date'
            }),
        }

    def clean_date(self):
        batch_date = self.cleaned_data.get('date')
        if batch_date and batch_date > date.today():
            raise ValidationError("Batch date cannot be in the future.")
        return batch_date

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip().lower()
            if len(name) < 2:
                raise ValidationError("Batch name must be at least 2 characters long.")

            # Check uniqueness if manually provided
            existing = DrugBatchModel.objects.filter(name=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)

            if existing.exists():
                raise ValidationError(f"Batch '{name}' already exists.")

        return name


class DrugStockForm(ModelForm):
    class Meta:
        model = DrugStockModel
        fields = ['drug', 'batch', 'quantity_bought', 'unit_cost_price', 'selling_price', 'location', 'expiry_date']
        widgets = {
            'expiry_date': forms.DateInput(attrs={'type': 'date'}),
            'batch': forms.HiddenInput(),  # Hidden since we'll set it in view
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if field.widget.__class__.__name__ != 'HiddenInput':
                field.widget.attrs.update({'class': 'form-control'})


# Create formset with extra=1 so you get at least one form
DrugStockFormSet = modelformset_factory(
    DrugStockModel,
    form=DrugStockForm,
    extra=1,  # Start with 1 form
    can_delete=False,
)


class DrugStockOutForm(ModelForm):
    """Form for drug stock out entries"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

        # Filter active stock entries with quantity left
        try:
            self.fields['stock'].queryset = DrugStockModel.objects.filter(
                quantity_left__gt=0,
                status='active'
            ).select_related('drug__formulation__generic_drug')
        except Exception:
            pass

    class Meta:
        model = DrugStockOutModel
        fields = ['stock', 'quantity', 'reason', 'remark']
        widgets = {
            'quantity': NumberInput(attrs={
                'min': '0.01',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'remark': Textarea(attrs={
                'rows': 2,
                'placeholder': 'Additional remarks...'
            }),
        }

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity and quantity <= 0:
            raise ValidationError("Quantity must be greater than zero.")
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        stock = cleaned_data.get('stock')
        quantity = cleaned_data.get('quantity')

        if stock and quantity:
            if quantity > stock.quantity_left:
                raise ValidationError(f"Cannot remove {quantity}. Only {stock.quantity_left} available in stock.")

        return cleaned_data


class DrugTransferForm(ModelForm):
    """Form for drug transfers from store to pharmacy"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

        # Filter drugs with store quantity > 0
        try:
            self.fields['drug'].queryset = DrugModel.objects.filter(
                store_quantity__gt=0,
                is_active=True
            ).select_related('formulation__generic_drug', 'manufacturer')
        except Exception:
            pass

    class Meta:
        model = DrugTransferModel
        fields = ['drug', 'quantity', 'notes']
        widgets = {
            'quantity': NumberInput(attrs={
                'min': '0.01',
                'step': '0.01',
                'placeholder': '0.00'
            }),
            'notes': Textarea(attrs={
                'rows': 2,
                'placeholder': 'Transfer notes...'
            }),
        }

    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity and quantity <= 0:
            raise ValidationError("Transfer quantity must be greater than zero.")
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        drug = cleaned_data.get('drug')
        quantity = cleaned_data.get('quantity')

        if drug and quantity:
            if quantity > drug.store_quantity:
                raise ValidationError(f"Cannot transfer {quantity}. Only {drug.store_quantity} available in store.")

        return cleaned_data


class DrugTransferFilterForm(forms.Form):
    """
    Form for filtering DrugTransferModel instances.
    """
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='From Date'
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='To Date'
    )
    drug = forms.ModelChoiceField(
        queryset=DrugModel.objects.all().order_by('brand_name'), # Assuming DrugModel has 'brand_name'
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Drug Name'
    )
    transferred_by = forms.ModelChoiceField(
        # The queryset for this field is set dynamically in __init__
        queryset=User.objects.none(), # Start with an empty queryset
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Transferred By'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically set the queryset for 'transferred_by' to only include users with transfers
        self.fields['transferred_by'].queryset = User.objects.filter(
            id__in=DrugTransferModel.objects.values_list('transferred_by', flat=True).distinct()
        ).order_by('username')
        # Add default "All" options for ModelChoiceFields
        self.fields['transferred_by'].empty_label = "All Users"
        self.fields['drug'].empty_label = "All Drugs"



class PharmacySettingForm(ModelForm):
    """Form for pharmacy settings"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field != 'drug_sale_without_prescription':
                self.fields[field].widget.attrs.update({
                    'class': 'form-control',
                    'autocomplete': 'off'
                })

    class Meta:
        model = PharmacySettingModel
        fields = '__all__'
        widgets = {
            'drug_sale_without_prescription': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'auto_transfer_threshold': NumberInput(attrs={
                'min': '1',
                'max': '100',
                'placeholder': 'Minimum quantity'
            }),
        }

    def clean_auto_transfer_threshold(self):
        threshold = self.cleaned_data.get('auto_transfer_threshold')
        if threshold and threshold < 1:
            raise ValidationError("Auto transfer threshold must be at least 1.")
        return threshold


class DrugTemplateForm(ModelForm):
    """Form for drug templates"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['is_prescription', 'drug_combinations']:
                self.fields[field].widget.attrs.update({
                    'class': 'form-control',
                    'autocomplete': 'off'
                })

    class Meta:
        model = DrugTemplateModel
        fields = ['name', 'generic_name', 'category', 'is_prescription', 'drug_combinations']
        widgets = {
            'is_prescription': CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'drug_combinations': Textarea(attrs={
                'rows': 8,
                'placeholder': '''[
  {"strength": "500mg", "form": "tablet", "manufacturer": "GSK"},
  {"strength": "250mg", "form": "syrup", "manufacturer": "Emzor"}
]'''
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            if len(name) < 3:
                raise ValidationError("Template name must be at least 3 characters long.")
        return name

    def clean_generic_name(self):
        name = self.cleaned_data.get('generic_name')
        if name:
            name = ' '.join(name.strip().split())
            if len(name) < 2:
                raise ValidationError("Generic name must be at least 2 characters long.")
        return name

    def clean_drug_combinations(self):
        combinations = self.cleaned_data.get('drug_combinations')

        if not combinations:
            raise ValidationError("Drug combinations cannot be empty.")

        # Validate JSON structure
        if isinstance(combinations, str):
            try:
                combinations = json.loads(combinations)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format for drug combinations.")

        if not isinstance(combinations, list) or len(combinations) == 0:
            raise ValidationError("Drug combinations must be a non-empty array.")

        # Validate each combination
        valid_forms = [choice[0] for choice in DrugFormulationModel.FORM_CHOICES]
        for i, combo in enumerate(combinations):
            if not isinstance(combo, dict):
                raise ValidationError(f"Combination {i + 1} must be an object.")

            required_fields = ['strength', 'form', 'manufacturer']
            for field in required_fields:
                if field not in combo or not combo[field]:
                    raise ValidationError(f"Combination {i + 1} missing required field: {field}")

            if combo['form'] not in valid_forms:
                raise ValidationError(
                    f"Invalid form '{combo['form']}' in combination {i + 1}. Valid forms: {valid_forms}")

        return combinations


class DrugImportLogForm(ModelForm):
    """Form for drug import logs"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'autocomplete': 'off'
            })

    class Meta:
        model = DrugImportLogModel
        fields = ['import_file']
        widgets = {
            'import_file': FileInput(attrs={
                'accept': '.csv,.xlsx,.xls'
            }),
        }

    def clean_import_file(self):
        file = self.cleaned_data.get('import_file')
        if file:
            # Validate file extension
            valid_extensions = ['.csv', '.xlsx', '.xls']
            file_extension = '.' + file.name.split('.')[-1].lower()

            if file_extension not in valid_extensions:
                raise ValidationError(f"Invalid file type. Allowed types: {', '.join(valid_extensions)}")

            # Validate file size (max 10MB)
            if file.size > 10 * 1024 * 1024:
                raise ValidationError("File size cannot exceed 10MB.")

        return file


# Quick action forms
class QuickStockUpdateForm(forms.Form):
    """Quick form for updating stock quantities"""
    drug_id = forms.IntegerField(widget=HiddenInput())
    store_quantity = forms.FloatField(
        min_value=0,
        widget=NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00'
        })
    )
    pharmacy_quantity = forms.FloatField(
        min_value=0,
        widget=NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00'
        })
    )


class QuickTransferForm(forms.Form):
    """Quick form for drug transfers"""
    drug_id = forms.IntegerField(widget=HiddenInput())
    quantity = forms.FloatField(
        min_value=0.01,
        widget=NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Quantity to transfer'
        })
    )
    notes = forms.CharField(
        required=False,
        widget=TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Transfer notes...'
        })
    )


class StockAlertForm(forms.Form):
    """Form for setting up stock alerts"""
    drug_id = forms.IntegerField(widget=HiddenInput())
    minimum_stock_level = forms.IntegerField(
        min_value=0,
        widget=NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Minimum stock level'
        })
    )


class BulkStatusUpdateForm(forms.Form):
    """Form for bulk status updates"""
    drug_ids = forms.CharField(widget=HiddenInput())
    status = forms.ChoiceField(
        choices=[('active', 'Active'), ('inactive', 'Inactive')],
        widget=Select(attrs={'class': 'form-control'})
    )


# Search and filter forms
class DrugSearchForm(forms.Form):
    """Advanced drug search form"""
    search_term = forms.CharField(
        required=False,
        widget=TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search drugs by name, brand, or SKU...'
        })
    )
    category = forms.ModelChoiceField(
        queryset=DrugCategoryModel.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=Select(attrs={'class': 'form-control'})
    )
    manufacturer = forms.ModelChoiceField(
        queryset=ManufacturerModel.objects.all(),
        required=False,
        empty_label="All Manufacturers",
        widget=Select(attrs={'class': 'form-control'})
    )
    form_type = forms.ChoiceField(
        choices=[('', 'All Forms')] + DrugFormulationModel.FORM_CHOICES,
        required=False,
        widget=Select(attrs={'class': 'form-control'})
    )
    stock_status = forms.ChoiceField(
        choices=[
            ('', 'All Stock'),
            ('in_stock', 'In Stock'),
            ('low_stock', 'Low Stock'),
            ('out_of_stock', 'Out of Stock')
        ],
        required=False,
        widget=Select(attrs={'class': 'form-control'})
    )
    is_active = forms.ChoiceField(
        choices=[('', 'All Status'), ('true', 'Active'), ('false', 'Inactive')],
        required=False,
        widget=Select(attrs={'class': 'form-control'})
    )


class StockReportForm(forms.Form):
    """Form for generating stock reports"""
    report_type = forms.ChoiceField(
        choices=[
            ('current_stock', 'Current Stock Level'),
            ('low_stock', 'Low Stock Items'),
            ('expired', 'Expired Items'),
            ('near_expiry', 'Near Expiry Items'),
            ('stock_movement', 'Stock Movement'),
        ],
        widget=Select(attrs={'class': 'form-control'})
    )
    date_from = forms.DateField(
        required=False,
        widget=DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    date_to = forms.DateField(
        required=False,
        widget=DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    format = forms.ChoiceField(
        choices=[('pdf', 'PDF'), ('excel', 'Excel'), ('csv', 'CSV')],
        widget=Select(attrs={'class': 'form-control'})
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        report_type = cleaned_data.get('report_type')

        # Validate date range for stock movement reports
        if report_type == 'stock_movement':
            if not date_from or not date_to:
                raise ValidationError("Date range is required for stock movement reports.")

            if date_from > date_to:
                raise ValidationError("Start date must be before end date.")

            if date_to > date.today():
                raise ValidationError("End date cannot be in the future.")

        return cleaned_data