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
from django.db.models import Q, Sum, F, Count, ExpressionWrapper, DecimalField
from django.db.models.functions import Lower, Cast
from django.forms import modelformset_factory
from django.http import JsonResponse, HttpResponse, Http404, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import now
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView, ListView, UpdateView, DeleteView, DetailView, TemplateView
)

from finance.models import PatientTransactionModel
from finance.views import _quantize_money
from insurance.claim_helpers import get_orders_with_claim_info
from insurance.models import PatientInsuranceModel
from patient.models import PatientModel, PatientWalletModel
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
    PharmacySettingModel, DrugTemplateModel, DrugImportLogModel, DrugOrderModel, DispenseRecord
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
    permission_required = 'pharmacy.add_drugcategorymodel'
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
    permission_required = 'pharmacy.add_drugcategorymodel'
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
    permission_required = 'pharmacy.add_drugcategorymodel'
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
    permission_required = 'pharmacy.view_drugcategorymodel'
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
    permission_required = 'pharmacy.add_drugcategorymodel'
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
    permission_required = 'pharmacy.add_drugcategorymodel'
    template_name = 'pharmacy/manufacturer/delete.html'
    context_object_name = "manufacturer"
    success_message = 'Manufacturer Successfully Deleted'

    def get_success_url(self):
        return reverse('manufacturer_index')


# -------------------------
# Generic Drug Views
# -------------------------
class GenericDrugCreateView(
    LoginRequiredMixin, PermissionRequiredMixin,
    PharmacyContextMixin, CreateView
):
    model = GenericDrugModel
    permission_required = 'pharmacy.add_drugcategorymodel'
    form_class = GenericDrugForm
    template_name = 'pharmacy/generic_drug/create.html'
    success_message = 'Generic Drug Successfully Created'

    def get_success_url(self):
        return reverse('generic_drug_detail', kwargs={'pk': self.object.pk})


class GenericDrugListView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, ListView):
    model = GenericDrugModel
    permission_required = 'pharmacy.view_drugcategorymodel'
    template_name = 'pharmacy/generic_drug/index.html'
    context_object_name = "generic_drug_list"
    paginate_by = 20

    def get_queryset(self):
        return GenericDrugModel.objects.select_related('category').order_by('generic_name')


class GenericDrugDetailView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, DetailView):
    model = GenericDrugModel
    permission_required = 'pharmacy.view_drugcategorymodel'
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
    LoginRequiredMixin, PermissionRequiredMixin,
    PharmacyContextMixin, UpdateView
):
    model = GenericDrugModel
    permission_required = 'pharmacy.add_drugcategorymodel'
    form_class = GenericDrugForm
    template_name = 'pharmacy/generic_drug/update.html'
    context_object_name = "generic_drug"

    success_message = 'Generic Drug Successfully Updated'

    def get_success_url(self):
        return reverse('generic_drug_detail', kwargs={'pk': self.object.pk})


class GenericDrugDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = GenericDrugModel
    permission_required = 'pharmacy.add_drugcategorymodel'
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
    permission_required = 'pharmacy.add_drugcategorymodel'
    form_class = DrugFormulationForm
    template_name = 'pharmacy/formulation/create.html'
    success_message = 'Drug Formulation Successfully Created'

    def get_success_url(self):
        return reverse('drug_formulation_detail', kwargs={'pk': self.object.pk})


class DrugFormulationListView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, ListView):
    model = DrugFormulationModel
    permission_required = 'pharmacy.view_drugcategorymodel'
    template_name = 'pharmacy/formulation/index.html'
    context_object_name = "formulation_list"
    paginate_by = 20

    def get_queryset(self):
        return DrugFormulationModel.objects.select_related(
            'generic_drug', 'generic_drug__category'
        ).order_by('generic_drug__generic_name', 'form_type', 'strength')


class DrugFormulationDetailView(LoginRequiredMixin, PermissionRequiredMixin, PharmacyContextMixin, DetailView):
    model = DrugFormulationModel
    permission_required = 'pharmacy.view_drugcategorymodel'
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
    permission_required = 'pharmacy.add_drugcategorymodel'
    form_class = DrugFormulationForm
    template_name = 'pharmacy/formulation/update.html'
    success_message = 'Drug Formulation Successfully Updated'
    context_object_name = "formulation"

    def get_success_url(self):
        return reverse('drug_formulation_detail', kwargs={'pk': self.object.pk})


class DrugFormulationDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = DrugFormulationModel
    permission_required = 'pharmacy.add_drugcategorymodel'
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
    permission_required = 'pharmacy.add_drugstockmodel'
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
    permission_required = 'pharmacy.view_drugstockmodel'
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
    permission_required = 'pharmacy.add_drugstockmodel'
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
    permission_required = 'pharmacy.add_drugstockmodel'
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

        if obj.stock_items.all():
            messages.error(request, 'Cannot Delete a batch that has stocks')
            return redirect(reverse('drug_batch_detail', kwargs={'pk':obj.id}))

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
    permission_required = 'pharmacy.add_drugstockmodel' # Ensure you have the correct permission

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
        }

        return context


class DrugStockUpdateView(
    LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
    PharmacyContextMixin, UpdateView
):
    model = DrugStockModel
    permission_required = 'pharmacy.add_drugstockmodel'
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
    permission_required = 'pharmacy.add_drugstockmodel'
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
                f"Cannot delete stock for '{stock.drug.__str__()}' (Batch: '{stock.batch.name}'). "
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
        return reverse('drug_batch_detail', kwargs={'pk':self.object.batch.pk})  # Redirect to the main stock overview

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


class DrugStockOutView(LoginRequiredMixin, PermissionRequiredMixin, View):
    """Handle drug stock out with FIFO allocation across multiple stocks"""
    permission_required = 'pharmacy.add_drugstockmodel'
    success_message = 'Drug Stock Successfully Reduced'

    def post(self, request, pk):
        drug = get_object_or_404(DrugModel, pk=pk)

        # Get form data
        quantity_to_reduce = float(request.POST.get('quantity_to_reduce', 0))
        location = request.POST.get('location', 'store')  # 'store' or 'pharmacy'
        reason = request.POST.get('reason', 'sale')
        remark = request.POST.get('remark', '')

        # Validation
        if quantity_to_reduce <= 0:
            messages.error(request, "Quantity to reduce must be greater than zero.")
            return self.redirect_back(drug)

        # Check if sufficient quantity in selected location
        current_quantity = drug.store_quantity if location == 'store' else drug.pharmacy_quantity

        if quantity_to_reduce > current_quantity:
            messages.error(request,
                           f"Cannot reduce {quantity_to_reduce} units from {location}. "
                           f"Only {current_quantity} units available in {location}.")
            return self.redirect_back(drug)

        # Perform FIFO stock reduction
        try:
            with transaction.atomic():
                self.process_stock_reduction(drug, quantity_to_reduce, location, reason, remark, request.user)
                messages.success(request, self.success_message)
        except Exception as e:
            messages.error(request, f"Error processing stock reduction: {str(e)}")

        return self.redirect_back(drug)

    def process_stock_reduction(self, drug, quantity_to_reduce, location, reason, remark, user):
        """Process stock reduction using FIFO logic"""
        remaining_to_reduce = quantity_to_reduce

        # Get active stocks for this drug in FIFO order (oldest first)
        active_stocks = DrugStockModel.objects.filter(
            drug=drug,
            status='active',
            quantity_left__gt=0
        ).order_by('date_added')

        if not active_stocks.exists():
            raise ValueError("No active stocks found for this drug")

        stock_outs_created = []

        # Process each stock in FIFO order
        for stock in active_stocks:
            if remaining_to_reduce <= 0:
                break

            # Calculate how much to deduct from this stock
            quantity_from_this_stock = min(remaining_to_reduce, stock.quantity_left)

            # Create stock out record
            stock_out = DrugStockOutModel.objects.create(
                stock=stock,
                drug=drug,
                quantity=quantity_from_this_stock,
                reason=reason,
                location_reduced_from=location,
                worth=stock.selling_price * Decimal(str(quantity_from_this_stock)),
                remark=remark,
                created_by=user
            )
            stock_outs_created.append(stock_out)

            # Update stock quantity and worth
            stock.quantity_left -= quantity_from_this_stock
            stock.current_worth = Decimal(str(stock.quantity_left)) * stock.selling_price
            stock.save()

            # Update remaining quantity to reduce
            remaining_to_reduce -= quantity_from_this_stock

        # Update drug quantities based on location
        if location == 'store':
            drug.store_quantity -= quantity_to_reduce
        else:
            drug.pharmacy_quantity -= quantity_to_reduce

        drug.save()

        # If we couldn't fulfill the entire request (shouldn't happen due to validation)
        if remaining_to_reduce > 0:
            raise ValueError(f"Could not fulfill complete request. {remaining_to_reduce} units remaining.")

        return stock_outs_created

    def redirect_back(self, drug):
        """Redirect back to appropriate page"""
        # You can customize this based on where you want to redirect
        # For now, assuming we go back to drug detail or drug list
        return redirect(reverse('drug_detail', kwargs={'pk': drug.pk}))


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
@permission_required('pharmacy.add_drugtransfermodel')
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


