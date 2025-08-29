import logging
import json
from decimal import Decimal
from datetime import date, datetime, timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q, Sum, F, Count
from django.db.models.functions import Lower
from django.forms import modelformset_factory
from django.http import JsonResponse, HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils.timezone import now
from django.views import View
from django.views.generic import (
    CreateView, ListView, UpdateView, DeleteView, DetailView, TemplateView
)

from pharmacy.forms import (
    DrugCategoryForm, GenericDrugForm, DrugFormulationForm, ManufacturerForm,
    DrugForm, DrugBatchForm, DrugStockForm, DrugStockOutForm, DrugTransferForm,
    PharmacySettingForm, DrugTemplateForm, DrugImportLogForm, DrugSearchForm,
    StockReportForm, QuickStockUpdateForm, QuickTransferForm, StockAlertForm,
    BulkStatusUpdateForm, DrugStockFormSet, DrugTransferFilterForm
)
from pharmacy.models import (
    DrugCategoryModel, GenericDrugModel, DrugFormulationModel, ManufacturerModel,
    DrugModel, DrugBatchModel, DrugStockModel, DrugStockOutModel, DrugTransferModel,
    PharmacySettingModel, DrugTemplateModel, DrugImportLogModel
)

logger = logging.getLogger(__name__)


# -------------------------
# Utility helpers
# -------------------------
def get_pharmacy_setting_instance():
    """Return the singleton PharmacySettingModel instance (or None)."""
    return PharmacySettingModel.objects.first()


def get_low_stock_drugs():
    """Get drugs with low stock levels"""
    return DrugModel.objects.filter(
        is_active=True
    ).annotate(
        total_stock=F('store_quantity') + F('pharmacy_quantity')
    ).filter(
        total_stock__lte=F('minimum_stock_level')
    )


def get_expired_stock():
    """Get expired stock entries"""
    return DrugStockModel.objects.filter(
        expiry_date__lte=date.today(),
        status='active',
        quantity_left__gt=0
    )


def get_near_expiry_stock(days=30):
    """Get stock entries expiring within specified days"""
    future_date = date.today() + timedelta(days=days)
    return DrugStockModel.objects.filter(
        expiry_date__lte=future_date,
        expiry_date__gt=date.today(),
        status='active',
        quantity_left__gt=0
    )


# -------------------------
# Mixins
# -------------------------
class FlashFormErrorsMixin:
    """
    Mixin for CreateView/UpdateView to flash form errors and redirect safely.
    """

    def form_invalid(self, form):
        try:
            for field, errors in form.errors.items():
                label = form.fields.get(field).label if form.fields.get(field) else field
                for error in errors:
                    messages.error(self.request, f"{label}: {error}")
        except Exception:
            logger.exception("Error while processing form_invalid errors.")
            messages.error(self.request, "There was an error processing the form. Please try again.")
        return redirect(self.get_success_url())


class PharmacyContextMixin:
    """Mixin to add common pharmacy context."""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pharmacy_setting'] = get_pharmacy_setting_instance()
        context['low_stock_count'] = get_low_stock_drugs().count()
        context['expired_stock_count'] = get_expired_stock().count()
        context['near_expiry_count'] = get_near_expiry_stock().count()
        return context


# -------------------------
# Drug Category Views
# -------------------------
class DrugCategoryCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = DrugCategoryModel
    permission_required = 'pharmacy.add_drugcategorymodel'
    form_class = DrugCategoryForm
    template_name = 'pharmacy/category/index.html'
    success_message = 'Drug Category Successfully Created'

    def get_success_url(self):
        return reverse('drug_category_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('drug_category_index'))
        return super().dispatch(request, *args, **kwargs)


class DrugCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = DrugCategoryModel
    permission_required = 'pharmacy.view_drugcategorymodel'
    template_name = 'pharmacy/category/index.html'
    context_object_name = "category_list"

    def get_queryset(self):
        return DrugCategoryModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = DrugCategoryForm()
        return context


class DrugCategoryUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = DrugCategoryModel
    permission_required = 'pharmacy.change_drugcategorymodel'
    form_class = DrugCategoryForm
    template_name = 'pharmacy/category/index.html'
    success_message = 'Drug Category Successfully Updated'

    def get_success_url(self):
        return reverse('drug_category_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('drug_category_index'))
        return super().dispatch(request, *args, **kwargs)


class DrugCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = DrugCategoryModel
    permission_required = 'pharmacy.delete_drugcategorymodel'
    template_name = 'pharmacy/category/delete.html'
    context_object_name = "category"
    success_message = 'Drug Category Successfully Deleted'

    def get_success_url(self):
        return reverse('drug_category_index')


# -------------------------
# Manufacturer Views
# -------------------------
class ManufacturerCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = ManufacturerModel
    permission_required = 'pharmacy.add_manufacturermodel'
    form_class = ManufacturerForm
    template_name = 'pharmacy/manufacturer/index.html'
    success_message = 'Manufacturer Successfully Created'

    def get_success_url(self):
        return reverse('manufacturer_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('manufacturer_index'))
        return super().dispatch(request, *args, **kwargs)


class ManufacturerListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ManufacturerModel
    permission_required = 'pharmacy.view_manufacturermodel'
    template_name = 'pharmacy/manufacturer/index.html'
    context_object_name = "manufacturer_list"

    def get_queryset(self):
        return ManufacturerModel.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ManufacturerForm()
        return context


class ManufacturerUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
):
    model = ManufacturerModel
    permission_required = 'pharmacy.change_manufacturermodel'
    form_class = ManufacturerForm
    template_name = 'pharmacy/manufacturer/index.html'
    success_message = 'Manufacturer Successfully Updated'

    def get_success_url(self):
        return reverse('manufacturer_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('manufacturer_index'))
        return super().dispatch(request, *args, **kwargs)


class ManufacturerDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ManufacturerModel
    permission_required = 'pharmacy.delete_manufacturermodel'
    template_name = 'pharmacy/manufacturer/delete.html'
    context_object_name = "manufacturer"
    success_message = 'Manufacturer Successfully Deleted'

    def get_success_url(self):
        return reverse('manufacturer_index')


# -------------------------
# Generic Drug Views
# -------------------------
class GenericDrugCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, CreateView
):
    model = GenericDrugModel
    permission_required = 'pharmacy.add_genericdrugmodel'
    form_class = GenericDrugForm
    template_name = 'pharmacy/generic_drug/create.html'
    success_message = 'Generic Drug Successfully Created'

    def get_success_url(self):
        return reverse('generic_drug_detail', kwargs={'pk': self.object.pk})


class GenericDrugListView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, ListView):
    model = GenericDrugModel
    permission_required = 'pharmacy.view_genericdrugmodel'
    template_name = 'pharmacy/generic_drug/index.html'
    context_object_name = "generic_drug_list"
    paginate_by = 20

    def get_queryset(self):
        return GenericDrugModel.objects.select_related('category').order_by('generic_name')


class GenericDrugDetailView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, DetailView):
    model = GenericDrugModel
    permission_required = 'pharmacy.view_genericdrugmodel'
    template_name = 'pharmacy/generic_drug/detail.html'
    context_object_name = "generic_drug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        generic_drug = self.object

        # Related formulations and products
        formulations = DrugFormulationModel.objects.filter(
            generic_drug=generic_drug, status='active'
        ).order_by('form_type', 'strength')

        products = DrugModel.objects.filter(
            formulation__generic_drug=generic_drug, is_active=True
        ).select_related('formulation', 'manufacturer').order_by('brand_name')

        context.update({
            'formulations': formulations,
            'products': products,
            'formulation_count': formulations.count(),
            'product_count': products.count(),
        })
        return context


class GenericDrugUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, UpdateView
):
    model = GenericDrugModel
    permission_required = 'pharmacy.change_genericdrugmodel'
    form_class = GenericDrugForm
    template_name = 'pharmacy/generic_drug/update.html'
    context_object_name = "generic_drug"

    success_message = 'Generic Drug Successfully Updated'

    def get_success_url(self):
        return reverse('generic_drug_detail', kwargs={'pk': self.object.pk})


class GenericDrugDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = GenericDrugModel
    permission_required = 'pharmacy.delete_genericdrugmodel'
    template_name = 'pharmacy/generic_drug/delete.html'
    context_object_name = "generic_drug"
    success_message = 'Generic Drug Successfully Deleted'

    def get_success_url(self):
        return reverse('generic_drug_index')


# -------------------------
# Drug Formulation Views
# -------------------------
class DrugFormulationCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, CreateView
):
    model = DrugFormulationModel
    permission_required = 'pharmacy.add_drugformulationmodel'
    form_class = DrugFormulationForm
    template_name = 'pharmacy/formulation/create.html'
    success_message = 'Drug Formulation Successfully Created'

    def get_success_url(self):
        return reverse('drug_formulation_detail', kwargs={'pk': self.object.pk})


class DrugFormulationListView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, ListView):
    model = DrugFormulationModel
    permission_required = 'pharmacy.view_drugformulationmodel'
    template_name = 'pharmacy/formulation/index.html'
    context_object_name = "formulation_list"
    paginate_by = 20

    def get_queryset(self):
        return DrugFormulationModel.objects.select_related(
            'generic_drug', 'generic_drug__category'
        ).order_by('generic_drug__generic_name', 'form_type', 'strength')


class DrugFormulationDetailView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, DetailView):
    model = DrugFormulationModel
    permission_required = 'pharmacy.view_drugformulationmodel'
    template_name = 'pharmacy/formulation/detail.html'
    context_object_name = "formulation"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        formulation = self.object

        # Related products
        products = DrugModel.objects.filter(
            formulation=formulation, is_active=True
        ).select_related('manufacturer').order_by('brand_name')

        context.update({
            'products': products,
            'product_count': products.count(),
        })
        return context


class DrugFormulationUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, UpdateView
):
    model = DrugFormulationModel
    permission_required = 'pharmacy.change_drugformulationmodel'
    form_class = DrugFormulationForm
    template_name = 'pharmacy/formulation/update.html'
    success_message = 'Drug Formulation Successfully Updated'
    context_object_name = "formulation"

    def get_success_url(self):
        return reverse('drug_formulation_detail', kwargs={'pk': self.object.pk})


class DrugFormulationDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = DrugFormulationModel
    permission_required = 'pharmacy.delete_drugformulationmodel'
    template_name = 'pharmacy/formulation/delete.html'
    context_object_name = "formulation"
    success_message = 'Drug Formulation Successfully Deleted'

    def get_success_url(self):
        return reverse('drug_formulation_index')


# -------------------------
# Drug Product Views
# -------------------------
class DrugCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, CreateView
):
    model = DrugModel
    permission_required = 'pharmacy.add_drugmodel'
    form_class = DrugForm
    template_name = 'pharmacy/drug/create.html'
    success_message = 'Drug Product Successfully Created'

    def get_success_url(self):
        return reverse('drug_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        try:
            form.instance.created_by = getattr(self.request, 'user', None)
        except Exception:
            logger.exception("Failed to set created_by on drug form_valid")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass all active formulations for client-side search
        context['formulation_list'] = DrugFormulationModel.objects.filter(
            status='active'
        ).select_related('generic_drug').order_by('generic_drug__generic_name', 'form_type', 'strength')

        # Pass all approved manufacturers for client-side search
        context['manufacturer_list'] = ManufacturerModel.objects.filter(
            is_approved=True
        ).order_by('name')
        return context


class DrugListView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, ListView):
    model = DrugModel
    permission_required = 'pharmacy.view_drugmodel'
    template_name = 'pharmacy/drug/index.html'
    context_object_name = "drug_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = DrugModel.objects.select_related(
            'formulation__generic_drug',
            'formulation__generic_drug__category',
            'manufacturer'
        ).order_by('formulation__generic_drug__generic_name', 'brand_name')

        # Apply search filters
        search_form = DrugSearchForm(self.request.GET)
        if search_form.is_valid():
            search_term = search_form.cleaned_data.get('search_term')
            category = search_form.cleaned_data.get('category')
            manufacturer = search_form.cleaned_data.get('manufacturer')
            form_type = search_form.cleaned_data.get('form_type')
            stock_status = search_form.cleaned_data.get('stock_status')
            is_active = search_form.cleaned_data.get('is_active')

            if search_term:
                queryset = queryset.filter(
                    Q(formulation__generic_drug__generic_name__icontains=search_term) |
                    Q(brand_name__icontains=search_term) |
                    Q(sku__icontains=search_term)
                )

            if category:
                queryset = queryset.filter(formulation__generic_drug__category=category)

            if manufacturer:
                queryset = queryset.filter(manufacturer=manufacturer)

            if form_type:
                queryset = queryset.filter(formulation__form_type=form_type)

            if stock_status == 'in_stock':
                queryset = queryset.filter(
                    store_quantity__gt=0
                ).union(queryset.filter(pharmacy_quantity__gt=0))
            elif stock_status == 'low_stock':
                queryset = queryset.annotate(
                    total_stock=F('store_quantity') + F('pharmacy_quantity')
                ).filter(total_stock__lte=F('minimum_stock_level'))
            elif stock_status == 'out_of_stock':
                queryset = queryset.filter(
                    store_quantity=0, pharmacy_quantity=0
                )

            if is_active == 'true':
                queryset = queryset.filter(is_active=True)
            elif is_active == 'false':
                queryset = queryset.filter(is_active=False)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = DrugSearchForm(self.request.GET)
        return context


