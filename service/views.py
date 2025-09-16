import json
import logging
from datetime import timedelta
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.db.models import Q, Sum, Count, Avg, F
from django.db.models.functions import TruncDate, Coalesce
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView, ListView, UpdateView, DeleteView, DetailView, TemplateView
)

# Import forms and models from the service app
from .forms import (
    ServiceCategoryForm, ServiceForm, ServiceItemForm, PatientServiceTransactionForm,
    ServiceItemStockMovementForm, ServiceResultForm, QuickTransactionForm, ServiceItemBatchForm,
    ServiceItemStockMovementFormSet
)
from .models import (
    ServiceCategory, Service, ServiceItem, ServiceItemStockMovement,
    PatientServiceTransaction, ServiceResult, ServiceItemBatch
)
from patient.models import PatientModel, PatientWalletModel
from finance.models import PatientTransactionModel

logger = logging.getLogger(__name__)


# -------------------------------------
# Service Category Views (Your Existing - Enhanced)
# -------------------------------------

class ServiceCategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ServiceCategory
    permission_required = 'service.view_servicecategory'
    template_name = 'service/category/index.html'
    context_object_name = "category_list"

    def get_queryset(self):
        return ServiceCategory.objects.all().order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ServiceCategoryForm()
        # Add statistics for dashboard
        context['stats'] = {
            'total_categories': ServiceCategory.objects.filter(is_active=True).count(),
            'service_categories': ServiceCategory.objects.filter(
                is_active=True, category_type__in=['service', 'mixed']
            ).count(),
            'item_categories': ServiceCategory.objects.filter(
                is_active=True, category_type__in=['item', 'mixed']
            ).count(),
        }
        return context


class ServiceCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ServiceCategory
    permission_required = 'service.add_servicecategory'
    form_class = ServiceCategoryForm
    template_name = 'service/category/index.html'
    success_url = reverse_lazy('service_category_list')

    def form_valid(self, form):
        messages.success(self.request, 'Service Category created successfully.')
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Failed to create category. Please check the errors.')
        return redirect('service_category_list')


class ServiceCategoryUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ServiceCategory
    permission_required = 'service.change_servicecategory'
    form_class = ServiceCategoryForm
    template_name = 'service/category/edit.html'
    success_url = reverse_lazy('service_category_list')

    def form_valid(self, form):
        messages.success(self.request, 'Service Category updated successfully.')
        return super().form_valid(form)


class ServiceCategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ServiceCategory
    permission_required = 'service.delete_servicecategory'
    template_name = 'service/category/delete.html'
    context_object_name = "category"
    success_url = reverse_lazy('service_category_list')

    def form_valid(self, form):
        messages.success(self.request, 'Service Category deleted successfully.')
        return super().form_valid(form)


# -------------------------------------
# Service Views (Your Existing - Enhanced)
# -------------------------------------

class ServiceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Service
    permission_required = 'service.view_service'
    template_name = 'service/service/index.html'
    context_object_name = "service_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = Service.objects.select_related('category').filter(is_active=True)

        # Add search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(category__name__icontains=search) |
                Q(description__icontains=search)
            )

        # Add category filter
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        return queryset.order_by('category__name', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ServiceForm()
        context['categories'] = ServiceCategory.objects.filter(
            is_active=True, category_type__in=['service', 'mixed']
        )
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_category'] = self.request.GET.get('category', '')
        return context


class ServiceCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Service
    permission_required = 'service.add_service'
    form_class = ServiceForm
    template_name = 'service/service/create.html'

    def get_success_url(self):
        """Redirect to the detail page of the service that was just created."""
        messages.success(self.request, 'Service created successfully.')
        return reverse('service_detail', kwargs={'pk': self.object.pk})


class ServiceDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Service
    permission_required = 'service.view_service'
    template_name = 'service/service/detail.html'
    context_object_name = 'service'


class ServiceUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Service
    permission_required = 'service.change_service'
    form_class = ServiceForm
    template_name = 'service/service/edit.html'

    def get_success_url(self):
        """Redirect to the detail page of the service that was just created."""
        messages.success(self.request, 'Service created successfully.')
        return reverse('service_detail', kwargs={'pk': self.object.pk})


class ServiceDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Service
    permission_required = 'service.delete_service'
    template_name = 'service/service/delete.html'
    context_object_name = 'service'
    success_url = reverse_lazy('service_list')

    def form_valid(self, form):
        messages.success(self.request, 'Service deleted successfully.')
        return super().form_valid(form)


# -------------------------------------
# Service Item Views (Your Existing - Enhanced)
# -------------------------------------

class ServiceItemListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ServiceItem
    permission_required = 'service.view_serviceitem'
    template_name = 'service/item/index.html'
    context_object_name = "item_list"
    paginate_by = 20

    def get_queryset(self):
        queryset = ServiceItem.objects.select_related('category').filter(is_active=True)

        # Add search functionality
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(category__name__icontains=search) |
                Q(model_number__icontains=search) |
                Q(description__icontains=search)
            )

        # Add category filter
        category_id = self.request.GET.get('category')
        if category_id:
            queryset = queryset.filter(category_id=category_id)

        # Add stock status filter
        stock_status = self.request.GET.get('stock_status')
        if stock_status == 'low':
            queryset = queryset.filter(stock_quantity__lte=F('minimum_stock_level'))
        elif stock_status == 'out':
            queryset = queryset.filter(stock_quantity=0)

        return queryset.order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ServiceItemForm()
        context['categories'] = ServiceCategory.objects.filter(
            is_active=True, category_type__in=['item', 'mixed']
        )
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_category'] = self.request.GET.get('category', '')
        context['stock_status'] = self.request.GET.get('stock_status', '')

        # Add inventory statistics
        context['inventory_stats'] = {
            'total_items': ServiceItem.objects.filter(is_active=True).count(),
            'low_stock_items': ServiceItem.objects.filter(
                is_active=True, stock_quantity__lte=F('minimum_stock_level')
            ).count(),
            'out_of_stock_items': ServiceItem.objects.filter(
                is_active=True, stock_quantity=0
            ).count(),
            'total_value': ServiceItem.objects.filter(is_active=True).aggregate(
                total=Sum(F('stock_quantity') * F('cost_price'))
            )['total'] or 0,
        }
        return context