@login_required
@permission_required('pharmacy.add_drugordermodel', raise_exception=True)
def drug_dispense_page(request):
    """Main drug dispensing page"""
    return render(request, 'pharmacy/dispense/dispense.html')


@login_required
def verify_patient_pharmacy_ajax(request):
    """Verify patient and get drug orders for dispensing - CLAIM-BASED VERSION"""
    card_number = request.GET.get('card_number', '').strip()

    if not card_number:
        return JsonResponse({'error': 'Card number required'}, status=400)

    try:
        patient = PatientModel.objects.get(card_number__iexact=card_number)

        # Get or create wallet
        wallet, created = PatientWalletModel.objects.get_or_create(
            patient=patient,
            defaults={'amount': Decimal('0.00')}
        )

        # Get active insurance for display
        active_insurance = None
        try:
            policies_qs = patient.insurance_policies.all()
        except Exception:
            try:
                policies_qs = patient.insurancepolicy_set.all()
            except:
                policies_qs = PatientInsuranceModel.objects.none()

        active_insurance = policies_qs.filter(
            is_active=True,
            valid_to__gte=timezone.now().date()
        ).select_related('hmo', 'coverage_plan').first()

        # Get ready to dispense orders (paid but not fully dispensed)
        ready_to_dispense_qs = DrugOrderModel.objects.filter(
            patient=patient,
            status__in=['paid', 'partially_dispensed']
        ).exclude(
            quantity_dispensed__gte=F('quantity_ordered')
        ).select_related('drug').order_by('-ordered_at')

        # Get unpaid orders
        unpaid_orders_qs = DrugOrderModel.objects.filter(
            patient=patient,
            status='pending'
        ).select_related('drug').order_by('-ordered_at')

        # Process ready_to_dispense with claim info (for display context)
        ready_items = []
        for order in ready_to_dispense_qs:
            ready_items.append({
                'id': order.id,
                'order_number': order.order_number,
                'drug_name': f"{order.drug.__str__()}",
                'quantity_left': float(order.drug.store_quantity),
                'quantity_ordered': float(order.quantity_ordered),
                'quantity_dispensed': float(order.quantity_dispensed),
                'remaining_quantity': float(order.remaining_to_dispense),
                'dosage_instructions': order.dosage_instructions,
                'duration': order.duration,
                'status': order.status,
                'ordered_date': order.ordered_at.strftime('%Y-%m-%d')
            })

        # Process unpaid orders with claim-based logic
        unpaid_results = get_orders_with_claim_info(unpaid_orders_qs, 'drug')

        unpaid_items = []
        for result in unpaid_results:
            order = result['order']
            unpaid_items.append({
                'id': order.id,
                'order_number': order.order_number,
                'drug_name': f"{order.drug.__str__()}",
                'quantity_ordered': float(order.quantity_ordered),
                'price_per_unit': float(order.drug.selling_price),
                'base_amount': float(result['base_amount']),
                'patient_amount': float(result['patient_amount']),
                'covered_amount': float(result['covered_amount']),
                'total_amount': float(result['patient_amount']),  # Use patient_amount instead
                'dosage_instructions': order.dosage_instructions,
                'duration': order.duration,
                'status': order.status,
                'ordered_date': order.ordered_at.strftime('%Y-%m-%d'),
                'has_approved_claim': result['has_approved_claim'],
                'claim_number': result['claim_number'],
                'claim_status': result['claim_status'],
                'has_pending_claim': result['has_pending_claim'],
                'pending_claim_number': result['pending_claim_number'],
            })

        # Count pending claims
        pending_claims_count = sum(1 for item in unpaid_items if item.get('has_pending_claim'))

        return JsonResponse({
            'success': True,
            'patient': {
                'id': patient.id,
                'full_name': str(patient),
                'card_number': patient.card_number,
                'phone': getattr(patient, 'mobile', ''),
                'email': getattr(patient, 'email', ''),
                'age': patient.age() if hasattr(patient, 'age') and callable(patient.age) else '',
                'gender': getattr(patient, 'gender', ''),
            },
            'wallet': {
                'balance': float(wallet.amount),
                'formatted_balance': f'₦{wallet.amount:,.2f}'
            },
            'insurance': {
                'has_active': active_insurance is not None,
                'hmo_name': active_insurance.hmo.name if active_insurance else None,
                'plan_name': active_insurance.coverage_plan.name if active_insurance else None,
            } if active_insurance else None,
            'drug_orders': {
                'ready_to_dispense': ready_items,
                'unpaid_orders': unpaid_items
            },
            'pending_claims_count': pending_claims_count
        })

    except PatientModel.DoesNotExist:
        return JsonResponse({
            'error': 'Patient not found with this card number'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'error': f'Error verifying patient: {str(e)}'
        }, status=500)


