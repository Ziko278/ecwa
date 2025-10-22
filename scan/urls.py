from django.urls import path
from scan.views import *

urlpatterns = [

    # Categories
    path('category/create', ScanCategoryCreateView.as_view(), name='scan_category_create'),
    path('category/index', ScanCategoryListView.as_view(), name='scan_category_index'),
    path('category/<int:pk>/edit', ScanCategoryUpdateView.as_view(), name='scan_category_edit'),
    path('category/<int:pk>/delete', ScanCategoryDeleteView.as_view(), name='scan_category_delete'),
    path('category/multi-action', multi_category_action, name='multi_category_action'),
    
    path('', ScanDashboardView.as_view(), name='scan_dashboard'),
    path('dashboard/data/', scan_dashboard_data, name='scan_dashboard_data'),

    path('entry/', ScanEntryView.as_view(), name='scan_entry'),
    path('verify-patient/', verify_scan_patient_ajax, name='verify_scan_patient_ajax'),
    path('patient/<int:patient_id>/external-scans/', PatientExternalScanListView.as_view(),name='patient_external_scan_list'),

    path('external-scan-order/<int:order_id>/upload-result/', UploadExternalScanResultView.as_view(),
        name='upload_external_scan_result'),

    # -------------------------
    # Templates
    # -------------------------
    path('templates/', ScanTemplateListView.as_view(), name='scan_template_index'),
    path('templates/create/', ScanTemplateCreateView.as_view(), name='scan_template_create'),
    path('templates/<int:pk>/', ScanTemplateDetailView.as_view(), name='scan_template_detail'),
    path('templates/<int:pk>/edit/', ScanTemplateUpdateView.as_view(), name='scan_template_edit'),
    path('templates/<int:pk>/delete/', ScanTemplateDeleteView.as_view(), name='scan_template_delete'),

    # AJAX - Template details
    path('api/template-details/', get_scan_template_details, name='get_scan_template_details'),

    # -------------------------
    # Patient Scans
    # -------------------------
    path('patient/<int:patient_id>/', PatientScansView.as_view(), name='patient_scan_orders'),
    path('patient/<int:patient_id>/create-order/', ScanOrderCreateView.as_view(), name='scan_order_create'),
    path('api/patient-scans/', get_patient_scans, name='get_patient_scans'),

    # -------------------------
    # Orders
    # -------------------------
    path('orders/', ScanOrderListView.as_view(), name='scan_order_index'),
    path('orders/<int:pk>/', ScanOrderDetailView.as_view(), name='scan_order_detail'),
    path('orders/<int:pk>/edit/', ScanOrderUpdateView.as_view(), name='scan_order_edit'),

    # Order Actions
    path('orders/process-payments/', process_scan_payments, name='process_scan_payments'),
    path('orders/<int:order_id>/schedule/', schedule_scan, name='schedule_scan'),
    path('orders/<int:order_id>/start/', start_scan, name='start_scan'),
    path('orders/bulk-action/', multi_scan_order_action, name='multi_scan_order_action'),

    # -------------------------
    # Results Dashboard
    # -------------------------
    path('result-dashboard/', ScanResultDashboardView.as_view(), name='scan_result_dashboard'),
    path('results/', ScanResultListView.as_view(), name='scan_result_index'),
    path('<int:patient_id>/results/', ScanResultDashboardView.as_view(), name='patient_scan_results'),
    path('results/create/<int:order_id>/', ScanResultCreateView.as_view(), name='scan_result_create_for_order'),
    path('results/<int:pk>/', ScanResultDetailView.as_view(), name='scan_result_detail'),
    path('results/<int:pk>/edit/', ScanResultUpdateView.as_view(), name='scan_result_edit'),
    path('results/<int:pk>/verify/', verify_scan_result, name='verify_scan_result'),
    path('results/<int:pk>/unverify/', unverify_scan_result, name='unverify_scan_result'),

    path('dashboard/', scan_dashboard, name='scan_dashboard'),
    path('dashboard/print/', scan_dashboard_print, name='scan_dashboard_print'),
    path('dashboard/analytics/', scan_analytics_api, name='scan_analytics_api'),
    path('reports/', ScanReportView.as_view(), name='scan_reports'),
    path('reports/export/excel/', ScanReportExportExcelView.as_view(), name='scan_report_export_excel'),
    path('reports/export/pdf/', ScanReportExportPDFView.as_view(), name='scan_report_export_pdf'),

    # -------------------------
    # Image Management
    # -------------------------
    path('results/<int:result_id>/upload-image/', ScanImageUploadView.as_view(), name='scan_image_upload'),
    path('images/<int:image_id>/delete/', delete_scan_image, name='delete_scan_image'),
    path('images/<int:image_id>/update/', update_image_details, name='update_image_details'),

    # -------------------------
    # Print Views
    # -------------------------
    path('orders/<int:pk>/print/', print_scan_order, name='print_scan_order'),
    path('results/<int:pk>/print/', print_scan_result, name='print_scan_result'),

    # -------------------------
    # Reports
    # -------------------------
    path('reports/', ScanReportView.as_view(), name='scan_reports'),

    
    # Equipment
    path('equipment/create', ScanEquipmentCreateView.as_view(), name='scan_equipment_create'),
    path('equipment/index', ScanEquipmentListView.as_view(), name='scan_equipment_index'),
    path('equipment/<int:pk>/edit', ScanEquipmentUpdateView.as_view(), name='scan_equipment_edit'),
    path('equipment/<int:pk>/delete', ScanEquipmentDeleteView.as_view(), name='scan_equipment_delete'),

    # Appointments
    path('appointment/create', ScanAppointmentCreateView.as_view(), name='scan_appointment_create'),
    path('appointment/index', ScanAppointmentListView.as_view(), name='scan_appointment_index'),
    path('appointment/<int:pk>/detail', ScanAppointmentDetailView.as_view(), name='scan_appointment_detail'),
    path('appointment/<int:pk>/edit', ScanAppointmentUpdateView.as_view(), name='scan_appointment_edit'),
    path('appointment/<int:pk>/delete', ScanAppointmentDeleteView.as_view(), name='scan_appointment_delete'),

    # Template Builder
    path('template-builder/create', ScanTemplateBuilderCreateView.as_view(), name='scan_template_builder_create'),
    path('template-builder/index', ScanTemplateBuilderListView.as_view(), name='scan_template_builder_index'),
    path('template-builder/<int:pk>/detail', ScanTemplateBuilderDetailView.as_view(), name='scan_template_builder_detail'),
    path('template-builder/<int:pk>/build', build_template, name='scan_template_builder_build'),

    # Settings
    path('setting/create', ScanSettingCreateView.as_view(), name='scan_setting_create'),
    path('setting/<int:pk>/detail', ScanSettingDetailView.as_view(), name='scan_setting_detail'),
    path('setting/<int:pk>/edit', ScanSettingUpdateView.as_view(), name='scan_setting_edit'),

    # Dashboard & Reports
    path('dashboard', ScanDashboardView.as_view(), name='scan_dashboard'),
    path('reports', ScanReportView.as_view(), name='scan_report_index'),

    # Print
    path('order/<int:pk>/print', print_order, name='scan_print_order'),
    path('result/<int:pk>/print', print_result, name='scan_print_result'),

    # Order action helpers
    path('order/<int:pk>/process-payment', process_payment, name='scan_process_payment'),
    path('order/<int:pk>/schedule', schedule_scan, name='scan_schedule'),
    path('order/<int:pk>/start', start_scan, name='scan_start'),
    path('order/<int:pk>/complete', complete_scan, name='scan_complete'),

    # AJAX / API endpoints
    path('ajax/template-details', get_template_details, name='get_template_details'),
    path('ajax/patient-orders', get_patient_orders, name='get_patient_orders'),
    path('ajax/dashboard-data', scan_dashboard_data, name='scan_dashboard_data'),
]