class DrugDetailView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, DetailView):
    model = DrugModel
    permission_required = 'pharmacy.view_drugmodel'
    template_name = 'pharmacy/drug/detail.html'
    context_object_name = "drug"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        drug = self.object

        # Stock entries
        stock_entries = DrugStockModel.objects.filter(
            drug=drug
        ).select_related('batch').order_by('-date_added')

        # Recent stock movements
        stock_outs = DrugStockOutModel.objects.filter(
            drug=drug
        ).select_related('stock').order_by('-created_at')[:10]

        # Recent transfers
        transfers = DrugTransferModel.objects.filter(
            drug=drug
        ).order_by('-transferred_at')[:10]

        context.update({
            'stock_entries': stock_entries,
            'stock_outs': stock_outs,
            'transfers': transfers,
            'quick_transfer_form': QuickTransferForm(),
            'stock_alert_form': StockAlertForm(),
        })
        return context


class DrugUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, UpdateView
):
    model = DrugModel
    permission_required = 'pharmacy.change_drugmodel'
    form_class = DrugForm
    template_name = 'pharmacy/drug/update.html'
    success_message = 'Drug Product Successfully Updated'
    context_object_name = "drug"

    def get_success_url(self):
        return reverse('drug_detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass all active formulations for client-side search
        context['formulation_list'] = DrugFormulationModel.objects.filter(
            status='active'
        ).select_related('generic_drug').order_by('generic_drug__generic_name', 'form_type', 'strength')

        # Pass all approved manufacturers for client-side search
        context['manufacturer_list'] = ManufacturerModel.objects.filter(
            is_approved=True
        ).order_by('name')
        return context


class DrugDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = DrugModel
    permission_required = 'pharmacy.delete_drugmodel'
    template_name = 'pharmacy/drug/delete.html'
    context_object_name = "drug"
    success_message = 'Drug Product Successfully Deleted'

    def get_success_url(self):
        return reverse('drug_index')


# -------------------------
# Drug Batch Views
# -------------------------
class DrugBatchCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, CreateView
):
    model = DrugBatchModel
    permission_required = 'pharmacy.add_drugbatchmodel'
    form_class = DrugBatchForm
    template_name = 'pharmacy/batch/index.html'
    success_message = 'Drug Batch Successfully Created'

    def get_success_url(self):
        return reverse('drug_batch_index')

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'GET':
            return redirect(reverse('drug_batch_index'))
        return super().dispatch(request, *args, **kwargs)


class DrugBatchListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = DrugBatchModel
    permission_required = 'pharmacy.view_drugbatchmodel'
    template_name = 'pharmacy/batch/index.html'
    context_object_name = "batch_list"

    def get_queryset(self):
        return DrugBatchModel.objects.all().order_by('-date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = DrugBatchForm()
        return context


class DrugBatchUpdateView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    # FlashFormErrorsMixin, # Uncomment if you're using this mixin
    UpdateView
):
    model = DrugBatchModel
    permission_required = 'pharmacy.change_drugbatchmodel'
    form_class = DrugBatchForm
    template_name = 'pharmacy/batch/index.html' # This template is typically for list + add modal
    # success_message = 'Drug Batch Successfully Updated' # Handled by FlashFormErrorsMixin or messages directly

    def get_object(self, queryset=None):
        """
        Ensures that only the last created drug batch can be updated.
        """
        requested_pk = self.kwargs.get('pk')

        try:
            # Get the very last created batch based on its creation timestamp
            last_batch = DrugBatchModel.objects.latest('created_at')
        except DrugBatchModel.DoesNotExist:
            # If no batches exist, show an error and redirect to the index page.
            messages.error(self.request, "No drug batches available to update.")
            return HttpResponseRedirect(self.get_success_url())

        # Compare the requested batch's primary key with the last batch's primary key
        if last_batch.pk != requested_pk:
            # If they don't match, it's not the last created batch.
            # Show an error message indicating which batch is editable.
            try:
                # Get the name of the batch that was attempted to be updated for a clearer message
                attempted_batch_name = get_object_or_404(DrugBatchModel, pk=requested_pk).name
            except Exception:
                attempted_batch_name = f"ID {requested_pk}"

            messages.error(
                self.request,
                f"Only the last created batch ('{last_batch.name}') can be updated. "
                f"You attempted to update batch '{attempted_batch_name}'."
            )
            # Redirect to the drug batch index page.
            return HttpResponseRedirect(self.get_success_url())

        # If the requested batch IS the last created one, return it.
        # The UpdateView will then proceed with this object.
        return last_batch

    def get_success_url(self):
        return reverse('drug_batch_index')

    def dispatch(self, request, *args, **kwargs):
        # This dispatch method handles a specific pattern where GET requests
        # to the update URL are redirected to the index page (which typically
        # contains the update form in a modal triggered by client-side JS).
        # We ensure that the get_object's redirect (if any) takes precedence.

        # Call get_object first to perform the "last created" check.
        # It might return an HttpResponseRedirect if the condition isn't met.
        obj = self.get_object()
        if isinstance(obj, HttpResponseRedirect):
            return obj # If get_object decided to redirect, honor that immediately.

        # If get_object didn't redirect, it means 'obj' is the valid last batch.
        # Set self.object for the view's context.
        self.object = obj

        if request.method == 'GET':
            # For GET requests, if it's the valid last batch,
            # still redirect to the index page as per the original design.
            # The actual update is expected to happen via a modal on the index.
            return redirect(self.get_success_url())

        # For POST requests (form submission), proceed with the UpdateView's normal flow.
        return super().dispatch(request, *args, **kwargs)