@login_required
@permission_required('pharmacy.change_drugordermodel', raise_exception=True)
@transaction.atomic
def process_dispense_ajax(request):
    """Process drug dispensing and/or payments with pharmacy stock management - CLAIM-BASED VERSION"""
    from insurance.claim_helpers import calculate_patient_amount_with_claim

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        patient_id = request.POST.get('patient_id')
        dispense_items = json.loads(request.POST.get('dispense_items', '[]'))
        payment_items = json.loads(request.POST.get('payment_items', '[]'))

        if not patient_id:
            return JsonResponse({'error': 'Patient ID required'}, status=400)

        patient = get_object_or_404(PatientModel, id=patient_id)
        wallet = PatientWalletModel.objects.get_or_create(
            patient=patient,
            defaults={'amount': Decimal('0.00')}
        )[0]

        dispensed_count = 0
        paid_count = 0
        total_payment = Decimal('0.00')

        # Process payments first WITH CLAIM-BASED LOGIC
        if payment_items:
            payment_orders = DrugOrderModel.objects.filter(
                id__in=payment_items,
                patient=patient,
                status='pending'
            ).select_related('drug')

            order_details = []
            for order in payment_orders:
                # Calculate base amount
                base_amount = Decimal(order.drug.selling_price) * Decimal(order.quantity_ordered)

                # Use claim-based calculation
                claim_info = calculate_patient_amount_with_claim(order, base_amount)
                patient_amount = claim_info['patient_amount']

                total_payment += _quantize_money(patient_amount)
                order_details.append({
                    'order': order,
                    'base_amount': base_amount,
                    'patient_amount': patient_amount,
                    'covered_amount': claim_info['covered_amount'],
                    'has_claim': claim_info['has_approved_claim'],
                    'claim_number': claim_info['claim_number']
                })

            # Check wallet balance
            if wallet.amount < total_payment:
                shortfall = _quantize_money(total_payment - wallet.amount)
                return JsonResponse({
                    'error': f'Insufficient wallet balance. Required: ₦{total_payment:,.2f}, Available: ₦{wallet.amount:,.2f}',
                    'shortfall': float(shortfall)
                }, status=400)

            old_balance = wallet.amount

            # Process payments
            for detail in order_details:
                order = detail['order']
                patient_amount = detail['patient_amount']

                # Deduct from wallet
                wallet.amount -= patient_amount

                # Update order status
                order.status = 'paid'
              
                order.quantity_paid = order.quantity_ordered
                order.save(update_fields=['status', 'quantity_paid'])

                paid_count += 1

                # Create transaction record for this order
                PatientTransactionModel.objects.create(
                    patient=patient,
                    transaction_type='drug_payment',
                    transaction_direction='out',
                    amount=patient_amount,
                    old_balance=old_balance,
                    new_balance=wallet.amount,
                    date=timezone.now().date(),
                    received_by=request.user,
                    payment_method='wallet',
                    status='completed',
                )
                old_balance = wallet.amount  # Update for next iteration

            wallet.save()

            # Count claims applied
            claims_count = sum(1 for d in order_details if d['has_claim'])

        # Process dispensing with pharmacy stock management (unchanged)
        if dispense_items:
            for item in dispense_items:
                order_id = item.get('order_id')
                dispense_quantity = Decimal(str(item.get('quantity', 0)))

                try:
                    order = DrugOrderModel.objects.get(
                        id=order_id,
                        patient=patient,
                        status__in=['paid', 'partially_dispensed']
                    )

                    remaining_quantity = order.remaining_to_dispense

                    if dispense_quantity <= 0:
                        continue

                    if dispense_quantity > remaining_quantity:
                        return JsonResponse({
                            'error': f'Cannot dispense {dispense_quantity} of {order.drug.brand_name or order.drug.generic_name}. Only {remaining_quantity} remaining.'
                        }, status=400)

                    # Check if sufficient quantity in pharmacy
                    if order.drug.pharmacy_quantity < float(dispense_quantity):
                        return JsonResponse({
                            'error': f'Insufficient stock in pharmacy for {order.drug.brand_name or order.drug.generic_name}. '
                                     f'Requested: {dispense_quantity}, Available: {order.drug.pharmacy_quantity}'
                        }, status=400)

                    # Process FIFO stock reduction
                    try:
                        stock_outs_created = process_fifo_stock_reduction(
                            drug=order.drug,
                            quantity_to_reduce=float(dispense_quantity),
                            location='pharmacy',
                            reason='sale',
                            remark=f'Dispensed to patient {patient.__str__() or patient.registration_id}',
                            user=request.user
                        )
                    except ValueError as e:
                        return JsonResponse({
                            'error': f'Stock allocation error for {order.drug.brand_name or order.drug.generic_name}: {str(e)}'
                        }, status=400)

                    # Create dispense record
                    dispense_record = DispenseRecord.objects.create(
                        order=order,
                        dispensed_by=request.user,
                        dispensed_qty=dispense_quantity,
                        notes=f'Dispensed by {request.user.__str__() or request.user.username}. '
                              f'Stock reduced from {len(stock_outs_created)} stock entries.'
                    )

                    # Update order quantities
                    order.quantity_dispensed += float(dispense_quantity)

                    # Update dispensed_at timestamp
                    order.dispensed_at = timezone.now()
                    order.dispensed_by = request.user

                    # Update status based on dispensing completion
                    if order.quantity_dispensed >= order.quantity_ordered:
                        order.status = 'dispensed'
                    else:
                        order.status = 'partially_dispensed'

                    order.save()
                    dispensed_count += 1

                except DrugOrderModel.DoesNotExist:
                    return JsonResponse({
                        'error': f'Drug order {order_id} not found or not eligible for dispensing'
                    }, status=404)

        # Build success message
        messages = []
        if paid_count > 0:
            payment_msg = f'Paid for {paid_count} drug order(s) - ₦{total_payment:,.2f} deducted from wallet'
            if claims_count > 0:
                payment_msg += f'. Insurance claims applied to {claims_count} order(s)'
            messages.append(payment_msg)
        if dispensed_count > 0:
            messages.append(f'Dispensed {dispensed_count} drug order(s) from pharmacy stock')

        return JsonResponse({
            'success': True,
            'message': '. '.join(messages),
            'new_wallet_balance': float(wallet.amount),
            'formatted_balance': f'₦{wallet.amount:,.2f}'
        })

    except Exception as e:
        return JsonResponse({
            'error': f'Error processing request: {str(e)}'
        }, status=500)


