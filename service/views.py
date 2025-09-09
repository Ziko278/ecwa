import logging
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.views.generic import (
    CreateView, ListView, UpdateView, DeleteView, DetailView
)

# Import forms and models from the service app
from .forms import ServiceCategoryForm, ServiceForm, ServiceItemForm
from .models import ServiceCategory, Service, ServiceItem, ServiceItemStockMovement

logger = logging.getLogger(__name__)


# -------------------------------------
# Service Category Views
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
        return context


class ServiceCategoryCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ServiceCategory
    permission_required = 'service.add_servicecategory'
    form_class = ServiceCategoryForm
    template_name = 'service/category/index.html'
    success_url = reverse_lazy('service_category_list')

    def form_valid(self, form):
        messages.success(self.request, 'Service Category created successfully.')
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Failed to create category. Please check the errors.')
        # Redirect back to the list view where errors can be displayed
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
# Service Views
# -------------------------------------

class ServiceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Service
    permission_required = 'service.view_service'
    template_name = 'service/service/index.html'
    context_object_name = "service_list"
    paginate_by = 20

    def get_queryset(self):
        return Service.objects.select_related('category').filter(is_active=True).order_by('category__name', 'name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ServiceForm()
        return context


class ServiceCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Service
    permission_required = 'service.add_service'
    form_class = ServiceForm
    template_name = 'service/service/index.html'
    success_url = reverse_lazy('service_list')

    def form_valid(self, form):
        messages.success(self.request, 'Service created successfully.')
        form.instance.created_by = self.request.user
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, 'Failed to create service. Please check the form.')
        return redirect('service_list')


class ServiceUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Service
    permission_required = 'service.change_service'
    form_class = ServiceForm
    template_name = 'service/service/edit.html'
    success_url = reverse_lazy('service_list')

    def form_valid(self, form):
        messages.success(self.request, 'Service updated successfully.')
        return super().form_valid(form)


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
# Service Item (Inventory) Views
# -------------------------------------

class ServiceItemListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = ServiceItem
    permission_required = 'service.view_serviceitem'
    template_name = 'service/item/index.html'
    context_object_name = "item_list"
    paginate_by = 20

    def get_queryset(self):
        return ServiceItem.objects.select_related('category').filter(is_active=True).order_by('name')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = ServiceItemForm()
        return context


class ServiceItemCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = ServiceItem
    permission_required = 'service.add_serviceitem'
    form_class = ServiceItemForm
    template_name = 'service/item/create.html' # Use a dedicated creation page
    success_url = reverse_lazy('service_item_list')

    def form_valid(self, form):
        try:
            with transaction.atomic():
                item = form.save(commit=False)
                item.created_by = self.request.user
                item.save()

                # Create initial stock movement record if stock is being added
                if item.stock_quantity > 0:
                    ServiceItemStockMovement.objects.create(
                        service_item=item,
                        movement_type='stock_in',
                        quantity=item.stock_quantity,
                        unit_cost=item.cost_price,
                        notes='Initial stock on item creation.',
                        created_by=self.request.user
                    )
                messages.success(self.request, f"Item '{item.name}' created successfully.")
        except Exception as e:
            logger.error(f"Error creating service item: {e}")
            messages.error(self.request, "An error occurred while creating the item.")
            return self.form_invalid(form)

        return redirect(self.success_url)


class ServiceItemDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = ServiceItem
    permission_required = 'service.view_serviceitem'
    template_name = 'service/item/detail.html'
    context_object_name = 'item'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        item = self.get_object()
        context['stock_movements'] = ServiceItemStockMovement.objects.filter(service_item=item).order_by('-created_at')
        return context


class ServiceItemUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = ServiceItem
    permission_required = 'service.change_serviceitem'
    form_class = ServiceItemForm
    template_name = 'service/item/edit.html'

    def get_success_url(self):
        return reverse('service_item_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, 'Item details updated successfully.')
        return super().form_valid(form)


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
# Stock Management (Function-Based Views)
# -------------------------------------

@login_required
@permission_required('service.change_serviceitemstockmovement', raise_exception=True)
def manage_stock(request, item_pk):
    """
    A view to handle adding and adjusting stock for a specific item.
    """
    item = get_object_or_404(ServiceItem, pk=item_pk)

    if request.method == 'POST':
        try:
            movement_type = request.POST.get('movement_type')
            quantity = int(request.POST.get('quantity', 0))
            unit_cost = request.POST.get('unit_cost', None)
            notes = request.POST.get('notes', '')

            if not movement_type or quantity <= 0:
                messages.error(request, "Invalid input. Movement type and a positive quantity are required.")
                return redirect('service_item_detail', pk=item.pk)

            # For movements that reduce stock, quantity should be negative
            if movement_type in ['stock_out', 'expired', 'adjustment_out']:
                if quantity > item.stock_quantity:
                    messages.error(request, "Cannot remove more stock than is available.")
                    return redirect('service_item_detail', pk=item.pk)
                quantity = -quantity # Make it negative

            with transaction.atomic():
                ServiceItemStockMovement.objects.create(
                    service_item=item,
                    movement_type=movement_type,
                    quantity=quantity,
                    unit_cost=float(unit_cost) if unit_cost else None,
                    notes=notes,
                    created_by=request.user
                )
            messages.success(request, "Stock level updated successfully.")

        except ValueError:
            messages.error(request, "Invalid number format for quantity or cost.")
        except Exception as e:
            logger.error(f"Error managing stock for item {item.pk}: {e}")
            messages.error(request, "An unexpected error occurred.")

        return redirect('service_item_detail', pk=item.pk)

    # Should not be accessed via GET
    return redirect('service_item_detail', pk=item.pk)


# -------------------------------------
# AJAX Views
# -------------------------------------

@login_required
def load_services_or_items_ajax(request):
    """
    AJAX view to fetch services or items based on a category ID.
    Used to populate dropdowns dynamically.
    """
    category_id = request.GET.get('category_id')
    if not category_id:
        return JsonResponse({'error': 'Category ID not provided'}, status=400)

    try:
        category = get_object_or_404(ServiceCategory, pk=category_id)
        services_data = []
        items_data = []

        # Fetch services if category type allows
        if category.category_type in ['service', 'mixed']:
            services = Service.objects.filter(category_id=category_id, is_active=True).values('id', 'name', 'price')
            services_data = list(services)

        # Fetch items if category type allows
        if category.category_type in ['item', 'mixed']:
            items = ServiceItem.objects.filter(category_id=category_id, is_active=True).values('id', 'name', 'price', 'stock_quantity')
            items_data = list(items)

        return JsonResponse({'services': services_data, 'items': items_data})

    except ServiceCategory.DoesNotExist:
        return JsonResponse({'error': 'Category not found'}, status=404)
    except Exception as e:
        logger.error(f"AJAX error loading services/items: {e}")
        return JsonResponse({'error': 'An internal error occurred'}, status=500)