class DrugBatchDeleteView(
    LoginRequiredMixin,
    PermissionRequiredMixin,
    DeleteView
):
    model = DrugBatchModel
    permission_required = 'pharmacy.delete_drugbatchmodel'
    template_name = 'pharmacy/batch/delete.html'
    context_object_name = "batch"
    # success_message = 'Drug Batch Successfully Deleted'

    def get_object(self, queryset=None):
        requested_pk = self.kwargs.get('pk')

        try:
            last_batch = DrugBatchModel.objects.latest('created_at')
        except DrugBatchModel.DoesNotExist:
            messages.error(self.request, "No drug batches available to delete.")
            return HttpResponseRedirect(self.get_success_url())

        if last_batch.pk != requested_pk:
            try:
                attempted_batch_name = get_object_or_404(DrugBatchModel, pk=requested_pk).name
            except Exception:
                attempted_batch_name = f"ID {requested_pk}"

            messages.error(
                self.request,
                f"Only the last created batch ('{last_batch.name}') can be deleted. "
                f"You attempted to delete batch '{attempted_batch_name}'."
            )
            return HttpResponseRedirect(self.get_success_url())

        return last_batch

    def get_success_url(self):
        return reverse('drug_batch_index')


    def dispatch(self, request, *args, **kwargs):
        """
        Custom dispatch to handle HttpResponseRedirect from get_object.
        """
        # Call get_object first to perform the "last created" check.
        # It might return an HttpResponseRedirect if the condition isn't met.
        obj = self.get_object()

        # If get_object returned a redirect, immediately return it.
        if isinstance(obj, HttpResponseRedirect):
            return obj

        # Otherwise, proceed with the normal DeleteView dispatch.
        # This sets self.object, which is then used by get_context_data and post.
        self.object = obj
        return super().dispatch(request, *args, **kwargs)



# -------------------------
# Drug Stock Views
class DrugStockCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, TemplateView
):
    model = DrugStockModel
    permission_required = 'pharmacy.add_drugstockmodel'
    template_name = 'pharmacy/stock/create.html'
    success_message = 'Drug Stocks Successfully Added'

    def get_last_batch(self):
        try:
            return DrugBatchModel.objects.latest('created_at')
        except DrugBatchModel.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        last_batch = self.get_last_batch()
        if not last_batch:
            messages.error(request, "No drug batches available. Please create a batch first.")
            return redirect('drug_batch_index')

        # Create formset with batch pre-filled
        formset = DrugStockFormSet(
            queryset=DrugStockModel.objects.none(),
            initial=[{'batch': last_batch}]  # Pre-fill first form
        )

        # Set batch for all forms (including empty_form)
        for form in formset:
            form.fields['batch'].initial = last_batch

        context = {
            'formset': formset,
            'last_batch': last_batch,
            'title': 'Add New Drug Stock'
        }
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        last_batch = self.get_last_batch()
        if not last_batch:
            messages.error(request, "No drug batches available. Please create a batch first.")
            return redirect('drug_batch_index')

        formset = DrugStockFormSet(request.POST, queryset=DrugStockModel.objects.none())

        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                instance.batch = last_batch  # Ensure batch is set
                instance.created_by = request.user
                instance.save()

            messages.success(request, self.success_message)
            return redirect('drug_batch_detail', pk=last_batch.pk)
        else:
            # Debug print to see what errors we have
            print("Formset errors:", formset.errors)
            print("Non-form errors:", formset.non_form_errors())

            messages.error(request, "Please correct the errors below.")

            # Re-set batch for forms on error
            for form in formset:
                form.fields['batch'].initial = last_batch

            context = {
                'formset': formset,
                'last_batch': last_batch,
                'title': 'Add New Drug Stock'
            }
            return self.render_to_response(context)

class DrugBatchStockListView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, ListView):
    # This view now lists DrugBatchModels, showing aggregated stock info
    model = DrugBatchModel  # Model is now DrugBatchModel
    permission_required = 'pharmacy.view_drugstockmodel'  # Use stock permission as it's for stock overview
    template_name = 'pharmacy/stock/index.html'
    context_object_name = "batch_list"  # Renamed to reflect it's a list of batches
    paginate_by = 20

    def get_queryset(self):
        # Annotate each batch with the count of distinct drugs and total quantity
        queryset = DrugBatchModel.objects.annotate(
            drug_count=Count('stock_items__drug', distinct=True),
            total_quantity=Sum('stock_items__quantity_bought')
        ).order_by('-date')  # Order by batch date

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # We might not need a form on the batch list page itself,
        # as creation is handled by DrugStockCreateView.
        # context['form'] = DrugBatchForm() # Remove if not needed
        return context


class DrugBatchDetailView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, DetailView):
    model = DrugBatchModel
    template_name = 'pharmacy/stock/batch_detail.html'
    context_object_name = 'batch'
    permission_required = 'pharmacy.view_drugbatchmodel' # Ensure you have the correct permission

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batch = self.object # The DrugBatchModel instance

        stock_items = batch.stock_items.select_related(
            'drug__formulation__generic_drug',
            'drug__manufacturer'
        ).order_by('drug__brand_name', 'expiry_date')

        # --- NEW LOGIC: Pre-calculate low stock flag in the view ---
        for stock in stock_items:
            # Ensure calculations are done with Decimal for precision
            # Assuming quantity_bought is already a Decimal type from the model
            threshold = Decimal(stock.quantity_bought) * Decimal('0.25')
            stock.is_low_stock = stock.quantity_left < threshold
            # You can also add other flags if needed, e.g., for near expiry
        # --- END NEW LOGIC ---

        context['stock_items'] = stock_items
        context['stock_out_form'] = DrugStockOutForm
        context['title'] = f"Batch Details: {batch.name.upper()}"
        context['update_forms'] = {
            stock.pk: DrugStockForm(instance=stock) for stock in stock_items
        },


        return context



class DrugStockUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, UpdateView
):
    model = DrugStockModel
    permission_required = 'pharmacy.change_drugstockmodel'
    form_class = DrugStockForm
    template_name = 'pharmacy/stock/edit.html'  # This template will likely be used in a modal
    success_message = 'Drug Stock Successfully Updated'

    def get_success_url(self):
        # Redirect back to the batch detail page after updating a stock item
        return reverse('drug_batch_detail', kwargs={'pk': self.object.batch.pk})

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Optionally hide the batch field during update if it should not be changeable
        # kwargs['instance'].batch field should be read-only if desired.
        return kwargs

    def form_valid(self, form):
        # Custom logic before saving an individual stock update
        # For example, if quantity_bought is changed, recalculate quantity_left
        old_instance = self.get_object()
        new_quantity_bought = form.cleaned_data['quantity_bought']

        # If quantity_bought changed, and no existing sales/stock-outs
        # you might want to adjust quantity_left
        if old_instance.quantity_bought != new_quantity_bought:
            # Check if quantity_left == quantity_bought for safety
            if old_instance.quantity_left == old_instance.quantity_bought:
                form.instance.quantity_left = new_quantity_bought
                messages.warning(self.request, "Quantity left adjusted based on new quantity bought.")
            else:
                messages.warning(self.request,
                                 "Quantity bought changed, but quantity left was not adjusted automatically as it differs from the original quantity. Please adjust manually if needed.")

        return super().form_valid(form)


class DrugStockDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = DrugStockModel
    permission_required = 'pharmacy.delete_drugstockmodel'
    template_name = 'pharmacy/stock/delete.html'
    context_object_name = "stock"
    success_message = 'Drug Stock Successfully Deleted'

    def get_object(self, queryset=None):
        """
        Ensures a stock entry can only be deleted if quantity_left == quantity_bought.
        """
        requested_pk = self.kwargs.get('pk')
        stock = get_object_or_404(DrugStockModel, pk=requested_pk)

        if stock.quantity_left != stock.quantity_bought:
            messages.error(
                self.request,
                f"Cannot delete stock for '{stock.drug.name}' (Batch: '{stock.batch.name}'). "
                f"Quantity left ({stock.quantity_left}) does not equal quantity bought ({stock.quantity_bought}). "
                "Only full, unused stock entries can be deleted."
            )
            # Redirect to the batch detail page for the affected stock
            return HttpResponseRedirect(reverse('drug_batch_detail', kwargs={'pk': stock.batch.pk}))

        return stock

    def get_success_url(self):
        # After successful deletion, redirect to the relevant batch detail page
        # Note: If self.object is set *after* get_object(), we need to store batch.pk
        # for a safe redirect. However, `get_object` already returns the 'stock' object here.
        # But if the deletion is prevented, we'll have redirected already.
        # If successfully deleted, self.object won't have a batch.pk anymore.
        # So, we should redirect to the main stock index.
        messages.success(self.request, self.success_message)  # Manually add success message here
        return reverse('drug_stock_index')  # Redirect to the main stock overview

    def dispatch(self, request, *args, **kwargs):
        """
        Custom dispatch to handle HttpResponseRedirect from get_object before delete process.
        """
        # Call get_object first to perform the quantity check.
        obj = self.get_object()

        # If get_object returned a redirect, immediately return it.
        if isinstance(obj, HttpResponseRedirect):
            return obj

        # Otherwise, proceed with the normal DeleteView dispatch.
        self.object = obj  # Set self.object for the template context
        return super().dispatch(request, *args, **kwargs)


class DrugStockOutView(LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, View):
    # This will be a POST-only view to handle reducing stock quantity
    permission_required = 'pharmacy.change_drugstockmodel'  # Requires permission to change stock
    success_message = 'Drug Stock Quantity Successfully Reduced'

    def post(self, request, pk):
        stock = get_object_or_404(DrugStockModel, pk=pk)
        quantity_to_reduce = float(request.POST.get('quantity_to_reduce', 0))

        if quantity_to_reduce <= 0:
            messages.error(self.request, "Quantity to reduce must be greater than zero.")
        elif quantity_to_reduce > stock.quantity_left:
            messages.error(self.request,
                           f"Cannot reduce {quantity_to_reduce} units. Only {stock.quantity_left} units left.")
        else:
            stock.quantity_left -= quantity_to_reduce
            stock.save()  # The save method will update current_worth and drug quantities
            # You might also want to create a DrugStockOutModel entry here
            messages.success(self.request, self.success_message)

        return redirect(reverse('drug_batch_detail', kwargs={'pk': stock.batch.pk}))


# Assume DrugStockOutForm exists (a simple form with a 'quantity' field)
class DrugStockOutForm(forms.Form):
    quantity_to_reduce = forms.FloatField(
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label='Quantity to Stock Out'
    )


# -------------------------
# Drug Transfer Views
# -------------------------
class DrugTransferCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, CreateView
):
    model = DrugTransferModel
    permission_required = 'pharmacy.add_drugtransfermodel'
    form_class = DrugTransferForm  # Assuming DrugTransferForm exists
    template_name = 'pharmacy/transfer/create.html'
    success_message = 'Drug Transfer Successfully Completed'

    def get_success_url(self):
        return reverse('drug_transfer_index')

    def form_valid(self, form):
        try:
            form.instance.transferred_by = getattr(self.request, 'user', None)
        except Exception:
            logger.exception("Failed to set transferred_by on transfer form_valid")

        # ⭐ Crucial: Before saving, check if enough stock is available in 'store' location
        drug = form.instance.drug
        quantity_to_transfer = form.instance.quantity

        if drug.store_quantity < quantity_to_transfer:
            messages.error(self.request,
                           f"Insufficient stock in store for {drug.brand_name}. Only {drug.store_quantity} available.")
            return self.form_invalid(form)  # Re-render form with error

        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """
        Add all DrugModel instances to the context for client-side filtering.
        """
        context = super().get_context_data(**kwargs)
        # Fetch all drugs, prefetching related data needed for display in the dropdown.
        # This includes store_quantity and pharmacy_quantity.
        context['drugs'] = DrugModel.objects.select_related(
            'formulation__generic_drug'
        ).all().order_by('brand_name')
        return context