def process_fifo_stock_reduction(drug, quantity_to_reduce, location, reason, remark, user):
    """
    Process FIFO stock reduction logic for dispensing
    Returns list of DrugStockOutModel objects created
    """
    from decimal import Decimal

    remaining_to_reduce = quantity_to_reduce

    # Get active stocks for this drug in FIFO order (oldest first)
    active_stocks = DrugStockModel.objects.filter(
        drug=drug,
        status='active',
        quantity_left__gt=0
    ).order_by('date_added')

    if not active_stocks.exists():
        raise ValueError("No active stocks available for this drug")

    stock_outs_created = []

    # Process each stock in FIFO order
    for stock in active_stocks:
        if remaining_to_reduce <= 0:
            break

        # Calculate how much to deduct from this stock
        quantity_from_this_stock = min(remaining_to_reduce, stock.quantity_left)

        # Create stock out record
        stock_out = DrugStockOutModel.objects.create(
            stock=stock,
            drug=drug,
            quantity=quantity_from_this_stock,
            reason=reason,
            location_reduced_from=location,
            worth=stock.selling_price * Decimal(str(quantity_from_this_stock)),
            remark=remark,
            created_by=user
        )
        stock_outs_created.append(stock_out)

        # Update stock quantity and worth
        stock.quantity_left -= quantity_from_this_stock
        stock.current_worth = Decimal(str(stock.quantity_left)) * stock.selling_price
        stock.save()

        # Update remaining quantity to reduce
        remaining_to_reduce -= quantity_from_this_stock

    # Update drug pharmacy quantity
    drug.pharmacy_quantity -= quantity_to_reduce
    drug.save()

    # If we couldn't fulfill the entire request (shouldn't happen due to validation)
    if remaining_to_reduce > 0:
        raise ValueError(f"Could not fulfill complete request. {remaining_to_reduce} units remaining.")

    return stock_outs_created


@login_required
@require_POST
@transaction.atomic
def create_pharmacy_order_ajax(request):
    """Creates a new drug order from the pharmacy dispense page for non-prescription drugs."""
    try:
        data = json.loads(request.body)
        patient_id = data.get('patient_id')
        drug_id = data.get('drug_id')
        quantity = data.get('quantity')

        if not all([patient_id, drug_id, quantity]):
            return JsonResponse({'error': 'Missing required data.'}, status=400)

        patient = get_object_or_404(PatientModel, id=patient_id)
        drug = get_object_or_404(DrugModel, id=drug_id)

        # Security check: Prevent sale of prescription-only drugs
        if drug.formulation.generic_drug.is_prescription_only:
            return JsonResponse({
                'error': f'Cannot sell "{drug.brand_name or drug.generic_name}". It is a prescription-only medication.'
            }, status=403) # 403 Forbidden

        # Create the new drug order
        DrugOrderModel.objects.create(
            patient=patient,
            drug=drug,
            quantity_ordered=float(quantity),
            ordered_by=request.user,
            status='pending',
            dosage_instructions='As directed by pharmacist.', # Default instruction
            duration='N/A'
        )

        return JsonResponse({'success': True, 'message': f'{drug.brand_name or drug.generic_name} added to unpaid orders.'})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format.'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'An unexpected error occurred: {str(e)}'}, status=500)


