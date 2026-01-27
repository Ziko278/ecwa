from django.urls import path
from .views import *

urlpatterns = [
    # 1: Drug Category URLs
    path('category/create', DrugCategoryCreateView.as_view(), name='drug_category_create'),
    path('category/index', DrugCategoryListView.as_view(), name='drug_category_index'),
    path('category/<int:pk>/edit', DrugCategoryUpdateView.as_view(), name='drug_category_edit'),
    path('category/<int:pk>/delete', DrugCategoryDeleteView.as_view(), name='drug_category_delete'),

    # 2: Manufacturer URLs
    path('manufacturer/create', ManufacturerCreateView.as_view(), name='manufacturer_create'),
    path('manufacturer/index', ManufacturerListView.as_view(), name='manufacturer_index'),
    path('manufacturer/<int:pk>/edit', ManufacturerUpdateView.as_view(), name='manufacturer_edit'),
    path('manufacturer/<int:pk>/delete', ManufacturerDeleteView.as_view(), name='manufacturer_delete'),

    # 3: Generic Drug URLs
    path('generic/create', GenericDrugCreateView.as_view(), name='generic_drug_create'),
    path('generic/index', GenericDrugListView.as_view(), name='generic_drug_index'),
    path('generic/<int:pk>/detail', GenericDrugDetailView.as_view(), name='generic_drug_detail'),
    path('generic/<int:pk>/edit', GenericDrugUpdateView.as_view(), name='generic_drug_edit'),
    path('generic/<int:pk>/delete', GenericDrugDeleteView.as_view(), name='generic_drug_delete'),

    # 4: Drug Formulation URLs
    path('formulation/create', DrugFormulationCreateView.as_view(), name='drug_formulation_create'),
    path('formulation/index', DrugFormulationListView.as_view(), name='drug_formulation_index'),
    path('formulation/<int:pk>/detail', DrugFormulationDetailView.as_view(), name='drug_formulation_detail'),
    path('formulation/<int:pk>/edit', DrugFormulationUpdateView.as_view(), name='drug_formulation_edit'),
    path('formulation/<int:pk>/delete', DrugFormulationDeleteView.as_view(), name='drug_formulation_delete'),

    # 5: Drug Product URLs (DrugModel)
    path('drug/create', DrugCreateView.as_view(), name='drug_create'),
    path('drug/index', DrugListView.as_view(), name='drug_index'),
    path('drug/<int:pk>/detail', DrugDetailView.as_view(), name='drug_detail'),
    path('drug/<int:pk>/edit', DrugUpdateView.as_view(), name='drug_edit'),
    path('drug/<int:pk>/delete', DrugDeleteView.as_view(), name='drug_delete'),

    # 6: Drug Batch URLs
    path('batch/create', DrugBatchCreateView.as_view(), name='drug_batch_create'),
    path('batch/index', DrugBatchListView.as_view(), name='drug_batch_index'),
    path('batch/<int:pk>/edit', DrugBatchUpdateView.as_view(), name='drug_batch_update'),
    path('batch/<int:pk>/delete', DrugBatchDeleteView.as_view(), name='drug_batch_delete'),

    # 7: Drug Stock URLs
    path('stock/add/', DrugStockCreateView.as_view(), name='drug_stock_create'), #
    path('stock/batch/<int:pk>/', DrugBatchDetailView.as_view(), name='drug_batch_detail'), # NEW: Details of a batch and its stocks
    path('stock/<int:pk>/edit/', DrugStockUpdateView.as_view(), name='drug_stock_update'), # Edit single stock item
    path('stock/<int:pk>/delete/', DrugStockDeleteView.as_view(), name='drug_stock_delete'), # Delete single stock item
    path('stock/<int:pk>/stock-out/', DrugStockOutView.as_view(), name='drug_stock_out'), # NEW: Stock out for single item


    # 9: Drug Transfer URLs
    path('transfers/', DrugTransferListView.as_view(), name='drug_transfer_index'),
    path('transfers/create/', DrugTransferCreateView.as_view(), name='drug_transfer_create'),


    # 10: Drug Template URLs
    path('template/create', DrugTemplateCreateView.as_view(), name='drug_template_create'),
    path('template/index', DrugTemplateListView.as_view(), name='drug_template_index'),
    path('template/<int:pk>/detail', DrugTemplateDetailView.as_view(), name='drug_template_detail'),
    path('template/<int:pk>/edit', DrugTemplateUpdateView.as_view(), name='drug_template_edit'),
    path('template/<int:pk>/delete', DrugTemplateDeleteView.as_view(), name='drug_template_delete'),
    path('template/<int:pk>/process/', process_drug_template_view, name='process_drug_template'),

    # 11: Pharmacy Settings URLs
    # Detail and Update are handled by the same template and share a single path due to get_object logic
    path('settings/', PharmacySettingDetailView.as_view(), name='pharmacy_setting_index'),
    # If you need an explicit 'edit' path for the update view, you can add it, but it might redirect internally
    # path('settings/edit/', PharmacySettingUpdateView.as_view(), name='pharmacy_setting_edit'),


    # 12: Drug Import Log URLs
    path('import/create', DrugImportLogCreateView.as_view(), name='drug_import_log_create'),
    path('import/index', DrugImportLogListView.as_view(), name='drug_import_log_index'),
    path('import/<int:pk>/detail', DrugImportLogDetailView.as_view(), name='drug_import_log_detail'),

    # 13: Dashboard and Reports URLs
    path('dashboard/', pharmacy_dashboard, name='pharmacy_dashboard'),
    path('dashboard/print/', pharmacy_dashboard_print, name='pharmacy_dashboard_print'),
    path('reports/stock/', StockReportView.as_view(), name='stock_report'),

    # 14: AJAX and API URLs
    path('ajax/quick-transfer/', quick_transfer_view, name='quick_transfer'),
    path('ajax/update-stock-alert/', update_stock_alert_view, name='update_stock_alert'),
    path('ajax/bulk-status-update/', bulk_drug_status_update_view, name='bulk_drug_status_update'),

    # 15: Export Views
    path('export/drugs/', export_drug_list_view, name='export_drug_list'),
    path('export/stock-report/', export_stock_report_view, name='export_stock_report'),

    path('dispense/', drug_dispense_page, name='drug_dispense_page'),
    path('verify-patient/', verify_patient_pharmacy_ajax, name='pharmacy_verify_patient_ajax'),
    path('process-dispense/', process_dispense_ajax, name='pharmacy_process_dispense'),
    path('dispense-history/', dispense_history_ajax, name='pharmacy_dispense_history'),
    path('create-pharmacy-order/', create_pharmacy_order_ajax, name='pharmacy_create_order_ajax'),
    path("dispense/general/", general_dispense_view, name="general_dispense_index"),
    path("dispense/patient/<int:patient_id>/", patient_dispense_view, name="patient_dispense_index"),
    
    # Walk-in dispense URLs
    path('dispense/walkin/', walkin_dispense_page, name='pharmacy_walkin_dispense_page'),
    path('ajax/walkin-orders-list/', walkin_orders_list_ajax, name='pharmacy_walkin_orders_list'),
    path('ajax/walkin-order-detail/', walkin_order_detail_ajax, name='pharmacy_walkin_order_detail'),
    path('ajax/process-walkin-dispense/', process_walkin_dispense_ajax, name='pharmacy_process_walkin_dispense'),


]