class DrugTransferListView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, ListView):
    model = DrugTransferModel
    permission_required = 'pharmacy.view_drugtransfermodel'
    template_name = 'pharmacy/transfer/index.html'
    context_object_name = "transfer_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = DrugTransferModel.objects.select_related(
            'drug__formulation__generic_drug',
            'drug__manufacturer',
            'transferred_by'  # ⭐ Include transferred_by for select_related
        ).order_by('-transferred_at')

        # Initialize the filter form with GET parameters
        form = DrugTransferFilterForm(self.request.GET)

        if form.is_valid():
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            drug = form.cleaned_data.get('drug')
            transferred_by = form.cleaned_data.get('transferred_by')

            if start_date:
                queryset = queryset.filter(transferred_at__date__gte=start_date)
            if end_date:
                queryset = queryset.filter(transferred_at__date__lte=end_date)
            if drug:
                queryset = queryset.filter(drug=drug)
            if transferred_by:
                queryset = queryset.filter(transferred_by=transferred_by)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass an instance of the filter form, pre-filled with GET data
        context['filter_form'] = DrugTransferFilterForm(self.request.GET)
        context['title'] = "Drug Transfers"  # Add a title for the page
        return context


# -------------------------
# Drug Template Views
# -------------------------
class DrugTemplateCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, CreateView
):
    model = DrugTemplateModel
    permission_required = 'pharmacy.add_drugtemplatemodel'
    form_class = DrugTemplateForm
    template_name = 'pharmacy/template/create.html'
    success_message = 'Drug Template Successfully Created'

    def get_success_url(self):
        return reverse('drug_template_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        try:
            form.instance.created_by = getattr(self.request, 'user', None)
        except Exception:
            logger.exception("Failed to set created_by on template form_valid")
        return super().form_valid(form)


class DrugTemplateListView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, ListView):
    model = DrugTemplateModel
    permission_required = 'pharmacy.view_drugtemplatemodel'
    template_name = 'pharmacy/template/index.html'
    context_object_name = "template_list"
    paginate_by = 20

    def get_queryset(self):
        return DrugTemplateModel.objects.select_related(
            'category', 'created_by'
        ).order_by('-created_at')


class DrugTemplateDetailView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, DetailView):
    model = DrugTemplateModel
    permission_required = 'pharmacy.view_drugtemplatemodel'
    template_name = 'pharmacy/template/detail.html'
    context_object_name = "template"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        template = self.object

        context.update({
            'preview_combinations': template.preview_combinations,
            'combination_count': len(template.drug_combinations),
            'can_process': not template.is_processed,
        })
        return context


class DrugTemplateUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, UpdateView
):
    model = DrugTemplateModel
    permission_required = 'pharmacy.change_drugtemplatemodel'
    form_class = DrugTemplateForm
    template_name = 'pharmacy/template/edit.html'
    success_message = 'Drug Template Successfully Updated'

    def get_success_url(self):
        return reverse('drug_template_detail', kwargs={'pk': self.object.pk})

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        if obj.is_processed:
            messages.error(self.request, 'Cannot edit processed templates.')
            return redirect('drug_template_detail', pk=obj.pk)
        return obj


class DrugTemplateDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = DrugTemplateModel
    permission_required = 'pharmacy.delete_drugtemplatemodel'
    template_name = 'pharmacy/template/delete.html'
    context_object_name = "template"
    success_message = 'Drug Template Successfully Deleted'

    def get_success_url(self):
        return reverse('drug_template_index')


# -------------------------
# Pharmacy Settings Views
# -------------------------
class PharmacySettingUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, UpdateView
):
    model = PharmacySettingModel
    permission_required = 'pharmacy.change_pharmacysettingmodel'
    form_class = PharmacySettingForm
    template_name = 'pharmacy/settings/index.html'
    success_message = 'Pharmacy Settings Successfully Updated'

    def get_object(self, queryset=None):
        # Get or create the singleton settings instance
        obj, created = PharmacySettingModel.objects.get_or_create(
            pk=1,
            defaults={}
        )
        return obj

    def get_success_url(self):
        return reverse('pharmacy_setting_index')


class PharmacySettingDetailView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, DetailView):
    model = PharmacySettingModel
    permission_required = 'pharmacy.view_pharmacysettingmodel'
    template_name = 'pharmacy/settings/index.html'
    context_object_name = "setting"

    def get_object(self, queryset=None):
        obj, created = PharmacySettingModel.objects.get_or_create(
            pk=1,
            defaults={}
        )
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PharmacySettingForm(instance=self.object)
        return context


# -------------------------
# Drug Import Log Views
# -------------------------
class DrugImportLogCreateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, CreateView
):
    model = DrugImportLogModel
    permission_required = 'pharmacy.add_drugimportlogmodel'
    form_class = DrugImportLogForm
    template_name = 'pharmacy/import/create.html'
    success_message = 'Drug Import Successfully Initiated'

    def get_success_url(self):
        return reverse('drug_import_log_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        try:
            form.instance.imported_by = getattr(self.request, 'user', None)
        except Exception:
            logger.exception("Failed to set imported_by on import form_valid")
        return super().form_valid(form)


class DrugImportLogListView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, ListView):
    model = DrugImportLogModel
    permission_required = 'pharmacy.view_drugimportlogmodel'
    template_name = 'pharmacy/import/index.html'
    context_object_name = "import_log_list"
    paginate_by = 20

    def get_queryset(self):
        return DrugImportLogModel.objects.select_related(
            'imported_by'
        ).order_by('-import_date')