#
# CORRECTED CODE
#
class ServiceItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ServiceItem
    permission_required = 'service.add_serviceitem'
    form_class = ServiceItemForm
    template_name = 'service/item/create.html'

    # We redirect to the detail page for better user experience
    def get_success_url(self):
        messages.success(self.request, f"Item '{self.object.name}' created successfully.")
        return reverse('service_item_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        # The quantity from the form for the initial stock movement
        initial_stock_quantity = form.cleaned_data.get('stock_quantity', 0)

        try:
            with transaction.atomic():
                # Step 1: Create the item in memory but DON'T save to the DB yet
                item = form.save(commit=False)

                # Step 2: Manually set its initial stock to 0 before its first save
                item.stock_quantity = 0

                # Step 3: Now, save the item to the database. It now exists with a stock of 0.
                item.save()
                self.object = item  # Set self.object for get_success_url

                # Step 4: If an initial quantity was provided, create the movement record.
                # This will now correctly read previous_stock as 0 and update it to 15.
                if initial_stock_quantity > 0:
                    ServiceItemStockMovement.objects.create(
                        service_item=item,
                        movement_type='stock_in',
                        quantity=initial_stock_quantity,
                        unit_cost=item.cost_price,
                        reference_type='purchase',
                        notes='Initial stock on item creation.',
                    )
        except Exception as e:
            logger.error(f"Error creating service item: {e}")
            messages.error(self.request, "An error occurred while creating the item.")
            return self.form_invalid(form)

        return redirect(self.get_success_url())


class ServiceItemDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ServiceItem
    permission_required = 'service.view_serviceitem'
    template_name = 'service/item/detail.html'
    context_object_name = 'item'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()
        context['stock_movements'] = ServiceItemStockMovement.objects.filter(
            service_item=item
        ).order_by('-created_at')[:20]
        context['stock_form'] = ServiceItemStockMovementForm(initial={'service_item': item})
        context['recent_transactions'] = PatientServiceTransaction.objects.filter(
            service_item=item
        ).select_related('patient').order_by('-created_at')[:10]
        return context


class ServiceItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ServiceItem
    permission_required = 'service.change_serviceitem'
    form_class = ServiceItemForm
    template_name = 'service/item/edit.html'
    context_object_name = 'item'

    def get_form(self, form_class=None):
        """Get the form instance and disable the stock_quantity field."""
        form = super().get_form(form_class)
        # This tells Django to render the field as disabled
        # and not to expect a value for it from the user.
        form.fields['stock_quantity'].disabled = True
        return form

    def get_success_url(self):
        """Redirect to the detail page of the item that was just updated."""
        messages.success(self.request, 'Item updated successfully.')
        # We will create this 'service_item_detail' page next
        return reverse('service_item_detail', kwargs={'pk': self.object.pk})


class ServiceItemDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ServiceItem
    permission_required = 'service.delete_serviceitem'
    template_name = 'service/item/delete.html'
    context_object_name = 'item'
    success_url = reverse_lazy('service_item_list')

    def form_valid(self, form):
        messages.success(self.request, 'Item deleted successfully.')
        return super().form_valid(form)


# -------------------------------------
# Service Item Batch Management (New)
# -------------------------------------


class ServiceItemBatchCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ServiceItemBatch
    permission_required = 'service.add_serviceitembatch'
    form_class = ServiceItemBatchForm

    def get_success_url(self):
        # After creating a batch, we'll redirect to the page for adding stock to it.
        # This is a key part of the workflow.
        messages.success(self.request, 'New batch created successfully. Now add items to it.')
        return reverse('service_item_stock_add', kwargs={'batch_pk': self.object.pk})

    def dispatch(self, request, *args, **kwargs):
        # A simple POST-only view. A GET request likely means the user
        # just wants to see the list, which might have a "Create New Batch" button.
        if request.method == 'GET':
            return redirect(reverse('service_item_batch_list'))
        return super().dispatch(request, *args, **kwargs)


class ServiceItemBatchListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ServiceItemBatch
    permission_required = 'service.view_serviceitembatch'
    template_name = 'service/batch/index.html'
    context_object_name = "batch_list"
    paginate_by = 15

    def get_queryset(self):
        return ServiceItemBatch.objects.all().order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ServiceItemBatchForm()
        # Get the last batch to enable the 'edit' button in the template
        try:
            context['last_batch'] = ServiceItemBatch.objects.latest('created_at')
        except ServiceItemBatch.DoesNotExist:
            context['last_batch'] = None
        return context


class ServiceItemBatchUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ServiceItemBatch
    permission_required = 'service.change_serviceitembatch'
    form_class = ServiceItemBatchForm

    def get_object(self, queryset=None):
        """Ensures that only the last created item batch can be updated."""
        requested_pk = self.kwargs.get('pk')
        try:
            last_batch = ServiceItemBatch.objects.latest('created_at')
        except ServiceItemBatch.DoesNotExist:
            messages.error(self.request, "No batches exist to update.")
            return HttpResponseRedirect(self.get_success_url())

        if last_batch.pk != requested_pk:
            attempted_batch_name = get_object_or_404(ServiceItemBatch, pk=requested_pk).name
            messages.error(
                self.request,
                f"Only the last created batch ('{last_batch.name}') can be updated. "
                f"You attempted to update batch '{attempted_batch_name}'."
            )
            return HttpResponseRedirect(self.get_success_url())
        return last_batch

    def get_success_url(self):
        return reverse('service_item_batch_list')

    def dispatch(self, request, *args, **kwargs):
        """Handle GET redirect and short-circuiting from get_object."""
        obj = self.get_object()
        if isinstance(obj, HttpResponseRedirect):
            return obj

        self.object = obj
        if request.method == 'GET':
            return redirect(self.get_success_url())

        messages.success(self.request, f"Batch '{self.object.name}' updated successfully.")
        return super().dispatch(request, *args, **kwargs)


class ServiceItemBatchDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = ServiceItemBatch
    permission_required = 'service.delete_serviceitembatch'
    template_name = 'service/batch/delete.html'
    context_object_name = "batch"

    def get_object(self, queryset=None):
        """Ensures that only the last created item batch can be deleted."""
        requested_pk = self.kwargs.get('pk')
        try:
            last_batch = ServiceItemBatch.objects.latest('created_at')
        except ServiceItemBatch.DoesNotExist:
            messages.error(self.request, "No batches exist to delete.")
            return HttpResponseRedirect(self.get_success_url())

        if last_batch.pk != requested_pk:
            attempted_batch_name = get_object_or_404(ServiceItemBatch, pk=requested_pk).name
            messages.error(
                self.request,
                f"Only the last created batch ('{last_batch.name}') can be deleted. "
                f"You attempted to delete batch '{attempted_batch_name}'."
            )
            return HttpResponseRedirect(self.get_success_url())
        return last_batch

    def form_valid(self, form):
        messages.success(self.request,
                         f"Batch '{self.object.name}' and all associated stock entries have been deleted.")
        return super().form_valid(form)

    def get_success_url(self):
        return reverse('service_item_batch_list')

    def dispatch(self, request, *args, **kwargs):
        """Handle HttpResponseRedirect from get_object."""
        obj = self.get_object()
        if isinstance(obj, HttpResponseRedirect):
            return obj
        self.object = obj
        return super().dispatch(request, *args, **kwargs)


class AddStockToBatchView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    permission_required = 'service.add_serviceitemstockmovement'
    template_name = 'service/batch/add_stock.html'

    def get_batch(self, **kwargs):
        """Helper to get the batch object from the URL."""
        batch_pk = self.kwargs.get('batch_pk')
        return get_object_or_404(ServiceItemBatch, pk=batch_pk)

    def get(self, request, *args, **kwargs):
        batch = self.get_batch(**kwargs)
        formset = ServiceItemStockMovementFormSet(
            queryset=ServiceItemStockMovement.objects.none()
        )
        context = {
            'formset': formset,
            'batch': batch,
            'title': f'Add Stock to Batch {batch.name}'
        }
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        batch = self.get_batch(**kwargs)
        formset = ServiceItemStockMovementFormSet(request.POST)

        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                instance.batch = batch
                instance.created_by = request.user
                instance.movement_type = 'stock_in' # Explicitly set the type
                instance.save() # This will trigger the stock update in the model's save()

            messages.success(request, f"Successfully added {len(instances)} item(s) to batch {batch.name}.")
            return redirect('service_item_batch_list')
        else:
            messages.error(request, "Please correct the errors below.")
            context = {
                'formset': formset,
                'batch': batch,
                'title': f'Add Stock to Batch {batch.name}'
            }
            return self.render_to_response(context)


class ServiceItemBatchDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ServiceItemBatch
    permission_required = 'service.view_serviceitembatch'
    template_name = 'service/batch/detail.html'
    context_object_name = 'batch'

    # In your ServiceItemBatchDetailView

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        batch = self.get_object()

        stock_entries = batch.stock_entries.select_related('service_item').all()

        # --- THIS IS THE FIX ---
        # Pre-calculate the total cost for each entry and add it to the object
        for entry in stock_entries:
            if entry.quantity and entry.unit_cost:
                entry.total_cost = entry.quantity * entry.unit_cost
            else:
                entry.total_cost = 0
        # --- END OF FIX ---

        context['stock_entries'] = stock_entries

        # ... the rest of your context data (totals, etc.) remains the same
        totals = stock_entries.aggregate(
            total_items=Sum('quantity'),
            total_cost=Sum(F('quantity') * F('unit_cost'))
        )
        context['total_items'] = totals.get('total_items') or 0
        context['total_cost'] = totals.get('total_cost') or 0

        try:
            context['is_last_batch'] = (ServiceItemBatch.objects.latest('created_at').pk == batch.pk)
        except ServiceItemBatch.DoesNotExist:
            context['is_last_batch'] = False

        return context

# -------------------------------------
# Stock Management Views (Enhanced)
# -------------------------------------
@login_required
@permission_required('service.add_serviceitemstockmovement', raise_exception=True)
def manage_stock(request, item_pk):
    """Enhanced stock management with proper form handling"""
    item = get_object_or_404(ServiceItem, pk=item_pk)

    if request.method == 'POST':
        form = ServiceItemStockMovementForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # 1. Create the object in memory, but don't save to DB yet.
                    stock_movement = form.save(commit=False)

                    # 2. Attach the logged-in user.
                    stock_movement.created_by = request.user

                    # 3. Now, save the complete object to the database.
                    stock_movement.save()

                    messages.success(request, "Stock level updated successfully.")
            except Exception as e:
                logger.error(f"Error managing stock for item {item.pk}: {e}")
                messages.error(request, "An unexpected error occurred.")
        else:
            # Your existing error handling for invalid form
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    return redirect('service_item_detail', pk=item.pk)

class StockMovementListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ServiceItemStockMovement
    permission_required = 'service.view_serviceitemstockmovement'
    template_name = 'service/stock/movements.html'
    context_object_name = 'movements'
    paginate_by = 50

    def get_queryset(self):
        queryset = ServiceItemStockMovement.objects.select_related('service_item').order_by('-created_at')

        # Filter by item
        item_id = self.request.GET.get('item')
        if item_id:
            queryset = queryset.filter(service_item_id=item_id)

        # Filter by movement type
        movement_type = self.request.GET.get('movement_type')
        if movement_type:
            queryset = queryset.filter(movement_type=movement_type)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = ServiceItem.objects.filter(is_active=True)
        context['movement_types'] = ServiceItemStockMovement._meta.get_field('movement_type').choices
        context['selected_item'] = self.request.GET.get('item', '')
        context['selected_movement_type'] = self.request.GET.get('movement_type', '')
        return context


# -------------------------------------
# PATIENT SERVICE MANAGEMENT (NEW MAIN FEATURE)
# -------------------------------------

class PatientServiceDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
    """Main patient service management page"""
    permission_required = 'service.view_patientservicetransaction'
    template_name = 'service/patient/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        patient_id = kwargs['patient_id']
        patient = get_object_or_404(PatientModel, pk=patient_id, is_active=True)

        # Get or create patient wallet
        wallet, created = PatientWalletModel.objects.get_or_create(patient=patient)

        context.update({
            'patient': patient,
            'wallet': wallet,
            'categories': ServiceCategory.objects.filter(is_active=True),
            'transaction_form': PatientServiceTransactionForm(),
            'quick_form': QuickTransactionForm(),
        })

        # Get patient's service history
        context['recent_transactions'] = PatientServiceTransaction.objects.filter(
            patient=patient
        ).select_related('service', 'service_item').order_by('-created_at')[:10]

        # Get pending transactions
        context['pending_transactions'] = PatientServiceTransaction.objects.filter(
            patient=patient, payment_status='pending'
        ).select_related('service', 'service_item')

        # Patient service statistics
        context['patient_stats'] = {
            'total_transactions': PatientServiceTransaction.objects.filter(patient=patient).count(),
            'pending_amount': PatientServiceTransaction.objects.filter(
                patient=patient, payment_status__in=['pending', 'partial']
            ).aggregate(
                total=Sum('total_amount') - Sum('amount_paid')
            )['total'] or 0,
            'total_paid': PatientServiceTransaction.objects.filter(
                patient=patient, payment_status='paid'
            ).aggregate(total=Sum('total_amount'))['total'] or 0,
        }

        return context


@login_required
@permission_required('service.add_patientservicetransaction', raise_exception=True)
def create_patient_transaction(request, patient_id):
    """Create new service/item transaction for patient"""
    patient = get_object_or_404(PatientModel, pk=patient_id, is_active=True)

    if request.method == 'POST':
        form = PatientServiceTransactionForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    service_transaction = form.save(commit=False)
                    service_transaction.patient = patient
                    service_transaction.performed_by = request.user
                    service_transaction.save()

                    messages.success(request, 'Service/Item added successfully.')

            except Exception as e:
                logger.error(f"Error creating patient transaction: {e}")
                messages.error(request, "An error occurred while processing the request.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

    return redirect('patient_service_dashboard', patient_id=patient_id)


@login_required
@permission_required('service.change_patientservicetransaction', raise_exception=True)
def process_patient_payment(request, patient_id, transaction_id):
    """Process payment for patient service transaction using wallet"""
    patient = get_object_or_404(PatientModel, pk=patient_id)
    service_transaction = get_object_or_404(
        PatientServiceTransaction, pk=transaction_id, patient=patient
    )

    if request.method == 'POST':
        try:
            amount_to_pay = Decimal(request.POST.get('amount_to_pay', 0))
            if amount_to_pay <= 0:
                messages.error(request, "Invalid payment amount.")
                return redirect('patient_service_dashboard', patient_id=patient_id)

            wallet, created = PatientWalletModel.objects.get_or_create(patient=patient)

            if wallet.amount < amount_to_pay:
                messages.error(request,
                               f"Insufficient wallet balance. Available: ₦{wallet.amount:,.2f}, Required: ₦{amount_to_pay:,.2f}. "
                               "Please visit Finance to fund your wallet."
                               )
                return redirect('patient_service_dashboard', patient_id=patient_id)

            with transaction.atomic():
                # Deduct from wallet
                wallet.deduct_funds(amount_to_pay)

                # Update service transaction amount paid
                service_transaction.amount_paid += amount_to_pay

                # --- THIS IS THE CORRECTED LOGIC ---
                # Check if the transaction is now fully paid.
                if service_transaction.balance_due <= 0:
                    # If so, update the status to 'paid'.
                    service_transaction.status = 'paid'
                # If not fully paid, the status remains 'pending_payment'.
                # There is no 'partial' status anymore.

                service_transaction.save()

                # Create finance transaction record
                PatientTransactionModel.objects.create(
                    patient=patient,
                    transaction_type='service' if service_transaction.service else 'item',
                    transaction_direction='out',
                    service=service_transaction,
                    amount=amount_to_pay,
                    old_balance=wallet.amount + amount_to_pay,
                    new_balance=wallet.amount,
                    date=timezone.now().date(),
                    received_by=request.user,
                    payment_method='wallet',
                    status='completed'
                )

                messages.success(request, f"Payment of ₦{amount_to_pay:,.2f} processed successfully.")

        except ValueError:
            messages.error(request, "Invalid payment amount format.")
        except Exception as e:
            logger.error(f"Error processing payment: {e}")
            messages.error(request, "An error occurred while processing payment.")

    return redirect('patient_service_dashboard', patient_id=patient_id)


@login_required
@permission_required('service.change_patientservicetransaction', raise_exception=True)
def disburse_patient_items(request, patient_id, transaction_id):
    """
    Dispenses items to a patient, creates the stock movement record,
    and updates the transaction status.
    """
    patient = get_object_or_404(PatientModel, pk=patient_id)
    service_transaction = get_object_or_404(
        PatientServiceTransaction, pk=transaction_id, patient=patient, service_item__isnull=False
    )

    if request.method == 'POST':
        try:
            quantity_to_disburse = int(request.POST.get('quantity_to_disburse', 0))

            if quantity_to_disburse <= 0:
                messages.error(request, "Invalid disbursement quantity.")
                return redirect('patient_service_dashboard', patient_id=patient_id)

            # 1. Check against the new status field
            if service_transaction.status not in ['paid', 'partially_dispensed']:
                messages.error(request, "Item must be paid for before disbursement.")
                return redirect('patient_service_dashboard', patient_id=patient_id)

            # 2. Check against the remaining quantity property
            if quantity_to_disburse > service_transaction.quantity_remaining:
                messages.error(request,
                               f"Cannot disburse more than the remaining {service_transaction.quantity_remaining} items.")
                return redirect('patient_service_dashboard', patient_id=patient_id)

            with transaction.atomic():
                # 3. Explicitly create the stock movement to deduct from inventory
                ServiceItemStockMovement.objects.create(
                    service_item=service_transaction.service_item,
                    movement_type='sale',
                    quantity=-quantity_to_disburse,  # Negative for deduction
                    reference_type='sale',
                    reference_id=service_transaction.pk,
                    notes=f"Dispensed from transaction #{service_transaction.pk}",
                    created_by=request.user
                )

                # 4. Update the dispensed quantity on the transaction
                service_transaction.quantity_dispensed += quantity_to_disburse

                # 5. Update the transaction's overall status
                if service_transaction.quantity_remaining == 0:
                    service_transaction.status = 'fully_dispensed'
                else:
                    service_transaction.status = 'partially_dispensed'

                service_transaction.save()

                messages.success(request,
                                 f"Successfully disbursed {quantity_to_disburse} units of {service_transaction.service_item.name}.")

        except ValueError:
            messages.error(request, "Invalid quantity format.")
        except Exception as e:
            logger.error(f"Error disbursing items: {e}")
            messages.error(request, "An error occurred during disbursement.")

    return redirect('patient_service_dashboard', patient_id=patient_id)


# -------------------------------------
# Service Results Management
# -------------------------------------

# In service/views.py

class ItemOrderListView(LoginRequiredMixin, ListView):
    model = PatientServiceTransaction
    template_name = 'service/order/item_index.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        # Exclude items that are still pending payment
        queryset = PatientServiceTransaction.objects.filter(service_item__isnull=False) \
            .exclude(status='pending_payment') \
            .select_related('patient', 'service_item', 'service_item__category') \
            .order_by('-created_at')

        # --- Search Logic ---
        search_query = self.request.GET.get('q', '')
        search_date = self.request.GET.get('date', '')

        if search_query:
            queryset = queryset.filter(
                Q(patient__first_name__icontains=search_query) |
                Q(patient__last_name__icontains=search_query) |
                Q(patient__card_number__icontains=search_query) |
                Q(service_item__name__icontains=search_query) |
                Q(service_item__category__name__icontains=search_query)
            )

        if search_date:
            queryset = queryset.filter(created_at__date=search_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['search_date'] = self.request.GET.get('date', '')
        return context


class ServiceOrderListView(LoginRequiredMixin, ListView):
    model = PatientServiceTransaction
    template_name = 'service/order/service_index.html'
    context_object_name = 'orders'
    paginate_by = 20

    def get_queryset(self):
        queryset = PatientServiceTransaction.objects.filter(service__isnull=False)\
            .select_related('patient', 'service', 'service__category')\
            .order_by('-created_at')

        # --- Search Logic ---
        search_query = self.request.GET.get('q', '')
        search_date = self.request.GET.get('date', '')

        if search_query:
            queryset = queryset.filter(
                Q(patient__first_name__icontains=search_query) |
                Q(patient__last_name__icontains=search_query) |
                Q(patient__card_number__icontains=search_query) |
                Q(service__name__icontains=search_query) |
                Q(service__category__name__icontains=search_query)
            )

        if search_date:
            queryset = queryset.filter(created_at__date=search_date)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('q', '')
        context['search_date'] = self.request.GET.get('date', '')
        return context


class ServiceResultDetailView(LoginRequiredMixin, DetailView):
    model = ServiceResult
    template_name = 'service/result/detail.html'
    context_object_name = 'result'


class ServiceResultCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ServiceResult
    permission_required = 'service.add_serviceresult'
    form_class = ServiceResultForm
    template_name = 'service/result/create.html'

    def dispatch(self, request, *args, **kwargs):
        transaction_id = self.request.GET.get('transaction_id')
        if transaction_id:
            # Get the transaction object
            transaction = get_object_or_404(PatientServiceTransaction, pk=transaction_id)

            # Check if a 'result' object is already linked to this transaction.
            # hasattr() is a clean way to check for a OneToOne relationship.
            if hasattr(transaction, 'result'):
                existing_result = transaction.result
                messages.info(request,
                              "A result already exists for this service. You are being redirected to the edit page.")
                # Redirect to the edit page for the existing result
                return redirect('service_result_edit', pk=existing_result.pk)

        # If no transaction_id or no existing result, proceed as normal
        return super().dispatch(request, *args, **kwargs)

    def get_initial(self):
        initial = super().get_initial()
        transaction_id = self.request.GET.get('transaction_id')
        if transaction_id:
            initial['transaction'] = transaction_id
        return initial

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        transaction_id = self.request.GET.get('transaction_id')
        if transaction_id:
            try:
                # Find the transaction to get its related service
                transaction = PatientServiceTransaction.objects.get(pk=transaction_id)
                if transaction.service:
                    context['service_id'] = transaction.service.id
                    # Also pass the full transaction object for display purposes
                    context['transaction_object'] = transaction
            except PatientServiceTransaction.DoesNotExist:
                pass # Handle error as needed
        return context

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Service result recorded successfully.')
        return super().form_valid(form)

    def get_success_url(self):
        """Redirect to the detail page of the result that was just created."""
        messages.success(self.request, 'Service result recorded successfully.')
        return reverse('service_result_detail', kwargs={'pk': self.object.pk})


class ServiceResultUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ServiceResult
    permission_required = 'service.change_serviceresult'
    form_class = ServiceResultForm
    template_name = 'service/result/edit.html'
    context_object_name = 'result'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass the service_id to the template for the JS to use
        if self.object.transaction and self.object.transaction.service:
            context['service_id'] = self.object.transaction.service.id
        return context

    def get_success_url(self):
        """Redirect back to the detail page after a successful edit."""
        messages.success(self.request, 'Service result updated successfully.')
        return reverse('service_result_detail', kwargs={'pk': self.object.pk})


# -------------------------------------
# AJAX Views (Enhanced)
# -------------------------------------

@login_required
def load_services_or_items_ajax(request):
    """Enhanced AJAX view to fetch services or items based on category"""
    category_id = request.GET.get('category_id')
    item_type = request.GET.get('type', 'both')  # 'services', 'items', or 'both'

    if not category_id:
        return JsonResponse({'error': 'Category ID not provided'}, status=400)

    try:
        category = get_object_or_404(ServiceCategory, pk=category_id)
        response_data = {}

        # Fetch services if requested
        if item_type in ['services', 'both'] and category.category_type in ['service', 'mixed']:
            services = Service.objects.filter(
                category_id=category_id, is_active=True
            ).values('id', 'name', 'price', 'has_results')
            response_data['services'] = list(services)

        # Fetch items if requested
        if item_type in ['items', 'both'] and category.category_type in ['item', 'mixed']:
            items = ServiceItem.objects.filter(
                category_id=category_id, is_active=True
            ).values('id', 'name', 'price', 'stock_quantity', 'unit_of_measure')
            response_data['items'] = list(items)

        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"AJAX error loading services/items: {e}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)


@login_required
def search_items_ajax(request):
    """AJAX search for items"""
    search_term = request.GET.get('q', '')
    category_id = request.GET.get('category_id')

    if len(search_term) < 2:
        return JsonResponse({'items': []})

    queryset = ServiceItem.objects.filter(is_active=True)

    if category_id:
        queryset = queryset.filter(category_id=category_id)

    items = queryset.filter(
        Q(name__icontains=search_term) |
        Q(model_number__icontains=search_term)
    ).values('id', 'name', 'price', 'stock_quantity', 'unit_of_measure')[:10]

    return JsonResponse({'items': list(items)})


@login_required
def get_service_template_ajax(request, service_id):
    """Get result template for a service"""
    try:
        service = get_object_or_404(Service, pk=service_id)
        return JsonResponse({
            'has_results': service.has_results,
            'template': service.result_template or {}
        })
    except Exception as e:
        logger.error(f"Error getting service template: {e}")
        return JsonResponse({'error': 'Service not found'}, status=404)


@login_required
def patient_transaction_summary_ajax(request, patient_id):
    """Get patient transaction summary for dashboard"""
    try:
        patient = get_object_or_404(PatientModel, pk=patient_id)

        # Get summary data
        summary = PatientServiceTransaction.objects.filter(patient=patient).aggregate(
            total_amount=Sum('total_amount'),
            total_paid=Sum('amount_paid'),
            pending_count=Count('id', filter=Q(payment_status='pending')),
            paid_count=Count('id', filter=Q(payment_status='paid'))
        )

        # Get wallet balance
        wallet, created = PatientWalletModel.objects.get_or_create(patient=patient)

        return JsonResponse({
            'summary': summary,
            'wallet_balance': float(wallet.amount),
            'outstanding_balance': float((summary['total_amount'] or 0) - (summary['total_paid'] or 0))
        })

    except Exception as e:
        logger.error(f"Error getting patient summary: {e}")
        return JsonResponse({'error': 'Error loading summary'}, status=500)


# -------------------------------------
# Dashboard and Reports
# -------------------------------------


class ServiceDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'service/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = "Service & Inventory Dashboard"

        # --- Date Ranges ---
        today = timezone.now().date()
        seven_days_ago = today - timedelta(days=6)

        # --- KPI Card Calculations (no changes here) ---
        today_transactions = PatientServiceTransaction.objects.filter(created_at__date=today)
        context['total_revenue_today'] = today_transactions.aggregate(total=Sum('total_amount'))['total'] or 0
        context['transactions_today'] = today_transactions.count()
        low_stock_items = ServiceItem.objects.filter(is_active=True, stock_quantity__lte=F('minimum_stock_level'))
        context['low_stock_count'] = low_stock_items.count()
        context['out_of_stock_count'] = ServiceItem.objects.filter(is_active=True, stock_quantity=0).count()

        # --- Table/List Data (no changes here) ---
        context['recent_transactions'] = PatientServiceTransaction.objects.select_related(
            'patient', 'service', 'service_item'
        ).order_by('-created_at')[:5]
        context['low_stock_list'] = low_stock_items.order_by('stock_quantity')[:5]
        context['top_selling_items'] = PatientServiceTransaction.objects.filter(service_item__isnull=False,
                                                                                created_at__date=today) \
                                           .values('service_item__name').annotate(count=Sum('quantity')).order_by(
            '-count')[:5]

        # --- Chart Data ---
        # 1. Daily Sales Chart (Last 7 Days)
        daily_sales = PatientServiceTransaction.objects.filter(created_at__date__gte=seven_days_ago) \
            .annotate(date=TruncDate('created_at')) \
            .values('date') \
            .annotate(revenue=Sum('total_amount')) \
            .order_by('date')

        # THE FIX IS HERE: Convert the Decimal revenue to a string
        sales_dict = {sale['date'].strftime('%Y-%m-%d'): str(sale['revenue']) for sale in daily_sales}

        chart_data = []
        for i in range(7):
            day = seven_days_ago + timedelta(days=i)
            day_str = day.strftime('%Y-%m-%d')
            chart_data.append({'date': day_str, 'revenue': sales_dict.get(day_str, 0)})
        context['daily_sales_chart_data'] = json.dumps(chart_data)

        # 2. Revenue by Category (Pie Chart)
        category_revenue = PatientServiceTransaction.objects.annotate(
            category_name=Coalesce('service__category__name', 'service_item__category__name')
        ).values('category_name').annotate(total=Sum('total_amount')).order_by('-total')

        # AND THE FIX IS HERE: Convert the Decimal total to a string
        context['category_revenue_data'] = json.dumps([
            {'value': str(item['total']), 'name': item['category_name']} for item in category_revenue if
            item['category_name']
        ])

        return context


class PatientOrderPageView(LoginRequiredMixin, TemplateView):
    template_name = 'service/patient/order_page.html'


@login_required
def verify_patient_and_get_orders_ajax(request):
    card_number = request.GET.get('card_number')
    if not card_number:
        return JsonResponse({'error': 'Card number is required.'}, status=400)

    try:
        patient = PatientModel.objects.get(card_number=card_number)  # Assuming card_id field
        wallet, _ = PatientWalletModel.objects.get_or_create(patient=patient)

        transactions = PatientServiceTransaction.objects.filter(patient=patient).order_by('-created_at')

        # Group transactions
        pending_payment = []
        pending_action = []

        for tx in transactions:
            item_details = {
                'id': tx.id,
                'name': tx.service.name if tx.service else tx.service_item.name,
                'is_item': bool(tx.service_item),
                'total_amount': tx.total_amount,
                'balance_due': tx.balance_due,
                'quantity': tx.quantity,
                'quantity_dispensed': tx.quantity_dispensed,
                'quantity_remaining': tx.quantity_remaining,
                'has_results': tx.service.has_results if tx.service else False,
                'has_result_entry': hasattr(tx, 'results') and tx.results.exists(),
                'status': tx.get_status_display(),
            }
            if tx.status == 'pending_payment':
                pending_payment.append(item_details)
                # An action is pending if it's paid but not dispensed, or partially dispensed.
            elif tx.status in ['paid', 'partially_dispensed']:
                pending_action.append(item_details)

        return JsonResponse({
            'success': True,
            'patient': {
                'id': patient.id,
                'full_name': patient.__str__(),
                'card_number': patient.card_number,  # Assuming patient_id
            },
            'wallet': {
                'balance': wallet.amount,
                'formatted_balance': f'₦{wallet.amount:,.2f}'
            },
            'orders': {
                'pending_payment': pending_payment,
                'pending_action': pending_action,
            }
        })
    except PatientModel.DoesNotExist:
        return JsonResponse({'error': 'Patient with this card number not found.'}, status=404)


@require_POST
@login_required
@permission_required('service.add_patientservicetransaction')
def add_new_transaction_ajax(request):
    data = json.loads(request.body)
    try:
        patient = PatientModel.objects.get(pk=data['patient_id'])
        item = None
        if data.get('service_id'):
            item = Service.objects.get(pk=data['service_id'])
        else:
            item = ServiceItem.objects.get(pk=data['service_item_id'])

        # This creates the transaction. The model's default status is 'pending_payment'.
        PatientServiceTransaction.objects.create(
            patient=patient,
            service=item if isinstance(item, Service) else None,
            service_item=item if isinstance(item, ServiceItem) else None,
            quantity=int(data['quantity']),
            unit_price=item.price,
            discount=0,
            performed_by=request.user,
        )
        return JsonResponse({'success': True, 'message': f'{item.name} added to bill.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_POST
@login_required
@permission_required('service.change_patientservicetransaction')
def process_bulk_payments_ajax(request):
    data = json.loads(request.body)
    tx_ids = data.get('transaction_ids', [])
    patient = PatientModel.objects.get(pk=data['patient_id'])

    transactions_to_pay = PatientServiceTransaction.objects.filter(pk__in=tx_ids, patient=patient)
    total_due = sum(tx.balance_due for tx in transactions_to_pay)

    wallet, _ = PatientWalletModel.objects.get_or_create(patient=patient)

    if wallet.amount < total_due:
        return JsonResponse({
            'error': f"Insufficient wallet balance. Required: ₦{total_due:,.2f}, Available: ₦{wallet.amount:,.2f}. Please fund at Finance."
        }, status=400)

    try:
        with transaction.atomic():
            old_balance = wallet.amount
            wallet.deduct_funds(total_due)

            for tx in transactions_to_pay:
                amount_to_pay_for_tx = tx.balance_due
                tx.amount_paid += amount_to_pay_for_tx
                # The status is changed from 'pending_payment' to 'paid'.
                tx.status = 'paid'
                tx.save() # The simplified .save() method is called.

            # This part correctly records the financial transaction.
            PatientTransactionModel.objects.create(
                patient=patient,
                transaction_type='service_payment',
                transaction_direction='out',
                amount=total_due,
                old_balance=old_balance,
                new_balance=wallet.amount,
                date=timezone.now().date(),
                received_by=request.user,
                payment_method='wallet',
                status='completed'
            )
        return JsonResponse({'success': True, 'message': 'Payment successful.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@require_POST
@login_required
@permission_required('service.change_patientservicetransaction')
def process_bulk_dispense_ajax(request):
    data = json.loads(request.body)
    dispense_items = data.get('dispense_items', [])

    if not dispense_items:
        return JsonResponse({'error': 'No items selected for dispensing.'}, status=400)

    try:
        # Process all dispensing actions in a single database transaction
        with transaction.atomic():
            for item_data in dispense_items:
                tx = PatientServiceTransaction.objects.get(pk=item_data['transaction_id'])
                quantity_to_dispense = int(item_data['quantity'])

                # --- Validation for each item ---
                if tx.status not in ['paid', 'partially_dispensed']:
                    raise Exception(f"Item '{tx.service_item.name}' must be paid for before dispensing.")

                if quantity_to_dispense <= 0 or quantity_to_dispense > tx.quantity_remaining:
                    raise Exception(f"Invalid quantity '{quantity_to_dispense}' for item '{tx.service_item.name}'.")

                # --- Update logic for each item ---
                tx.quantity_dispensed += quantity_to_dispense
                if tx.quantity_remaining == 0:
                    tx.status = 'fully_dispensed'
                else:
                    tx.status = 'partially_dispensed'

                # The model's .save() method is called, which will now
                # correctly trigger the stock movement creation for the dispensed amount.
                tx.save()

        return JsonResponse(
            {'success': True, 'message': f'Successfully dispensed {len(dispense_items)} item(s).'})

    except PatientServiceTransaction.DoesNotExist:
        return JsonResponse({'error': 'One or more transactions not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def ajax_search_services_and_items(request):
    query = request.GET.get('q', '')
    if len(query) < 2:
        return JsonResponse({'results': []})

    services = Service.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query), is_active=True
    ).values('id', 'name', 'price')[:5]

    items = ServiceItem.objects.filter(
        Q(name__icontains=query) | Q(description__icontains=query), is_active=True, stock_quantity__gt=0
    ).values('id', 'name', 'price', 'stock_quantity')[:5]

    results = []
    for s in services:
        results.append({'id': s['id'], 'name': s['name'], 'price': s['price'], 'type': 'service', 'stock': 'N/A'})
    for i in items:
        results.append({'id': i['id'], 'name': i['name'], 'price': i['price'], 'type': 'item', 'stock': i['stock_quantity']})

    return JsonResponse({'results': results})