@login_required
def dispense_history_ajax(request):
    """Get dispensing history for a patient"""
    patient_id = request.GET.get('patient_id')

    if not patient_id:
        return JsonResponse({'error': 'Patient ID required'}, status=400)

    try:
        patient = get_object_or_404(PatientModel, id=patient_id)

        dispense_records = DispenseRecord.objects.filter(
            order__patient=patient
        ).select_related('order', 'order__drug', 'dispensed_by').order_by('-created_at')[:20]

        records = []
        for record in dispense_records:
            records.append({
                'id': record.id,
                'order_number': record.order.order_number,
                'drug_name': f"{record.order.drug.brand_name or record.order.drug.generic_name}",
                'dispensed_qty': float(record.dispensed_qty),
                'dispensed_by': record.dispensed_by.__str__() if record.dispensed_by else 'Unknown',
                'dispensed_at': record.created_at.strftime('%Y-%m-%d %H:%M'),
                'notes': record.notes
            })

        return JsonResponse({
            'success': True,
            'records': records
        })

    except Exception as e:
        return JsonResponse({
            'error': f'Error fetching history: {str(e)}'
        }, status=500)


@login_required
@permission_required('pharmacy.add_dispenserecord', raise_exception=True)
def general_dispense_view(request):
    # Defaults
    today = now().date()
    start_date = request.GET.get("start_date", today.strftime("%Y-%m-%d"))
    end_date = request.GET.get("end_date", today.strftime("%Y-%m-%d"))
    staff_id = request.GET.get("staff")
    drug_id = request.GET.get("drug")

    records = DispenseRecord.objects.all()

    # Filter date range
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        records = records.filter(created_at__date__range=[start_dt, end_dt])
    except Exception:
        records = records.filter(created_at__date=today)

    # Filter by staff
    if staff_id:
        records = records.filter(dispensed_by_id=staff_id)

    # Filter by drug (assuming order has a drug FK)
    if drug_id:
        records = records.filter(order__drug_id=drug_id)

    staffs = User.objects.filter(dispenserecord__isnull=False).distinct()
    drugs = DrugModel.objects.filter(drug_orders__isnull=False).distinct()

    # Pagination (20 per page)
    paginator = Paginator(records, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "start_date": start_date,
        "end_date": end_date,
        "staffs": staffs,
        "drugs": drugs,
        "staff_id": staff_id,
        "drug_id": drug_id,
    }
    return render(request, "pharmacy/dispense/index.html", context)


@permission_required('pharmacy.view_dispenserecord', raise_exception=True)
def patient_dispense_view(request, patient_id):
    patient = get_object_or_404(PatientModel, id=patient_id)
    records = DispenseRecord.objects.filter(order__patient=patient)

    # Pagination (20 per page)
    paginator = Paginator(records, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "patient": patient,
        "page_obj": page_obj,
    }
    return render(request, "pharmacy/dispense/patient_index.html", context)


def calculate_growth_percentage(current, previous):
    """Calculate growth percentage between two values"""
    if previous == 0:
        return 100 if current > 0 else 0
    return round(((current - previous) / previous) * 100, 1)


def get_low_stock_alerts():
    """Get drugs that are below minimum stock level"""
    return DrugModel.objects.filter(
        Q(store_quantity__lte=F('minimum_stock_level')) |
        Q(pharmacy_quantity__lte=F('minimum_stock_level'))
    ).select_related('formulation__generic_drug', 'manufacturer')


def get_expired_drugs():
    """Get expired drug stocks"""
    today = timezone.now().date()
    return DrugStockModel.objects.filter(
        expiry_date__lte=today,
        status='active',
        quantity_left__gt=0
    ).select_related('drug__formulation__generic_drug')


def get_near_expiry_drugs(days=30):
    """Get drugs expiring within specified days"""
    near_expiry_date = timezone.now().date() + timedelta(days=days)
    return DrugStockModel.objects.filter(
        expiry_date__lte=near_expiry_date,
        expiry_date__gt=timezone.now().date(),
        status='active',
        quantity_left__gt=0
    ).select_related('drug__formulation__generic_drug')