class DrugImportLogDetailView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, DetailView):
    model = DrugImportLogModel
    permission_required = 'pharmacy.view_drugimportlogmodel'
    template_name = 'pharmacy/import/detail.html'
    context_object_name = "import_log"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        import_log = self.object

        context.update({
            'success_rate': (
                import_log.successful_records / import_log.total_records * 100
                if import_log.total_records > 0 else 0
            ),
            'has_errors': bool(import_log.error_log),
            'error_lines': import_log.error_log.split('\n') if import_log.error_log else [],
        })
        return context


# -------------------------
# Dashboard and Reports Views
# -------------------------
class PharmacyDashboardView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, TemplateView):
    permission_required = 'pharmacy.view_drugmodel'
    template_name = 'pharmacy/dashboard/index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Summary statistics
        total_drugs = DrugModel.objects.filter(is_active=True).count()
        total_categories = DrugCategoryModel.objects.count()
        total_manufacturers = ManufacturerModel.objects.filter(is_approved=True).count()

        # Stock statistics
        low_stock_drugs = get_low_stock_drugs()
        expired_stock = get_expired_stock()
        near_expiry_stock = get_near_expiry_stock()

        # Recent activity
        recent_stock_entries = DrugStockModel.objects.select_related(
            'drug__formulation__generic_drug', 'batch'
        ).order_by('-created_at')[:5]

        recent_stock_outs = DrugStockOutModel.objects.select_related(
            'drug__formulation__generic_drug'
        ).order_by('-created_at')[:5]

        recent_transfers = DrugTransferModel.objects.select_related(
            'drug__formulation__generic_drug'
        ).order_by('-transferred_at')[:5]

        # Value calculations
        total_inventory_value = DrugStockModel.objects.filter(
            status='active'
        ).aggregate(
            total_value=Sum('current_worth')
        )['total_value'] or 0

        context.update({
            'total_drugs': total_drugs,
            'total_categories': total_categories,
            'total_manufacturers': total_manufacturers,
            'low_stock_drugs': low_stock_drugs,
            'expired_stock': expired_stock,
            'near_expiry_stock': near_expiry_stock,
            'recent_stock_entries': recent_stock_entries,
            'recent_stock_outs': recent_stock_outs,
            'recent_transfers': recent_transfers,
            'total_inventory_value': total_inventory_value,
        })
        return context


class StockReportView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, TemplateView):
    permission_required = 'pharmacy.view_drugstockmodel'
    template_name = 'pharmacy/reports/stock_report.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        form = StockReportForm(self.request.GET or None)
        context['form'] = form

        if form.is_valid():
            report_type = form.cleaned_data.get('report_type')
            date_from = form.cleaned_data.get('date_from')
            date_to = form.cleaned_data.get('date_to')
            category = form.cleaned_data.get('category')
            manufacturer = form.cleaned_data.get('manufacturer')

            queryset = DrugModel.objects.select_related(
                'formulation__generic_drug__category',
                'manufacturer'
            ).filter(is_active=True)

            if category:
                queryset = queryset.filter(formulation__generic_drug__category=category)
            if manufacturer:
                queryset = queryset.filter(manufacturer=manufacturer)

            if report_type == 'low_stock':
                queryset = queryset.annotate(
                    total_stock=F('store_quantity') + F('pharmacy_quantity')
                ).filter(total_stock__lte=F('minimum_stock_level'))
                context['report_title'] = 'Low Stock Report'

            elif report_type == 'expired':
                expired_stock_ids = DrugStockModel.objects.filter(
                    expiry_date__lte=date.today(),
                    status='active',
                    quantity_left__gt=0
                ).values_list('drug_id', flat=True)
                queryset = queryset.filter(id__in=expired_stock_ids)
                context['report_title'] = 'Expired Stock Report'

            elif report_type == 'near_expiry':
                future_date = date.today() + timedelta(days=30)
                near_expiry_stock_ids = DrugStockModel.objects.filter(
                    expiry_date__lte=future_date,
                    expiry_date__gt=date.today(),
                    status='active',
                    quantity_left__gt=0
                ).values_list('drug_id', flat=True)
                queryset = queryset.filter(id__in=near_expiry_stock_ids)
                context['report_title'] = 'Near Expiry Stock Report'

            elif report_type == 'inventory_value':
                context['report_title'] = 'Inventory Value Report'
                # Calculate total value for each drug
                for drug in queryset:
                    drug.total_value = drug.stock_entries.filter(
                        status='active'
                    ).aggregate(total=Sum('current_worth'))['total'] or 0

            context['report_data'] = queryset
            context['report_generated'] = True

        return context

# -------------------------
# AJAX and API Views
# -------------------------
@login_required
@permission_required('pharmacy.add_drugtransfermodel')
def quick_transfer_view(request):
    """AJAX view for quick transfers from drug detail page"""
    if request.method == 'POST':
        form = QuickTransferForm(request.POST)
        if form.is_valid():
            try:
                drug_id = form.cleaned_data['drug_id']
                quantity = form.cleaned_data['quantity']

                drug = get_object_or_404(DrugModel, id=drug_id)

                if drug.store_quantity < quantity:
                    return JsonResponse({
                        'success': False,
                        'error': 'Insufficient stock in store.'
                    })

                transfer = DrugTransferModel.objects.create(
                    drug=drug,
                    quantity=quantity,
                    transferred_by=request.user,
                    notes=form.cleaned_data.get('notes', '')
                )

                return JsonResponse({
                    'success': True,
                    'message': f'Successfully transferred {quantity} units to pharmacy.',
                    'new_store_quantity': drug.store_quantity,
                    'new_pharmacy_quantity': drug.pharmacy_quantity
                })

            except Exception as e:
                logger.exception("Quick transfer failed")
                return JsonResponse({
                    'success': False,
                    'error': 'Transfer failed. Please try again.'
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid form data.'
            })

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@login_required
@permission_required('pharmacy.change_drugmodel')
def update_stock_alert_view(request):
    """AJAX view for updating minimum stock levels"""
    if request.method == 'POST':
        form = StockAlertForm(request.POST)
        if form.is_valid():
            try:
                drug_id = form.cleaned_data['drug_id']
                minimum_stock_level = form.cleaned_data['minimum_stock_level']

                drug = get_object_or_404(DrugModel, id=drug_id)
                drug.minimum_stock_level = minimum_stock_level
                drug.save()

                return JsonResponse({
                    'success': True,
                    'message': f'Minimum stock level updated to {minimum_stock_level}.'
                })

            except Exception as e:
                logger.exception("Stock alert update failed")
                return JsonResponse({
                    'success': False,
                    'error': 'Update failed. Please try again.'
                })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Invalid form data.'
            })

    return JsonResponse({'success': False, 'error': 'Invalid request method.'})


