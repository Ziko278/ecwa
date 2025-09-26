from django.urls import path
from laboratory.views import *

urlpatterns = [

    # Categories
    path('category/create', LabTestCategoryCreateView.as_view(), name='lab_category_create'),
    path('category/index', LabTestCategoryListView.as_view(), name='lab_category_index'),
    path('category/<int:pk>/edit', LabTestCategoryUpdateView.as_view(), name='lab_category_edit'),
    path('category/<int:pk>/delete', LabTestCategoryDeleteView.as_view(), name='lab_category_delete'),
    path('category/multi-action', multi_category_action, name='multi_category_action'),

    # Templates
    path('template/create', LabTestTemplateCreateView.as_view(), name='lab_template_create'),
    path('template/index', LabTestTemplateListView.as_view(), name='lab_template_index'),
    path('template/<int:pk>/detail', LabTestTemplateDetailView.as_view(), name='lab_template_detail'),
    path('template/<int:pk>/edit', LabTestTemplateUpdateView.as_view(), name='lab_template_edit'),
    path('template/<int:pk>/toggle-status', LabTestTemplateToggleStatusView.as_view(), name='lab_template_toggle'),
    path('template/<int:pk>/delete', LabTestTemplateDeleteView.as_view(), name='lab_template_delete'),

    # Orders
    # Lab Entry Point
    path('order-entry', LabEntryView.as_view(), name='lab_entry'),
    path('verify-patient/', verify_lab_patient_ajax, name='verify_lab_patient_ajax'),

    # Patient Lab Tests Management
    path('patient/<int:patient_id>/tests/', PatientLabTestsView.as_view(), name='patient_lab_tests'),

    # Lab Test Orders
    path('order/create/<int:patient_id>/', LabTestOrderCreateView.as_view(), name='lab_order_create'),
    path('orders/', LabTestOrderListView.as_view(), name='lab_order_list'),
    path('order/<int:pk>/', LabTestOrderDetailView.as_view(), name='lab_order_detail'),
    path('order/<int:pk>/edit/', LabTestOrderUpdateView.as_view(), name='lab_order_update'),

    # Payment Processing
    path('process-payments/', process_lab_payments, name='process_lab_payments'),

    # Sample Collection
    path('collect-sample/<int:order_id>/', collect_sample, name='collect_sample'),

    # Results
    path('dashboard/', laboratory_dashboard, name='laboratory_dashboard'),
    path('dashboard/print/', laboratory_dashboard_print, name='laboratory_dashboard_print'),
    path('dashboard/analytics/', laboratory_analytics_api, name='laboratory_analytics_api'),

    path('results/', LabTestResultListView.as_view(), name='lab_result_index'),
    path('results/create/', LabTestResultCreateView.as_view(), name='lab_result_create'),
    path('results/create/<int:order_id>/', LabTestResultCreateView.as_view(), name='lab_result_create_for_order'),
    path('results/<int:pk>/', LabTestResultDetailView.as_view(), name='lab_result_detail'),
    path('results/<int:pk>/edit/', LabTestResultUpdateView.as_view(), name='lab_result_edit'),

    # AJAX endpoints
    path('results/<int:pk>/verify/', verify_result, name='verify_result'),
    path('results/<int:pk>/unverify/', unverify_result, name='unverify_result'),
    path('orders/<int:order_id>/process-for-results/', process_to_result_entry, name='process_to_result_entry'),

    # Equipment
    path('equipment/create', LabEquipmentCreateView.as_view(), name='lab_equipment_create'),
    path('equipment/index', LabEquipmentListView.as_view(), name='lab_equipment_index'),
    path('equipment/<int:pk>/edit', LabEquipmentUpdateView.as_view(), name='lab_equipment_edit'),
    path('equipment/<int:pk>/delete', LabEquipmentDeleteView.as_view(), name='lab_equipment_delete'),

    # Reagents
    path('reagent/create', LabReagentCreateView.as_view(), name='lab_reagent_create'),
    path('reagent/index', LabReagentListView.as_view(), name='lab_reagent_index'),
    path('reagent/<int:pk>/edit', LabReagentUpdateView.as_view(), name='lab_reagent_edit'),
    path('reagent/<int:pk>/delete', LabReagentDeleteView.as_view(), name='lab_reagent_delete'),

    # Template Builder
    path('template-builder/create', LabTestTemplateBuilderCreateView.as_view(), name='lab_template_builder_create'),
    path('template-builder/index', LabTestTemplateBuilderListView.as_view(), name='lab_template_builder_index'),
    path('template-builder/<int:pk>/detail', LabTestTemplateBuilderDetailView.as_view(), name='lab_template_builder_detail'),
    path('template-builder/<int:pk>/build', build_template, name='lab_template_builder_build'),

    # Settings
    path('setting/create', LabSettingCreateView.as_view(), name='lab_setting_create'),
    path('setting/<int:pk>/detail', LabSettingDetailView.as_view(), name='lab_setting_detail'),
    path('setting/<int:pk>/edit', LabSettingUpdateView.as_view(), name='lab_setting_edit'),

    # Dashboard & Reports
    path('dashboard', LabDashboardView.as_view(), name='lab_dashboard'),
    path('reports', LabReportView.as_view(), name='lab_report_index'),

    # Print
    path('order/<int:pk>/print', print_order, name='lab_print_order'),
    path('result/<int:pk>/print', print_result, name='lab_print_result'),

    # Order action helpers
    path('order/<int:pk>/process-payment', process_payment, name='lab_process_payment'),
    path('order/<int:pk>/collect-sample', collect_sample, name='lab_collect_sample'),
    path('order/<int:pk>/start-processing', start_processing, name='lab_start_processing'),
    path('order/<int:pk>/complete', complete_test, name='lab_complete_test'),

    # AJAX / API endpoints
    path('ajax/template-details', get_template_details, name='get_template_details'),
    path('ajax/patient-orders', get_patient_orders, name='get_patient_orders'),
    path('ajax/dashboard-data', lab_dashboard_data, name='lab_dashboard_data'),
]