def get_sales_chart_data(days=7):
    """Get daily sales data for the last N days"""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days - 1)

    sales_data = []
    for i in range(days):
        current_date = start_date + timedelta(days=i)

        # Sales (stock outs with reason='sale')
        daily_sales = DrugStockOutModel.objects.filter(
            created_at__date=current_date,
            reason='sale'
        ).aggregate(
            total_quantity=Sum('quantity'),
            total_worth=Sum('worth')
        )

        # Orders completed
        daily_orders = DrugOrderModel.objects.filter(
            dispensed_at__date=current_date,
            status='dispensed'
        ).count()

        sales_data.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'sales_quantity': float(daily_sales['total_quantity'] or 0),
            'sales_worth': float(daily_sales['total_worth'] or 0),
            'orders_completed': daily_orders
        })

    return sales_data


def get_category_distribution():
    """Get drug distribution by category"""
    categories = DrugCategoryModel.objects.annotate(
        drug_count=Count('generic_drugs__formulations__products'),
        total_stock=Sum('generic_drugs__formulations__products__store_quantity') +
                    Sum('generic_drugs__formulations__products__pharmacy_quantity')
    ).filter(drug_count__gt=0)

    return [
        {
            'name': category.name,
            'value': category.drug_count,
            'stock': float(category.total_stock or 0)
        }
        for category in categories
    ]


def get_top_selling_drugs(limit=10):
    """Get top selling drugs by quantity"""
    return DrugStockOutModel.objects.filter(
        reason='sale',
        created_at__gte=timezone.now() - timedelta(days=30)
    ).values(
        'drug__formulation__generic_drug__generic_name',
        'drug__brand_name'
    ).annotate(
        total_sold=Sum('quantity'),
        total_revenue=Sum('worth')
    ).order_by('-total_sold')[:limit]


def get_inventory_value():
    """Calculate total inventory value from DrugModel aggregated quantities."""

    # choose precision that fits your data; adjust if you expect larger totals or more decimals
    DECIMAL_MAX_DIGITS = 18
    DECIMAL_DECIMAL_PLACES = 2
    DECIMAL_OUTPUT = DecimalField(max_digits=DECIMAL_MAX_DIGITS, decimal_places=DECIMAL_DECIMAL_PLACES)

    # Cast the float quantity to Decimal and multiply by the Decimal selling_price
    store_price_expr = ExpressionWrapper(
        Cast(F('store_quantity'), output_field=DECIMAL_OUTPUT) * F('selling_price'),
        output_field=DECIMAL_OUTPUT
    )

    pharmacy_price_expr = ExpressionWrapper(
        Cast(F('pharmacy_quantity'), output_field=DECIMAL_OUTPUT) * F('selling_price'),
        output_field=DECIMAL_OUTPUT
    )

    qs = DrugModel.objects.filter(is_active=True)

    store_value = qs.aggregate(total=Sum(store_price_expr))['total'] or Decimal('0.00')
    pharmacy_value = qs.aggregate(total=Sum(pharmacy_price_expr))['total'] or Decimal('0.00')

    total_value = store_value + pharmacy_value

    # return floats for compatibility with existing code; keep Decimal if you prefer precision
    return {
        'store_value': float(store_value),
        'pharmacy_value': float(pharmacy_value),
        'total_value': float(total_value)
    }


def get_monthly_trends(months=12):
    """Get monthly trends for sales and stock movements"""
    end_date = timezone.now().date()
    start_date = end_date.replace(day=1) - timedelta(days=30 * (months - 1))

    monthly_data = []
    current_date = start_date

    while current_date <= end_date:
        month_start = current_date.replace(day=1)
        if month_start.month == 12:
            month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)

        # Sales data
        monthly_sales = DrugStockOutModel.objects.filter(
            created_at__date__gte=month_start,
            created_at__date__lte=month_end,
            reason='sale'
        ).aggregate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum('worth')
        )

        # Stock additions
        monthly_additions = DrugStockModel.objects.filter(
            date_added__gte=month_start,
            date_added__lte=month_end
        ).aggregate(
            total_added=Sum('quantity_bought')
        )

        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'sales_quantity': float(monthly_sales['total_quantity'] or 0),
            'sales_revenue': float(monthly_sales['total_revenue'] or 0),
            'stock_added': float(monthly_additions['total_added'] or 0)
        })

        # Move to next month
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)

    return monthly_data