@login_required
@permission_required('pharmacy.add_drugtemplatemodel')
def process_drug_template_view(request, pk):
    """Process a drug template to create drug variants"""
    template = get_object_or_404(DrugTemplateModel, pk=pk)

    if request.method == 'POST':
        if template.is_processed:
            messages.error(request, 'This template has already been processed.')
            return redirect('drug_template_detail', pk=pk)

        selected_indices = request.POST.getlist('selected_combinations')
        if selected_indices:
            selected_indices = [int(i) for i in selected_indices]

        result = template.create_drug_variants(selected_indices)

        if result.get('success'):
            messages.success(
                request,
                f'Successfully created {result["created_count"]} drug variants.'
            )
            if result.get('errors'):
                for error in result['errors']:
                    messages.warning(request, error)
        else:
            messages.error(request, result.get('error', 'Processing failed.'))

        return redirect('drug_template_detail', pk=pk)

    context = {
        'template': template,
        'combinations': template.drug_combinations,
        'preview_combinations': template.preview_combinations,
    }
    return render(request, 'pharmacy/template/process.html', context)


@login_required
@permission_required('pharmacy.change_drugmodel')
def bulk_drug_status_update_view(request):
    """Bulk update drug status (active/inactive)"""
    if request.method == 'POST':
        form = BulkStatusUpdateForm(request.POST)
        if form.is_valid():
            try:
                drug_ids = form.cleaned_data['drug_ids']
                new_status = form.cleaned_data['status']

                drugs = DrugModel.objects.filter(id__in=drug_ids)
                updated_count = drugs.update(is_active=new_status)

                status_text = 'active' if new_status else 'inactive'
                messages.success(
                    request,
                    f'Successfully updated {updated_count} drugs to {status_text} status.'
                )

            except Exception as e:
                logger.exception("Bulk status update failed")
                messages.error(request, 'Bulk update failed. Please try again.')
        else:
            messages.error(request, 'Invalid form data.')

    return redirect('drug_index')


# -------------------------
# Export Views
# -------------------------
@login_required
@permission_required('pharmacy.view_drugmodel')
def export_drug_list_view(request):
    """Export drug list to CSV"""
    import csv
    from django.http import StreamingHttpResponse

    def generate_csv():
        yield 'Generic Name,Brand Name,SKU,Form,Strength,Manufacturer,Category,Store Qty,Pharmacy Qty,Total Qty,Min Stock,Status\n'

        drugs = DrugModel.objects.select_related(
            'formulation__generic_drug__category',
            'formulation__generic_drug',
            'manufacturer'
        ).filter(is_active=True).order_by('formulation__generic_drug__generic_name')

        for drug in drugs:
            row = [
                drug.formulation.generic_drug.generic_name,
                drug.brand_name or '',
                drug.sku,
                drug.formulation.get_form_type_display(),
                drug.formulation.strength,
                drug.manufacturer.name,
                drug.formulation.generic_drug.category.name if drug.formulation.generic_drug.category else '',
                str(drug.store_quantity),
                str(drug.pharmacy_quantity),
                str(drug.total_quantity),
                str(drug.minimum_stock_level),
                'Low Stock' if drug.is_low_stock else 'Normal'
            ]
            yield ','.join(f'"{field}"' for field in row) + '\n'

    response = StreamingHttpResponse(
        generate_csv(),
        content_type='text/csv'
    )
    response['Content-Disposition'] = f'attachment; filename="drug_inventory_{date.today()}.csv"'
    return response


@login_required
@permission_required('pharmacy.view_drugstockmodel')
def export_stock_report_view(request):
    """Export stock report to CSV"""
    import csv
    from django.http import StreamingHttpResponse

    report_type = request.GET.get('type', 'all')

    def generate_csv():
        yield 'Drug Name,SKU,Form,Strength,Manufacturer,Batch,Quantity Left,Unit Cost,Selling Price,Current Worth,Location,Expiry Date,Status\n'

        queryset = DrugStockModel.objects.select_related(
            'drug__formulation__generic_drug',
            'drug__manufacturer',
            'batch'
        ).filter(status='active', quantity_left__gt=0)

        if report_type == 'low_stock':
            drug_ids = get_low_stock_drugs().values_list('id', flat=True)
            queryset = queryset.filter(drug_id__in=drug_ids)
        elif report_type == 'expired':
            queryset = queryset.filter(expiry_date__lte=date.today())
        elif report_type == 'near_expiry':
            future_date = date.today() + timedelta(days=30)
            queryset = queryset.filter(
                expiry_date__lte=future_date,
                expiry_date__gt=date.today()
            )

        for stock in queryset.order_by('drug__formulation__generic_drug__generic_name'):
            row = [
                stock.drug.formulation.generic_drug.generic_name,
                stock.drug.sku,
                stock.drug.formulation.get_form_type_display(),
                stock.drug.formulation.strength,
                stock.drug.manufacturer.name,
                stock.batch.name if stock.batch else '',
                str(stock.quantity_left),
                str(stock.unit_cost_price),
                str(stock.selling_price),
                str(stock.current_worth),
                stock.get_location_display(),
                stock.expiry_date.strftime('%Y-%m-%d') if stock.expiry_date else '',
                'Expired' if stock.is_expired else 'Active'
            ]
            yield ','.join(f'"{field}"' for field in row) + '\n'

    filename = f"stock_report_{report_type}_{date.today()}.csv"
    response = StreamingHttpResponse(
        generate_csv(),
        content_type='text/csv'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response