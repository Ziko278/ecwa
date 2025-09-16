from django.urls import path
from service.views import *

urlpatterns = [
    # Dashboard
    path('', ServiceDashboardView.as_view(), name='service_dashboard'),

    # Service Categories
    path('categories/', ServiceCategoryListView.as_view(), name='service_category_list'),
    path('categories/create/', ServiceCategoryCreateView.as_view(), name='service_category_create'),
    path('categories/<int:pk>/edit/', ServiceCategoryUpdateView.as_view(), name='service_category_update'),
    path('categories/<int:pk>/delete/', ServiceCategoryDeleteView.as_view(), name='service_category_delete'),

    # Services
    path('services/', ServiceListView.as_view(), name='service_list'),
    path('services/create/', ServiceCreateView.as_view(), name='service_create'),
    path('services/<int:pk>/', ServiceDetailView.as_view(), name='service_detail'),

    path('services/<int:pk>/edit/', ServiceUpdateView.as_view(), name='service_edit'),
    path('services/<int:pk>/delete/', ServiceDeleteView.as_view(), name='service_delete'),

    # Service Items (Inventory)
    path('items/', ServiceItemListView.as_view(), name='service_item_list'),
    path('items/create/', ServiceItemCreateView.as_view(), name='service_item_create'),
    path('items/<int:pk>/', ServiceItemDetailView.as_view(), name='service_item_detail'),
    path('items/<int:pk>/edit/', ServiceItemUpdateView.as_view(), name='service_item_edit'),
    path('items/<int:pk>/delete/', ServiceItemDeleteView.as_view(), name='service_item_delete'),

    path('item-batch/', ServiceItemBatchListView.as_view(), name='service_item_batch_list'),
    path('item-batch/create/', ServiceItemBatchCreateView.as_view(), name='service_item_batch_create'),
    path('item-batch/<int:pk>/edit/', ServiceItemBatchUpdateView.as_view(), name='service_item_batch_update'),
    path('item-batch/<int:pk>/delete/', ServiceItemBatchDeleteView.as_view(), name='service_item_batch_delete'),

    # Stock Management
    path('item-batch/<int:batch_pk>/add-stock/', AddStockToBatchView.as_view(), name='service_item_stock_add'),
    path('item-batch/<int:pk>/detail/', ServiceItemBatchDetailView.as_view(), name='service_item_batch_detail'),

    path('items/<int:item_pk>/manage-stock/', manage_stock, name='manage_stock'),
    path('stock/movements/', StockMovementListView.as_view(), name='stock_movements'),

    # Patient Service Management (Main Feature)
    path('patient/<int:patient_id>/services/', PatientServiceDashboardView.as_view(),
         name='patient_service_dashboard'),
    path('patient/<int:patient_id>/services/create/', create_patient_transaction,
         name='create_patient_transaction'),
    path('patient/<int:patient_id>/services/<int:transaction_id>/pay/', process_patient_payment,
         name='process_patient_payment'),
    path('patient/<int:patient_id>/services/<int:transaction_id>/disburse/', disburse_patient_items,
         name='disburse_patient_items'),

    path('orders/items/', ItemOrderListView.as_view(), name='item_order_list'),
    path('orders/services/', ServiceOrderListView.as_view(), name='service_order_list'),
    path('results/<int:pk>/', ServiceResultDetailView.as_view(), name='service_result_detail'),
    path('results/<int:pk>/edit/', ServiceResultUpdateView.as_view(), name='service_result_edit'),

    # Service Results
    path('results/create/', ServiceResultCreateView.as_view(), name='service_result_create'),
    path('results/<int:pk>/edit/', ServiceResultUpdateView.as_view(), name='service_result_edit'),

    # AJAX URLs
    path('ajax/load-services-items/', load_services_or_items_ajax, name='load_services_items_ajax'),
    path('ajax/search-items/', search_items_ajax, name='search_items_ajax'),
    path('ajax/service/<int:service_id>/template/', get_service_template_ajax, name='get_service_template_ajax'),
    path('ajax/patient/<int:patient_id>/summary/', patient_transaction_summary_ajax,
         name='patient_transaction_summary_ajax'),
    path('patient-orders/', PatientOrderPageView.as_view(), name='patient_order_page'),

    # AJAX URLs for the Order Page
    path('ajax/verify-patient-orders/', verify_patient_and_get_orders_ajax, name='ajax_verify_patient_orders'),
    path('ajax/add-transaction/', add_new_transaction_ajax, name='ajax_add_new_transaction'),
    path('ajax/process-payments/', process_bulk_payments_ajax, name='ajax_process_bulk_payments'),
    path('ajax/process-bulk-dispense/', process_bulk_dispense_ajax, name='ajax_process_bulk_dispense'),
    path('ajax/search-all/', ajax_search_services_and_items, name='ajax_search_all'),


]