def get_pharmacy_dashboard_context(request):
    """Get comprehensive pharmacy dashboard context"""
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # Basic inventory statistics
    total_drugs = DrugModel.objects.filter(is_active=True).count()
    total_categories = DrugCategoryModel.objects.count()
    total_manufacturers = ManufacturerModel.objects.count()

    # Stock statistics
    total_stock_items = DrugStockModel.objects.filter(status='active').count()
    low_stock_count = get_low_stock_alerts().count()
    expired_count = get_expired_drugs().count()
    near_expiry_count = get_near_expiry_drugs().count()

    # Inventory values
    inventory_values = get_inventory_value()

    # Sales statistics
    today_sales = DrugStockOutModel.objects.filter(
        created_at__date=today,
        reason='sale'
    ).aggregate(
        quantity=Sum('quantity'),
        revenue=Sum('worth')
    )

    week_sales = DrugStockOutModel.objects.filter(
        created_at__date__gte=week_start,
        reason='sale'
    ).aggregate(
        quantity=Sum('quantity'),
        revenue=Sum('worth')
    )

    month_sales = DrugStockOutModel.objects.filter(
        created_at__date__gte=month_start,
        reason='sale'
    ).aggregate(
        quantity=Sum('quantity'),
        revenue=Sum('worth')
    )

    # Order statistics
    pending_orders = DrugOrderModel.objects.filter(status='pending').count()
    today_orders_completed = DrugOrderModel.objects.filter(
        dispensed_at__date=today,
        status='dispensed'
    ).count()

    # Recent transfers
    recent_transfers = DrugTransferModel.objects.filter(
        transferred_at__gte=week_start
    ).aggregate(
        total_quantity=Sum('quantity')
    )['total_quantity'] or 0

    # Growth calculations (compare with last month)
    last_month_start = (month_start - timedelta(days=1)).replace(day=1)
    last_month_end = month_start - timedelta(days=1)

    last_month_sales = DrugStockOutModel.objects.filter(
        created_at__date__gte=last_month_start,
        created_at__date__lte=last_month_end,
        reason='sale'
    ).aggregate(revenue=Sum('worth'))['revenue'] or 0

    revenue_growth = calculate_growth_percentage(
        float(month_sales['revenue'] or 0),
        float(last_month_sales)
    )

    # Chart data
    sales_chart_data = get_sales_chart_data()
    category_distribution = get_category_distribution()
    monthly_trends = get_monthly_trends()
    top_selling_drugs = list(get_top_selling_drugs())

    # Recent activity
    recent_stock_additions = DrugStockModel.objects.filter(
        date_added__gte=week_start
    ).select_related('drug__formulation__generic_drug').order_by('-created_at')[:5]

    return {
        # Basic counts
        'total_drugs': total_drugs,
        'total_categories': total_categories,
        'total_manufacturers': total_manufacturers,
        'total_stock_items': total_stock_items,

        # Alerts
        'low_stock_count': low_stock_count,
        'expired_count': expired_count,
        'near_expiry_count': near_expiry_count,
        'pending_orders': pending_orders,

        # Inventory values
        'store_inventory_value': inventory_values['store_value'],
        'pharmacy_inventory_value': inventory_values['pharmacy_value'],
        'total_inventory_value': inventory_values['total_value'],

        # Sales data
        'today_sales_quantity': float(today_sales['quantity'] or 0),
        'today_sales_revenue': float(today_sales['revenue'] or 0),
        'week_sales_quantity': float(week_sales['quantity'] or 0),
        'week_sales_revenue': float(week_sales['revenue'] or 0),
        'month_sales_quantity': float(month_sales['quantity'] or 0),
        'month_sales_revenue': float(month_sales['revenue'] or 0),
        'revenue_growth': revenue_growth,

        # Orders
        'today_orders_completed': today_orders_completed,
        'recent_transfers_quantity': float(recent_transfers),

        # Chart data (JSON serialized)
        'sales_chart_data': json.dumps(sales_chart_data),
        'category_distribution': json.dumps(category_distribution),
        'monthly_trends': json.dumps(monthly_trends),
        'top_selling_drugs': top_selling_drugs,

        # Recent activity
        'recent_stock_additions': recent_stock_additions,
        'low_stock_drugs': get_low_stock_alerts()[:10],  # Show top 10
        'expired_drugs': get_expired_drugs()[:10],
        'near_expiry_drugs': get_near_expiry_drugs()[:10],
    }


@login_required
def pharmacy_dashboard(request):
    """
    Comprehensive pharmacy dashboard with inventory, sales, and operational insights
    """
    context = get_pharmacy_dashboard_context(request)
    return render(request, 'pharmacy/dashboard.html', context)


@login_required
def pharmacy_dashboard_print(request):
    """
    Print-friendly version of pharmacy dashboard
    """
    context = get_pharmacy_dashboard_context(request)
    return render(request, 'pharmacy/dashboard_print.html', context)