# import logging
# from decimal import Decimal
#
# from django.contrib import messages
# from django.contrib.auth.decorators import login_required, permission_required
# from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
# from django.db import transaction
# from django.db.models import Q, Sum, F
# from django.db.models.functions import Lower
# from django.http import JsonResponse
# from django.shortcuts import render, redirect, get_object_or_404
# from django.urls import reverse
# from django.utils import timezone
# from django.views.generic import (
#     CreateView, ListView, UpdateView, DeleteView, DetailView, TemplateView
# )
#
# from inventory.forms import (
#     UnitForm, SupplierForm, InventoryCategoryForm, InventoryItemForm,
#     StockRecordForm, StockUsageForm, StockUsageItemForm, StockDamageForm,
#     AssetForm, AssetMaintenanceForm, AssetDamageForm,
#     QuickStockInForm, QuickStockOutForm
# )
# from inventory.models import (
#     Unit, Supplier, InventoryCategory, InventoryItem, StockRecord,
#     StockUsage, StockUsageItem, StockDamage, Asset, AssetMaintenance,
#     AssetDamage, AssetPurchase
# )
# from human_resource.models import DepartmentModel
#
# logger = logging.getLogger(__name__)
#
#
# # -------------------------
# # Utility helpers
# # -------------------------
# class FlashFormErrorsMixin:
#     """
#     Mixin for CreateView/UpdateView to flash form errors and redirect safely.
#     Use before SuccessMessageMixin in MRO so messages appear before redirect.
#     """
#
#     def form_invalid(self, form):
#         try:
#             for field, errors in form.errors.items():
#                 label = form.fields.get(field).label if form.fields.get(field) else field
#                 for error in errors:
#                     messages.error(self.request, f"{label}: {error}")
#         except Exception:
#             logger.exception("Error while processing form_invalid errors.")
#             messages.error(self.request, "There was an error processing the form. Please try again.")
#         return redirect(self.get_success_url())
#
#
# # -------------------------
# # Unit Views
# # -------------------------
# class UnitCreateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
#     CreateView
# ):
#     model = Unit
#     permission_required = 'inventory.add_unit'
#     form_class = UnitForm
#     template_name = 'inventory/unit/index.html'
#     success_message = 'Unit Successfully Created'
#
#     def get_success_url(self):
#         return reverse('unit_index')
#
#     def dispatch(self, request, *args, **kwargs):
#         if request.method == 'GET':
#             return redirect(reverse('unit_index'))
#         return super().dispatch(request, *args, **kwargs)
#
#
# class UnitListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = Unit
#     permission_required = 'inventory.view_unit'
#     template_name = 'inventory/unit/index.html'
#     context_object_name = "unit_list"
#
#     def get_queryset(self):
#         return Unit.objects.all().order_by('name')
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['form'] = StockDamageForm()
#
#         # Damage statistics
#         total_damage_cost = StockDamage.objects.aggregate(
#             total=Sum('cost')
#         )['total'] or Decimal('0.00')
#         context['total_damage_cost'] = total_damage_cost
#
#         return context
#
#
# # -------------------------
# # Dashboard and Reports
# # -------------------------
# class InventoryDashboardView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
#     permission_required = 'inventory.view_inventoryitem'
#     template_name = 'inventory/dashboard.html'
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#
#         # Stock alerts
#         low_stock_items = InventoryItem.objects.filter(
#             quantity__lte=F('reorder_level'),
#             quantity__gt=F('min_level'),
#             is_active=True
#         ).select_related('category', 'unit')
#
#         critical_stock_items = InventoryItem.objects.filter(
#             quantity__lte=F('min_level'),
#             is_active=True
#         ).select_related('category', 'unit')
#
#         out_of_stock_items = InventoryItem.objects.filter(
#             quantity=0,
#             is_active=True
#         ).select_related('category', 'unit')
#
#         # Expired items
#         expired_items = InventoryItem.objects.filter(
#             expiry_date__lt=timezone.now().date(),
#             is_active=True
#         ).select_related('category', 'unit')
#
#         # Asset alerts
#         overdue_maintenance = Asset.objects.filter(
#             maintenances__next_due__lt=timezone.now().date(),
#             is_operational=True
#         ).distinct().select_related('department')
#
#         # Recent activities
#         recent_movements = StockRecord.objects.select_related(
#             'item', 'performed_by'
#         ).order_by('-created_at')[:10]
#
#         recent_usage = StockUsage.objects.select_related(
#             'performed_by', 'department'
#         ).order_by('-usage_date')[:5]
#
#         context.update({
#             'low_stock_items': low_stock_items,
#             'critical_stock_items': critical_stock_items,
#             'out_of_stock_items': out_of_stock_items,
#             'expired_items': expired_items,
#             'overdue_maintenance': overdue_maintenance,
#             'recent_movements': recent_movements,
#             'recent_usage': recent_usage,
#
#             # Summary counts
#             'total_items': InventoryItem.objects.filter(is_active=True).count(),
#             'total_assets': Asset.objects.count(),
#             'low_stock_count': low_stock_items.count(),
#             'critical_stock_count': critical_stock_items.count(),
#             'out_of_stock_count': out_of_stock_items.count(),
#             'expired_count': expired_items.count(),
#             'overdue_maintenance_count': overdue_maintenance.count(),
#         })
#         return context
#
#
# # -------------------------
# # AJAX Views for Dynamic Forms
# # -------------------------
# @login_required
# def get_items_by_category(request):
#     """Return items filtered by category for AJAX requests."""
#     category_id = request.GET.get('category_id')
#     if not category_id:
#         return JsonResponse({'error': 'category_id is required'}, status=400)
#
#     try:
#         items = InventoryItem.objects.filter(
#             category_id=category_id,
#             is_active=True
#         ).values('id', 'name', 'quantity', 'unit__name')
#
#         return JsonResponse({'items': list(items)})
#     except Exception:
#         logger.exception("Failed fetching items by category id=%s", category_id)
#         return JsonResponse({'error': 'Internal error'}, status=500)
#
#
# @login_required
# def get_item_stock_info(request):
#     """Return current stock info for an item."""
#     item_id = request.GET.get('item_id')
#     if not item_id:
#         return JsonResponse({'error': 'item_id is required'}, status=400)
#
#     try:
#         item = InventoryItem.objects.get(id=item_id)
#         data = {
#             'quantity': str(item.quantity),
#             'unit': item.unit.name if item.unit else '',
#             'last_purchase_price': str(item.last_purchase_price) if item.last_purchase_price else '',
#             'is_low_stock': item.is_low_stock,
#             'is_critical_stock': item.is_critical_stock,
#         }
#         return JsonResponse(data)
#     except InventoryItem.DoesNotExist:
#         return JsonResponse({'error': 'Item not found'}, status=404)
#     except Exception:
#         logger.exception("Failed fetching item stock info for id=%s", item_id)
#         return JsonResponse({'error': 'Internal error'}, status=500)
#
#
# # -------------------------
# # Bulk Actions
# # -------------------------
# def multi_item_action(request):
#     """Handle bulk actions on inventory items."""
#     if request.method == 'POST':
#         item_ids = request.POST.getlist('item')
#         action = request.POST.get('action')
#
#         if not item_ids:
#             messages.error(request, 'No items selected.')
#             return redirect(reverse('item_index'))
#
#         try:
#             with transaction.atomic():
#                 items = InventoryItem.objects.filter(id__in=item_ids)
#
#                 if action == 'delete':
#                     count, _ = items.delete()
#                     messages.success(request, f'Successfully deleted {count} item(s).')
#                 elif action == 'deactivate':
#                     count = items.update(is_active=False)
#                     messages.success(request, f'Successfully deactivated {count} item(s).')
#                 elif action == 'activate':
#                     count = items.update(is_active=True)
#                     messages.success(request, f'Successfully activated {count} item(s).')
#                 else:
#                     messages.error(request, 'Invalid action.')
#         except Exception:
#             logger.exception("Bulk item action failed for ids=%s action=%s", item_ids, action)
#             messages.error(request, "An error occurred performing that action. Try again or contact admin.")
#
#         return redirect(reverse('item_index'))
#
#     # GET - confirm action
#     item_ids = request.GET.getlist('item')
#     if not item_ids:
#         messages.error(request, 'No items selected.')
#         return redirect(reverse('item_index'))
#
#     action = request.GET.get('action')
#     context = {'item_list': InventoryItem.objects.filter(id__in=item_ids)}
#
#     if action == 'delete':
#         return render(request, 'inventory/item/multi_delete.html', context)
#     elif action in ['activate', 'deactivate']:
#         context['action'] = action
#         return render(request, 'inventory/item/multi_action.html', context)
#
#     messages.error(request, 'Invalid action.')
#     return redirect(reverse('item_index'))
#
#
# # -------------------------
# # Stock Adjustment Views
# # -------------------------
# @login_required
# @permission_required('inventory.add_stockrecord', raise_exception=True)
# def stock_adjustment(request):
#     """Handle stock adjustments (corrections)."""
#     if request.method == 'POST':
#         item_id = request.POST.get('item')
#         adjustment_type = request.POST.get('adjustment_type')  # 'in' or 'out'
#         quantity = request.POST.get('quantity')
#         reason = request.POST.get('reason', '')
#
#         try:
#             item = get_object_or_404(InventoryItem, id=item_id)
#             quantity = Decimal(quantity)
#
#             if quantity <= 0:
#                 messages.error(request, "Adjustment quantity must be positive.")
#                 return redirect(reverse('item_detail', kwargs={'pk': item_id}))
#
#             transaction_type = StockRecord.TYPE_ADJUST_IN if adjustment_type == 'in' else StockRecord.TYPE_ADJUST_OUT
#
#             with transaction.atomic():
#                 StockRecord.objects.create(
#                     item=item,
#                     transaction_type=transaction_type,
#                     quantity=quantity,
#                     reference=f"Stock Adjustment: {reason}",
#                     performed_by=request.user
#                 )
#
#             action_word = "increased" if adjustment_type == 'in' else "decreased"
#             messages.success(request, f"Stock {action_word} by {quantity} {item.unit}. New quantity: {item.quantity}")
#
#         except (ValueError, InvalidOperation):
#             messages.error(request, "Invalid quantity value.")
#         except Exception:
#             logger.exception("Error in stock adjustment")
#             messages.error(request, "An error occurred during stock adjustment. Contact admin.")
#
#     return redirect(request.META.get('HTTP_REFERER', reverse('item_index')))
#
#
# # -------------------------
# # Reports Views
# # -------------------------
# class LowStockReportView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = InventoryItem
#     permission_required = 'inventory.view_inventoryitem'
#     template_name = 'inventory/reports/low_stock.html'
#     context_object_name = "low_stock_items"
#
#     def get_queryset(self):
#         return InventoryItem.objects.filter(
#             quantity__lte=F('reorder_level'),
#             is_active=True
#         ).select_related('category', 'unit', 'department').order_by('quantity')
#
#
# class ExpiredItemsReportView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = InventoryItem
#     permission_required = 'inventory.view_inventoryitem'
#     template_name = 'inventory/reports/expired_items.html'
#     context_object_name = "expired_items"
#
#     def get_queryset(self):
#         return InventoryItem.objects.filter(
#             expiry_date__lt=timezone.now().date(),
#             is_active=True
#         ).select_related('category', 'unit', 'department').order_by('expiry_date')
#
#
# class StockValuationReportView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
#     permission_required = 'inventory.view_inventoryitem'
#     template_name = 'inventory/reports/stock_valuation.html'
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#
#         # Calculate stock valuation
#         items_with_value = InventoryItem.objects.filter(
#             is_active=True,
#             quantity__gt=0,
#             last_purchase_price__isnull=False
#         ).annotate(
#             total_value=F('quantity') * F('last_purchase_price')
#         ).select_related('category', 'unit', 'department')
#
#         total_valuation = items_with_value.aggregate(
#             total=Sum('total_value')
#         )['total'] or Decimal('0.00')
#
#         # Group by category
#         category_totals = {}
#         for item in items_with_value:
#             category = item.category.name if item.category else 'Uncategorized'
#             if category not in category_totals:
#                 category_totals[category] = Decimal('0.00')
#             category_totals[category] += item.total_value
#
#         context.update({
#             'items_with_value': items_with_value,
#             'total_valuation': total_valuation,
#             'category_totals': category_totals,
#         })
#         return context
#
#
# class AssetMaintenanceReportView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = Asset
#     permission_required = 'inventory.view_asset'
#     template_name = 'inventory/reports/maintenance_due.html'
#     context_object_name = "assets_needing_maintenance"
#
#     def get_queryset(self):
#         return Asset.objects.filter(
#             maintenances__next_due__lt=timezone.now().date(),
#             is_operational=True
#         ).distinct().select_related('department')
#
#
# # -------------------------
# # Recalculate Stock (Admin function)
# # -------------------------
# @login_required
# @permission_required('inventory.change_inventoryitem', raise_exception=True)
# def recalculate_all_stock(request):
#     """Recalculate all inventory item quantities from stock records."""
#     if request.method == 'POST':
#         try:
#             with transaction.atomic():
#                 items = InventoryItem.objects.all()
#                 count = 0
#                 for item in items:
#                     old_qty = item.quantity
#                     new_qty = item.recalc_quantity()
#                     if old_qty != new_qty:
#                         count += 1
#
#             messages.success(request, f"Successfully recalculated quantities for {count} items.")
#         except Exception:
#             logger.exception("Error recalculating stock quantities")
#             messages.error(request, "An error occurred while recalculating stock. Contact admin.")
#
#     return redirect(request.META.get('HTTP_REFERER', reverse('inventory_dashboard')))
#
#
# # -------------------------
# # Search and Filter Views
# # -------------------------
# @login_required
# def inventory_search(request):
#     """Global inventory search."""
#     query = request.GET.get('q', '').strip()
#
#     if not query:
#         return JsonResponse({'error': 'Search query is required'}, status=400)
#
#     try:
#         # Search inventory items
#         items = InventoryItem.objects.filter(
#             Q(name__icontains=query) |
#             Q(sku__icontains=query) |
#             Q(category__name__icontains=query),
#             is_active=True
#         ).select_related('category', 'unit')[:10]
#
#         # Search assets
#         assets = Asset.objects.filter(
#             Q(name__icontains=query) |
#             Q(serial_number__icontains=query) |
#             Q(asset_tag__icontains=query)
#         ).select_related('department')[:10]
#
#         items_data = [{
#             'id': item.id,
#             'name': item.name,
#             'sku': item.sku,
#             'category': item.category.name if item.category else '',
#             'quantity': str(item.quantity),
#             'unit': item.unit.name if item.unit else '',
#             'type': 'item'
#         } for item in items]
#
#         assets_data = [{
#             'id': asset.id,
#             'name': asset.name,
#             'serial_number': asset.serial_number,
#             'asset_tag': asset.asset_tag,
#             'department': asset.department.name if asset.department else '',
#             'type': 'asset'
#         } for asset in assets]
#
#         return JsonResponse({
#             'items': items_data,
#             'assets': assets_data
#         })
#     except Exception:
#         logger.exception("Error in inventory search for query=%s", query)
#         return JsonResponse({'error': 'Search failed'}, status=500)
#
#
# # -------------------------
# # Export Views (Optional)
# # -------------------------
# @login_required
# @permission_required('inventory.view_inventoryitem', raise_exception=True)
# def export_inventory_csv(request):
#     """Export inventory items to CSV."""
#     import csv
#     from django.http import HttpResponse
#
#     response = HttpResponse(content_type='text/csv')
#     response['Content-Disposition'] = 'attachment; filename="inventory_export.csv"'
#
#     writer = csv.writer(response)
#     writer.writerow([
#         'Name', 'SKU', 'Category', 'Type', 'Unit', 'Department',
#         'Current Quantity', 'Reorder Level', 'Min Level', 'Last Purchase Price',
#         'Expiry Date', 'Storage Location', 'Status'
#     ])
#
#     items = InventoryItem.objects.select_related(
#         'category', 'unit', 'department'
#     ).order_by('name')
#
#     for item in items:
#         writer.writerow([
#             item.name,
#             item.sku or '',
#             item.category.name if item.category else '',
#             item.get_item_type_display(),
#             item.unit.name if item.unit else '',
#             item.department.name if item.department else '',
#             str(item.quantity),
#             str(item.reorder_level),
#             str(item.min_level),
#             str(item.last_purchase_price) if item.last_purchase_price else '',
#             item.expiry_date.strftime('%Y-%m-%d') if item.expiry_date else '',
#             item.storage_location or '',
#             'Active' if item.is_active else 'Inactive'
#         ])
#
#     return response
#
#
# @login_required
# @permission_required('inventory.view_asset', raise_exception=True)
# def export_assets_csv(request):
#     """Export assets to CSV."""
#     import csv
#     from django.http import HttpResponse
#
#     response = HttpResponse(content_type='text/csv')
#     response['Content-Disposition'] = 'attachment; filename="assets_export.csv"'
#
#     writer = csv.writer(response)
#     writer.writerow([
#         'Name', 'Serial Number', 'Asset Tag', 'Type', 'Department',
#         'Location', 'Purchase Date', 'Purchase Cost', 'Vendor',
#         'Condition', 'Operational', 'Warranty Expiry', 'Current Value'
#     ])
#
#     assets = Asset.objects.select_related(
#         'department', 'vendor'
#     ).order_by('name')
#
#     for asset in assets:
#         writer.writerow([
#             asset.name,
#             asset.serial_number or '',
#             asset.asset_tag or '',
#             asset.get_asset_type_display(),
#             asset.department.name if asset.department else '',
#             asset.location or '',
#             asset.purchase_date.strftime('%Y-%m-%d') if asset.purchase_date else '',
#             str(asset.purchase_cost) if asset.purchase_cost else '',
#             asset.vendor.name if asset.vendor else '',
#             asset.get_condition_display(),
#             'Yes' if asset.is_operational else 'No',
#             asset.warranty_expiry.strftime('%Y-%m-%d') if asset.warranty_expiry else '',
#             str(asset.current_value()) if asset.current_value() else ''
#         ])
#
#     return response
#
#
# # -------------------------
# # Stock Transfer (Between Departments)
# # -------------------------
# @login_required
# @permission_required('inventory.add_stockrecord', raise_exception=True)
# def stock_transfer(request):
#     """Transfer stock between departments."""
#     if request.method == 'POST':
#         item_id = request.POST.get('item')
#         quantity = request.POST.get('quantity')
#         from_dept_id = request.POST.get('from_department')
#         to_dept_id = request.POST.get('to_department')
#         reference = request.POST.get('reference', '')
#
#         try:
#             item = get_object_or_404(InventoryItem, id=item_id)
#             quantity = Decimal(quantity)
#             from_dept = get_object_or_404(DepartmentModel, id=from_dept_id) if from_dept_id else None
#             to_dept = get_object_or_404(DepartmentModel, id=to_dept_id) if to_dept_id else None
#
#             if quantity <= 0:
#                 messages.error(request, "Transfer quantity must be positive.")
#                 return redirect(request.META.get('HTTP_REFERER', reverse('item_index')))
#
#             if quantity > item.quantity:
#                 messages.error(request, f"Insufficient stock. Available: {item.quantity}")
#                 return redirect(request.META.get('HTTP_REFERER', reverse('item_index')))
#
#             if from_dept == to_dept:
#                 messages.error(request, "Source and destination departments cannot be the same.")
#                 return redirect(request.META.get('HTTP_REFERER', reverse('item_index')))
#
#             with transaction.atomic():
#                 # Create transfer out record
#                 StockRecord.objects.create(
#                     item=item,
#                     transaction_type=StockRecord.TYPE_TRANSFER,
#                     quantity=quantity,
#                     department=from_dept,
#                     reference=f"Transfer to {to_dept.name if to_dept else 'Unknown'}: {reference}",
#                     performed_by=request.user
#                 )
#
#             messages.success(request, f"Successfully transferred {quantity} {item.unit} of {item.name}")
#
#         except (ValueError, InvalidOperation):
#             messages.error(request, "Invalid quantity value.")
#         except Exception:
#             logger.exception("Error in stock transfer")
#             messages.error(request, "An error occurred during stock transfer. Contact admin.")
#
#     return redirect(request.META.get('HTTP_REFERER', reverse('item_index')))
#
#
# # -------------------------
# # Inventory Alerts View
# # -------------------------
# class InventoryAlertsView(LoginRequiredMixin, PermissionRequiredMixin, TemplateView):
#     permission_required = 'inventory.view_inventoryitem'
#     template_name = 'inventory/alerts.html'
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#
#         # Stock alerts
#         low_stock = InventoryItem.objects.filter(
#             quantity__lte=F('reorder_level'),
#             quantity__gt=F('min_level'),
#             is_active=True
#         ).select_related('category', 'unit', 'department')
#
#         critical_stock = InventoryItem.objects.filter(
#             quantity__lte=F('min_level'),
#             is_active=True
#         ).select_related('category', 'unit', 'department')
#
#         expired_items = InventoryItem.objects.filter(
#             expiry_date__lt=timezone.now().date(),
#             is_active=True
#         ).select_related('category', 'unit', 'department')
#
#         # Expiring soon (next 30 days)
#         expiring_soon = InventoryItem.objects.filter(
#             expiry_date__gte=timezone.now().date(),
#             expiry_date__lte=timezone.now().date() + timezone.timedelta(days=30),
#             is_active=True
#         ).select_related('category', 'unit', 'department')
#
#         # Asset maintenance alerts
#         overdue_maintenance = Asset.objects.filter(
#             maintenances__next_due__lt=timezone.now().date(),
#             is_operational=True
#         ).distinct().select_related('department')
#
#         context.update({
#             'low_stock': low_stock,
#             'critical_stock': critical_stock,
#             'expired_items': expired_items,
#             'expiring_soon': expiring_soon,
#             'overdue_maintenance': overdue_maintenance,
#         })
#         return contextkwargs)
#         context['form'] = UnitForm()
#         return context
#
#
# class UnitUpdateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
# ):
#     model = Unit
#     permission_required = 'inventory.change_unit'
#     form_class = UnitForm
#     template_name = 'inventory/unit/index.html'
#     success_message = 'Unit Successfully Updated'
#
#     def get_success_url(self):
#         return reverse('unit_index')
#
#     def dispatch(self, request, *args, **kwargs):
#         if request.method == 'GET':
#             return redirect(reverse('unit_index'))
#         return super().dispatch(request, *args, **kwargs)
#
#
# class UnitDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
#     model = Unit
#     permission_required = 'inventory.delete_unit'
#     template_name = 'inventory/unit/delete.html'
#     context_object_name = "unit"
#     success_message = 'Unit Successfully Deleted'
#
#     def get_success_url(self):
#         return reverse('unit_index')
#
#
# # -------------------------
# # Supplier Views
# # -------------------------
# class SupplierCreateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
#     CreateView
# ):
#     model = Supplier
#     permission_required = 'inventory.add_supplier'
#     form_class = SupplierForm
#     template_name = 'inventory/supplier/index.html'
#     success_message = 'Supplier Successfully Created'
#
#     def get_success_url(self):
#         return reverse('supplier_index')
#
#     def dispatch(self, request, *args, **kwargs):
#         if request.method == 'GET':
#             return redirect(reverse('supplier_index'))
#         return super().dispatch(request, *args, **kwargs)
#
#
# class SupplierListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = Supplier
#     permission_required = 'inventory.view_supplier'
#     template_name = 'inventory/supplier/index.html'
#     context_object_name = "supplier_list"
#
#     def get_queryset(self):
#         return Supplier.objects.all().order_by('name')
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['form'] = SupplierForm()
#         return context
#
#
# class SupplierUpdateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
# ):
#     model = Supplier
#     permission_required = 'inventory.change_supplier'
#     form_class = SupplierForm
#     template_name = 'inventory/supplier/index.html'
#     success_message = 'Supplier Successfully Updated'
#
#     def get_success_url(self):
#         return reverse('supplier_index')
#
#     def dispatch(self, request, *args, **kwargs):
#         if request.method == 'GET':
#             return redirect(reverse('supplier_index'))
#         return super().dispatch(request, *args, **kwargs)
#
#
# class SupplierDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
#     model = Supplier
#     permission_required = 'inventory.view_supplier'
#     template_name = 'inventory/supplier/detail.html'
#     context_object_name = "supplier"
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         supplier = self.object
#
#         # Recent purchases from this supplier
#         recent_purchases = StockRecord.objects.filter(
#             supplier=supplier,
#             transaction_type=StockRecord.TYPE_IN
#         ).select_related('item').order_by('-created_at')[:10]
#
#         # Total spent with this supplier
#         total_spent = StockRecord.objects.filter(
#             supplier=supplier,
#             transaction_type=StockRecord.TYPE_IN,
#             cost__isnull=False
#         ).aggregate(total=Sum('cost'))['total'] or Decimal('0.00')
#
#         context.update({
#             'recent_purchases': recent_purchases,
#             'total_spent': total_spent,
#         })
#         return context
#
#
# class SupplierDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
#     model = Supplier
#     permission_required = 'inventory.delete_supplier'
#     template_name = 'inventory/supplier/delete.html'
#     context_object_name = "supplier"
#     success_message = 'Supplier Successfully Deleted'
#
#     def get_success_url(self):
#         return reverse('supplier_index')
#
#
# # -------------------------
# # Category Views
# # -------------------------
# class CategoryCreateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
#     CreateView
# ):
#     model = InventoryCategory
#     permission_required = 'inventory.add_inventorycategory'
#     form_class = InventoryCategoryForm
#     template_name = 'inventory/category/index.html'
#     success_message = 'Category Successfully Created'
#
#     def get_success_url(self):
#         return reverse('category_index')
#
#     def dispatch(self, request, *args, **kwargs):
#         if request.method == 'GET':
#             return redirect(reverse('category_index'))
#         return super().dispatch(request, *args, **kwargs)
#
#
# class CategoryListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = InventoryCategory
#     permission_required = 'inventory.view_inventorycategory'
#     template_name = 'inventory/category/index.html'
#     context_object_name = "category_list"
#
#     def get_queryset(self):
#         return InventoryCategory.objects.all().order_by('name')
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['form'] = InventoryCategoryForm()
#         return context
#
#
# class CategoryUpdateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
# ):
#     model = InventoryCategory
#     permission_required = 'inventory.change_inventorycategory'
#     form_class = InventoryCategoryForm
#     template_name = 'inventory/category/index.html'
#     success_message = 'Category Successfully Updated'
#
#     def get_success_url(self):
#         return reverse('category_index')
#
#     def dispatch(self, request, *args, **kwargs):
#         if request.method == 'GET':
#             return redirect(reverse('category_index'))
#         return super().dispatch(request, *args, **kwargs)
#
#
# class CategoryDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
#     model = InventoryCategory
#     permission_required = 'inventory.delete_inventorycategory'
#     template_name = 'inventory/category/delete.html'
#     context_object_name = "category"
#     success_message = 'Category Successfully Deleted'
#
#     def get_success_url(self):
#         return reverse('category_index')
#
#
# # -------------------------
# # Inventory Item Views
# # -------------------------
# class InventoryItemCreateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
#     CreateView
# ):
#     model = InventoryItem
#     permission_required = 'inventory.add_inventoryitem'
#     form_class = InventoryItemForm
#     template_name = 'inventory/item/create.html'
#     success_message = 'Inventory Item Successfully Created'
#
#     def get_success_url(self):
#         return reverse('item_detail', kwargs={'pk': self.object.pk})
#
#
# class InventoryItemListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = InventoryItem
#     permission_required = 'inventory.view_inventoryitem'
#     template_name = 'inventory/item/index.html'
#     context_object_name = "item_list"
#     paginate_by = 25
#
#     def get_queryset(self):
#         queryset = InventoryItem.objects.select_related(
#             'category', 'unit', 'department'
#         ).order_by('name')
#
#         # Search functionality
#         search = self.request.GET.get('search')
#         if search:
#             queryset = queryset.filter(
#                 Q(name__icontains=search) |
#                 Q(sku__icontains=search) |
#                 Q(category__name__icontains=search)
#             )
#
#         # Filter by category
#         category = self.request.GET.get('category')
#         if category:
#             queryset = queryset.filter(category_id=category)
#
#         # Filter by department
#         department = self.request.GET.get('department')
#         if department:
#             queryset = queryset.filter(department_id=department)
#
#         # Filter by stock status
#         stock_status = self.request.GET.get('stock_status')
#         if stock_status == 'low':
#             queryset = queryset.filter(quantity__lte=F('reorder_level'))
#         elif stock_status == 'critical':
#             queryset = queryset.filter(quantity__lte=F('min_level'))
#         elif stock_status == 'out':
#             queryset = queryset.filter(quantity=0)
#
#         return queryset
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['categories'] = InventoryCategory.objects.filter(is_active=True)
#         context['departments'] = DepartmentModel.objects.all()
#
#         # Stock alerts
#         context['low_stock_count'] = InventoryItem.objects.filter(
#             quantity__lte=F('reorder_level'), quantity__gt=F('min_level')
#         ).count()
#         context['critical_stock_count'] = InventoryItem.objects.filter(
#             quantity__lte=F('min_level')
#         ).count()
#         context['out_of_stock_count'] = InventoryItem.objects.filter(quantity=0).count()
#
#         return context
#
#
# class InventoryItemDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
#     model = InventoryItem
#     permission_required = 'inventory.view_inventoryitem'
#     template_name = 'inventory/item/detail.html'
#     context_object_name = "item"
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         item = self.object
#
#         # Recent stock movements
#         recent_movements = item.stock_records.select_related(
#             'supplier', 'performed_by', 'department'
#         ).order_by('-created_at')[:10]
#
#         # Usage history
#         recent_usage = StockUsageItem.objects.filter(
#             item=item
#         ).select_related('usage', 'usage__performed_by').order_by('-usage__created_at')[:10]
#
#         # Damage history
#         damages = item.damages.select_related('reported_by').order_by('-date_reported')[:5]
#
#         context.update({
#             'recent_movements': recent_movements,
#             'recent_usage': recent_usage,
#             'damages': damages,
#             'quick_in_form': QuickStockInForm(initial={'item': item}),
#             'quick_out_form': QuickStockOutForm(initial={'item': item}),
#         })
#         return context
#
#
# class InventoryItemUpdateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
# ):
#     model = InventoryItem
#     permission_required = 'inventory.change_inventoryitem'
#     form_class = InventoryItemForm
#     template_name = 'inventory/item/edit.html'
#     success_message = 'Inventory Item Successfully Updated'
#
#     def get_success_url(self):
#         return reverse('item_detail', kwargs={'pk': self.object.pk})
#
#
# class InventoryItemDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
#     model = InventoryItem
#     permission_required = 'inventory.delete_inventoryitem'
#     template_name = 'inventory/item/delete.html'
#     context_object_name = "item"
#     success_message = 'Inventory Item Successfully Deleted'
#
#     def get_success_url(self):
#         return reverse('item_index')
#
#
# # -------------------------
# # Stock Record Views
# # -------------------------
# class StockRecordCreateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
#     CreateView
# ):
#     model = StockRecord
#     permission_required = 'inventory.add_stockrecord'
#     form_class = StockRecordForm
#     template_name = 'inventory/stock/record_form.html'
#     success_message = 'Stock Record Successfully Created'
#
#     def get_success_url(self):
#         return reverse('stock_movements')
#
#     def form_valid(self, form):
#         try:
#             form.instance.performed_by = self.request.user
#             with transaction.atomic():
#                 return super().form_valid(form)
#         except Exception:
#             logger.exception("Error creating stock record")
#             messages.error(self.request, "An error occurred while creating stock record. Contact admin.")
#             return redirect(self.get_success_url())
#
#
# class StockRecordListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = StockRecord
#     permission_required = 'inventory.view_stockrecord'
#     template_name = 'inventory/stock/movements.html'
#     context_object_name = "stock_records"
#     paginate_by = 50
#
#     def get_queryset(self):
#         return StockRecord.objects.select_related(
#             'item', 'supplier', 'performed_by', 'department'
#         ).order_by('-created_at')
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['form'] = StockRecordForm()
#         context['quick_in_form'] = QuickStockInForm()
#         context['quick_out_form'] = QuickStockOutForm()
#         return context
#
#
# # -------------------------
# # Quick Stock Operations
# # -------------------------
# @login_required
# @permission_required('inventory.add_stockrecord', raise_exception=True)
# def quick_stock_in(request):
#     if request.method == 'POST':
#         form = QuickStockInForm(request.POST)
#         if form.is_valid():
#             try:
#                 with transaction.atomic():
#                     stock_record = StockRecord.objects.create(
#                         item=form.cleaned_data['item'],
#                         transaction_type=StockRecord.TYPE_IN,
#                         quantity=form.cleaned_data['quantity'],
#                         supplier=form.cleaned_data['supplier'],
#                         reference=form.cleaned_data.get('reference', ''),
#                         cost=form.cleaned_data.get('cost'),
#                         performed_by=request.user
#                     )
#
#                     # Update last purchase price if cost provided
#                     if form.cleaned_data.get('cost'):
#                         item = form.cleaned_data['item']
#                         item.last_purchase_price = form.cleaned_data['cost']
#                         item.save(update_fields=['last_purchase_price'])
#
#                 messages.success(request,
#                                  f"Successfully added {stock_record.quantity} {stock_record.item.unit} of {stock_record.item.name}")
#             except Exception:
#                 logger.exception("Error in quick stock in")
#                 messages.error(request, "An error occurred while adding stock. Contact admin.")
#         else:
#             for field, errors in form.errors.items():
#                 for error in errors:
#                     messages.error(request, f"{field}: {error}")
#
#     return redirect(reverse('stock_movements'))
#
#
# @login_required
# @permission_required('inventory.add_stockrecord', raise_exception=True)
# def quick_stock_out(request):
#     if request.method == 'POST':
#         form = QuickStockOutForm(request.POST)
#         if form.is_valid():
#             try:
#                 with transaction.atomic():
#                     stock_record = StockRecord.objects.create(
#                         item=form.cleaned_data['item'],
#                         transaction_type=StockRecord.TYPE_OUT,
#                         quantity=form.cleaned_data['quantity'],
#                         department=form.cleaned_data['department'],
#                         reference=form.cleaned_data.get('reference', ''),
#                         performed_by=request.user
#                     )
#
#                 messages.success(request,
#                                  f"Successfully issued {stock_record.quantity} {stock_record.item.unit} of {stock_record.item.name}")
#             except Exception:
#                 logger.exception("Error in quick stock out")
#                 messages.error(request, "An error occurred while issuing stock. Contact admin.")
#         else:
#             for field, errors in form.errors.items():
#                 for error in errors:
#                     messages.error(request, f"{field}: {error}")
#
#     return redirect(reverse('stock_movements'))
#
#
# # -------------------------
# # Stock Usage Views
# # -------------------------
# class StockUsageCreateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
#     CreateView
# ):
#     model = StockUsage
#     permission_required = 'inventory.add_stockusage'
#     form_class = StockUsageForm
#     template_name = 'inventory/usage/create.html'
#     success_message = 'Stock Usage Successfully Created'
#
#     def get_success_url(self):
#         return reverse('usage_detail', kwargs={'pk': self.object.pk})
#
#     def form_valid(self, form):
#         try:
#             form.instance.performed_by = self.request.user
#             with transaction.atomic():
#                 return super().form_valid(form)
#         except Exception:
#             logger.exception("Error creating stock usage")
#             messages.error(self.request, "An error occurred while creating usage record. Contact admin.")
#             return redirect(reverse('usage_index'))
#
#
# class StockUsageListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = StockUsage
#     permission_required = 'inventory.view_stockusage'
#     template_name = 'inventory/usage/index.html'
#     context_object_name = "usage_list"
#     paginate_by = 25
#
#     def get_queryset(self):
#         return StockUsage.objects.select_related(
#             'patient', 'performed_by', 'department'
#         ).order_by('-usage_date')
#
#
# class StockUsageDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
#     model = StockUsage
#     permission_required = 'inventory.view_stockusage'
#     template_name = 'inventory/usage/detail.html'
#     context_object_name = "usage"
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         usage = self.object
#
#         # Items used in this usage event
#         usage_items = usage.usage_items.select_related('item', 'item__unit')
#
#         context.update({
#             'usage_items': usage_items,
#             'usage_item_form': StockUsageItemForm(),
#         })
#         return context
#
#
# # -------------------------
# # Stock Usage Item Views
# # -------------------------
# class StockUsageItemCreateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
#     CreateView
# ):
#     model = StockUsageItem
#     permission_required = 'inventory.add_stockusageitem'
#     form_class = StockUsageItemForm
#     template_name = 'inventory/usage/item_form.html'
#
#     def get_success_url(self):
#         return reverse('usage_detail', kwargs={'pk': self.object.usage.pk})
#
#     def dispatch(self, request, *args, **kwargs):
#         # Get usage from URL parameter
#         self.usage = get_object_or_404(StockUsage, pk=kwargs.get('usage_pk'))
#         return super().dispatch(request, *args, **kwargs)
#
#     def form_valid(self, form):
#         try:
#             form.instance.usage = self.usage
#             with transaction.atomic():
#                 return super().form_valid(form)
#         except Exception:
#             logger.exception("Error adding usage item")
#             messages.error(self.request, "An error occurred while adding item to usage. Contact admin.")
#             return redirect(self.get_success_url())
#
#
# # -------------------------
# # Asset Views
# # -------------------------
# class AssetCreateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
#     CreateView
# ):
#     model = Asset
#     permission_required = 'inventory.add_asset'
#     form_class = AssetForm
#     template_name = 'inventory/asset/create.html'
#     success_message = 'Asset Successfully Created'
#
#     def get_success_url(self):
#         return reverse('asset_detail', kwargs={'pk': self.object.pk})
#
#
# class AssetListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = Asset
#     permission_required = 'inventory.view_asset'
#     template_name = 'inventory/asset/index.html'
#     context_object_name = "asset_list"
#     paginate_by = 25
#
#     def get_queryset(self):
#         queryset = Asset.objects.select_related(
#             'department', 'vendor'
#         ).order_by('-purchase_date', 'name')
#
#         # Search functionality
#         search = self.request.GET.get('search')
#         if search:
#             queryset = queryset.filter(
#                 Q(name__icontains=search) |
#                 Q(serial_number__icontains=search) |
#                 Q(asset_tag__icontains=search)
#             )
#
#         # Filter by asset type
#         asset_type = self.request.GET.get('asset_type')
#         if asset_type:
#             queryset = queryset.filter(asset_type=asset_type)
#
#         # Filter by condition
#         condition = self.request.GET.get('condition')
#         if condition:
#             queryset = queryset.filter(condition=condition)
#
#         # Filter by department
#         department = self.request.GET.get('department')
#         if department:
#             queryset = queryset.filter(department_id=department)
#
#         return queryset
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['asset_types'] = Asset._meta.get_field('asset_type').choices
#         context['conditions'] = Asset._meta.get_field('condition').choices
#         context['departments'] = DepartmentModel.objects.all()
#
#         # Asset statistics
#         context['total_assets'] = Asset.objects.count()
#         context['operational_assets'] = Asset.objects.filter(is_operational=True).count()
#         context['needs_maintenance'] = Asset.objects.filter(
#             maintenances__next_due__lt=timezone.now().date()
#         ).distinct().count()
#
#         return context
#
#
# class AssetDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
#     model = Asset
#     permission_required = 'inventory.view_asset'
#     template_name = 'inventory/asset/detail.html'
#     context_object_name = "asset"
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         asset = self.object
#
#         # Maintenance history
#         maintenances = asset.maintenances.select_related('performed_by').order_by('-performed_on')
#
#         # Damage history
#         damages = asset.damages.select_related('reported_by').order_by('-date_reported')
#
#         # Purchase history
#         purchases = asset.purchases.select_related('purchaser', 'supplier').order_by('-purchase_date')
#
#         context.update({
#             'maintenances': maintenances,
#             'damages': damages,
#             'purchases': purchases,
#             'maintenance_form': AssetMaintenanceForm(initial={'asset': asset}),
#             'damage_form': AssetDamageForm(initial={'asset': asset}),
#         })
#         return context
#
#
# class AssetUpdateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin, UpdateView
# ):
#     model = Asset
#     permission_required = 'inventory.change_asset'
#     form_class = AssetForm
#     template_name = 'inventory/asset/edit.html'
#     success_message = 'Asset Successfully Updated'
#
#     def get_success_url(self):
#         return reverse('asset_detail', kwargs={'pk': self.object.pk})
#
#
# class AssetDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
#     model = Asset
#     permission_required = 'inventory.delete_asset'
#     template_name = 'inventory/asset/delete.html'
#     context_object_name = "asset"
#     success_message = 'Asset Successfully Deleted'
#
#     def get_success_url(self):
#         return reverse('asset_index')
#
#
# # -------------------------
# # Asset Maintenance Views
# # -------------------------
# class AssetMaintenanceCreateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
#     CreateView
# ):
#     model = AssetMaintenance
#     permission_required = 'inventory.add_assetmaintenance'
#     form_class = AssetMaintenanceForm
#     template_name = 'inventory/asset/maintenance_form.html'
#
#     def get_success_url(self):
#         return reverse('asset_detail', kwargs={'pk': self.object.asset.pk})
#
#     def form_valid(self, form):
#         try:
#             form.instance.performed_by = self.request.user
#             with transaction.atomic():
#                 return super().form_valid(form)
#         except Exception:
#             logger.exception("Error creating asset maintenance")
#             messages.error(self.request, "An error occurred while recording maintenance. Contact admin.")
#             return redirect(self.get_success_url())
#
#
# class AssetMaintenanceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = AssetMaintenance
#     permission_required = 'inventory.view_assetmaintenance'
#     template_name = 'inventory/asset/maintenance_list.html'
#     context_object_name = "maintenance_list"
#     paginate_by = 25
#
#     def get_queryset(self):
#         return AssetMaintenance.objects.select_related(
#             'asset', 'performed_by'
#         ).order_by('-performed_on')
#
#
# # -------------------------
# # Asset Damage Views
# # -------------------------
# class AssetDamageCreateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
#     CreateView
# ):
#     model = AssetDamage
#     permission_required = 'inventory.add_assetdamage'
#     form_class = AssetDamageForm
#     template_name = 'inventory/asset/damage_form.html'
#
#     def get_success_url(self):
#         return reverse('asset_detail', kwargs={'pk': self.object.asset.pk})
#
#     def form_valid(self, form):
#         try:
#             form.instance.reported_by = self.request.user
#             with transaction.atomic():
#                 return super().form_valid(form)
#         except Exception:
#             logger.exception("Error creating asset damage")
#             messages.error(self.request, "An error occurred while reporting damage. Contact admin.")
#             return redirect(self.get_success_url())
#
#
# # -------------------------
# # Stock Damage Views
# # -------------------------
# class StockDamageCreateView(
#     LoginRequiredMixin, PermissionRequiredMixin, FlashFormErrorsMixin,
#     CreateView
# ):
#     model = StockDamage
#     permission_required = 'inventory.add_stockdamage'
#     form_class = StockDamageForm
#     template_name = 'inventory/damage/form.html'
#     success_message = 'Stock Damage Successfully Recorded'
#
#     def get_success_url(self):
#         return reverse('damage_index')
#
#     def form_valid(self, form):
#         try:
#             form.instance.reported_by = self.request.user
#             with transaction.atomic():
#                 # Create the damage record
#                 damage = form.save()
#
#                 # Automatically create a stock record for the damage
#                 StockRecord.objects.create(
#                     item=damage.item,
#                     transaction_type=StockRecord.TYPE_DAMAGE,
#                     quantity=damage.quantity,
#                     reference=f"Damage Report {damage.id}",
#                     performed_by=self.request.user,
#                     department=damage.department,
#                     cost=damage.cost
#                 )
#
#                 return redirect(self.get_success_url())
#         except Exception:
#             logger.exception("Error creating stock damage")
#             messages.error(self.request, "An error occurred while recording damage. Contact admin.")
#             return redirect(self.get_success_url())
#
#
# class StockDamageListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
#     model = StockDamage
#     permission_required = 'inventory.view_stockdamage'
#     template_name = 'inventory/damage/index.html'
#     context_object_name = "damage_list"
#     paginate_by = 25
#
#     def get_queryset(self):
#         return StockDamage.objects.select_related(
#             'item', 'reported_by', 'department'
#         ).order_by('-date_reported')
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**