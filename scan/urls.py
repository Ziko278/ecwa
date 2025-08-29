from django.urls import path
from scan.views import *

urlpatterns = [

    # Categories
    path('category/create', ScanCategoryCreateView.as_view(), name='scan_category_create'),
    path('category/index', ScanCategoryListView.as_view(), name='scan_category_index'),
    path('category/<int:pk>/edit', ScanCategoryUpdateView.as_view(), name='scan_category_edit'),
    path('category/<int:pk>/delete', ScanCategoryDeleteView.as_view(), name='scan_category_delete'),
    path('category/multi-action', multi_category_action, name='multi_category_action'),

    # Templates
    path('template/create', ScanTemplateCreateView.as_view(), name='scan_template_create'),
    path('template/index', ScanTemplateListView.as_view(), name='scan_template_index'),
    path('template/<int:pk>/detail', ScanTemplateDetailView.as_view(), name='scan_template_detail'),
    path('template/<int:pk>/edit', ScanTemplateUpdateView.as_view(), name='scan_template_edit'),
    path('template/<int:pk>/delete', ScanTemplateDeleteView.as_view(), name='scan_template_delete'),

    # Orders
    path('order/create', ScanOrderCreateView.as_view(), name='scan_order_create'),
    path('order/index', ScanOrderListView.as_view(), name='scan_order_index'),
    path('order/<int:pk>/detail', ScanOrderDetailView.as_view(), name='scan_order_detail'),
    path('order/<int:pk>/edit', ScanOrderUpdateView.as_view(), name='scan_order_edit'),
    path('order/multi-action', multi_order_action, name='multi_order_action'),

    # Results
    path('result/create', ScanResultCreateView.as_view(), name='scan_result_create'),
    path('result/index', ScanResultListView.as_view(), name='scan_result_index'),
    path('result/<int:pk>/detail', ScanResultDetailView.as_view(), name='scan_result_detail'),
    path('result/<int:pk>/edit', ScanResultUpdateView.as_view(), name='scan_result_edit'),
    path('result/<int:pk>/verify', verify_result, name='scan_result_verify'),

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
