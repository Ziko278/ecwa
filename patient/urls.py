from django.urls import path
from patient.views import *

urlpatterns = [

    path('registration-fee/create', RegistrationFeeCreateView.as_view(), name='registration_fee_create'),
    path('registration-fee/index', RegistrationFeeListView.as_view(), name='registration_fee_index'),
    path('registration-fee/<int:pk>/edit', RegistrationFeeUpdateView.as_view(), name='registration_fee_edit'),
    path('registration-fee/<int:pk>/delete', RegistrationFeeDeleteView.as_view(), name='registration_fee_delete'),

    path('setting/create', PatientSettingCreateView.as_view(), name='patient_setting_create'),
    path('setting/<int:pk>/detail', PatientSettingDetailView.as_view(), name='patient_setting_detail'),
    path('setting/<int:pk>/edit', PatientSettingUpdateView.as_view(), name='patient_setting_edit'),


    path('pending-registration/', PatientPendingListView.as_view(), name='pending_patient_index'),
    path('register/<int:pay_id>/', PatientCreateView.as_view(), name='patient_create'),
    path('index', PatientListView.as_view(), name='patient_index'),
    path('payments/history/', PatientPaymentHistoryView.as_view(), name='patient_payment_history'),
    path('<int:pk>/detail', PatientDetailView.as_view(), name='patient_detail'),
    path('<int:pk>/edit', PatientUpdateView.as_view(), name='patient_edit'),
    path('<int:pk>/delete', PatientDeleteView.as_view(), name='patient_delete'),
    path('get-detail-with-card-number', get_patient_with_card, name='get_patient_with_card'),

    path('dashboard/', patient_dashboard, name='patient_dashboard'),
    path('dashboard/print/', patient_dashboard_print, name='patient_dashboard_print'),

    path('<int:patient_id>/upload-document/', upload_consultation_document, name='upload_consultation_document'),
    path('document/<int:document_id>/delete/', delete_consultation_document, name='delete_consultation_document'),

    path('reports/', ReportsHubView.as_view(), name='reports_hub'),

    # Bio Data Report
    path('reports/bio-data/', BiodataReportView.as_view(), name='biodata_report'),
    path('reports/bio-data/export/', BiodataReportExportView.as_view(), name='biodata_report_export'),

    # Registration Report
    path('reports/registration/', RegistrationReportView.as_view(), name='registration_report'),
    path('reports/registration/template/create/', RegistrationTemplateCreateView.as_view(),
         name='registration_template_create'),
    path('reports/registration/template/<int:pk>/edit/', RegistrationTemplateUpdateView.as_view(),
         name='registration_template_edit'),
    path('reports/registration/template/<int:pk>/delete/', RegistrationTemplateDeleteView.as_view(),
         name='registration_template_delete'),
    path('reports/registration/export-pdf/', RegistrationReportExportPDFView.as_view(), name='registration_report_pdf'),

    # Consultation Templates Report
    path('reports/consultation-templates/', ConsultationTemplateListView.as_view(), name='consultation_templates'),
    path('reports/consultation-templates/create/', ConsultationTemplateCreateView.as_view(),
         name='consultation_template_create'),
    path('reports/consultation-templates/<int:pk>/edit/', ConsultationTemplateUpdateView.as_view(),
         name='consultation_template_edit'),
    path('reports/consultation-templates/<int:pk>/delete/', ConsultationTemplateDeleteView.as_view(),
         name='consultation_template_delete'),
    path('reports/consultation-templates/export-pdf/', ConsultationTemplateExportPDFView.as_view(),
         name='consultation_template_pdf'),

]

