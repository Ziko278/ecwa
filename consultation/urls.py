from django.urls import path
from consultation.views import *

urlpatterns = [

    # -------------------------
    # 1. SPECIALIZATION URLS
    # -------------------------
    path('specialization/create', SpecializationCreateView.as_view(), name='specialization_create'),
    path('specialization/index', SpecializationListView.as_view(), name='specialization_index'),
    path('specialization/<int:pk>/detail', SpecializationDetailView.as_view(), name='specialization_detail'),
    path('specialization/<int:pk>/edit', SpecializationUpdateView.as_view(), name='specialization_edit'),
    path('specialization/<int:pk>/delete', SpecializationDeleteView.as_view(), name='specialization_delete'),

    path('specialization-group/index', SpecializationGroupListView.as_view(), name='specialization_group_index'),
    path('specialization-group/create/', SpecializationGroupCreateView.as_view(), name='specialization_group_create'),
    path('specialization-group/<int:pk>/update/', SpecializationGroupUpdateView.as_view(), name='specialization_group_update'),
    path('specialization-group/<int:pk>/delete/', SpecializationGroupDeleteView.as_view(), name='specialization_group_delete'),

    path('diagnosis/create', DiagnosisOptionCreateView.as_view(), name='diagnosis_create'),
    path('diagnosis/index', DiagnosisOptionListView.as_view(), name='diagnosis_index'),
    path('diagnosis/<int:pk>/detail', DiagnosisOptionDetailView.as_view(), name='diagnosis_detail'),
    path('diagnosis/<int:pk>/edit', DiagnosisOptionUpdateView.as_view(), name='diagnosis_edit'),
    path('diagnosis/<int:pk>/delete', DiagnosisOptionDeleteView.as_view(), name='diagnosis_delete'),

    # -------------------------
    # 2. CONSULTATION BLOCKS URLS
    # -------------------------
    path('block/create', ConsultationBlockCreateView.as_view(), name='block_create'),
    path('block/index', ConsultationBlockListView.as_view(), name='block_index'),
    path('block/<int:pk>/edit', ConsultationBlockUpdateView.as_view(), name='block_edit'),
    path('block/<int:pk>/delete', ConsultationBlockDeleteView.as_view(), name='block_delete'),

    # -------------------------
    # 3. CONSULTATION ROOMS URLS
    # -------------------------
    path('room/create', ConsultationRoomCreateView.as_view(), name='room_create'),
    path('room/index', ConsultationRoomListView.as_view(), name='room_index'),
    path('room/<int:pk>/edit', ConsultationRoomUpdateView.as_view(), name='room_edit'),
    path('room/<int:pk>/delete', ConsultationRoomDeleteView.as_view(), name='room_delete'),

    # -------------------------
    # 4. CONSULTANTS URLS
    # -------------------------
    path('consultant/create', ConsultantCreateView.as_view(), name='consultant_create'),
    path('consultant/index', ConsultantListView.as_view(), name='consultant_list'),
    path('consultant/<int:pk>/detail', ConsultantDetailView.as_view(), name='consultant_detail'),
    path('consultant/<int:pk>/edit', ConsultantUpdateView.as_view(), name='consultant_edit'),
    path('consultant/<int:pk>/delete', ConsultantDeleteView.as_view(), name='consultant_delete'),

    path('consultant/<int:pk>/toggle-availability/', toggle_consultant_availability,
         name='consultant_toggle_availability'),
    path('consultant/<int:pk>/queue/', ConsultantQueueView.as_view(), name='consultant_queue'),

    # AJAX endpoints
    path('ajax/transfer-patient/<int:queue_id>/<int:new_consultant_id>/', transfer_patient_ajax,
         name='transfer_patient_ajax'),
    path('ajax/bulk-transfer-patients/', bulk_transfer_patients_ajax, name='bulk_transfer_patients_ajax'),

    # -------------------------
    # 5. CONSULTATION FEES URLS
    # -------------------------
    path('fee/create', ConsultationFeeCreateView.as_view(), name='consultation_fee_create'),
    path('fee/index', ConsultationFeeListView.as_view(), name='consultation_fee_index'),
    path('fee/<int:pk>/edit', ConsultationFeeUpdateView.as_view(), name='consultation_fee_edit'),
    path('fee/<int:pk>/delete', ConsultationFeeDeleteView.as_view(), name='consultation_fee_delete'),

    # -------------------------
    # 6. CONSULTATION PAYMENTS URLS
    # -------------------------
    path('payment/create', ConsultationPaymentCreateView.as_view(), name='consultation_payment_create'),
    path('payment/verify_patient_ajax', ConsultationPaymentListView.as_view(), name='consultation_payment_list'),
    path('payment/<int:pk>/detail', ConsultationPaymentDetailView.as_view(), name='consultation_payment_detail'),
    path('verify-patient', verify_patient_ajax, name='verify_patient_ajax'),
    path('get-consultation-fees', get_consultation_fees_ajax, name='get_consultation_fees_ajax'),
    path('get-specialization-consultants', get_specialization_consultants_ajax, name='get_specialization_consultants_ajax'),

    # --- Add the two new URL patterns for the AJAX views ---
    path('ajax/get-consultation-status/', get_consultation_status_ajax, name='get_consultation_status_ajax'),
    path('ajax/create-queue-from-payment/', create_queue_from_payment_ajax, name='create_queue_from_payment_ajax'),

    # This URL should already exist, just showing for context
    path('ajax/verify-patient/', verify_patient_ajax, name='verify_patient_ajax'),


    # -------------------------
    # 7. PATIENT QUEUE MANAGEMENT URLS
    # -------------------------
    path('queue/add-patient', PatientQueueCreateView.as_view(), name='patient_queue_create'),
    path('queue/index', PatientQueueListView.as_view(), name='patient_queue_index'),
    path('queue/<int:queue_pk>/cancel/', cancel_queue_entry_view, name='cancel_queue_entry'),

    # -------------------------
    # 8. VITALS MANAGEMENT URLS
    # -------------------------
    path('vitals/queue', VitalsQueueListView.as_view(), name='vitals_queue_list'),
    path('vitals/<int:queue_pk>/create', PatientVitalsCreateView.as_view(), name='patient_vitals_create'),
    path('vitals/<int:queue_pk>/complete/', complete_vitals_view, name='complete_vitals'),
    path('vitals/bulk-complete/', bulk_complete_vitals_view, name='bulk_complete_vitals'),

    # -------------------------
    # 9. DOCTOR QUEUE & CONSULTATION URLS
    # -------------------------
    path('doctor/queue', DoctorQueueListView.as_view(), name='doctor_queue_list'),
    path('consultation/<int:queue_pk>/start/', start_consultation_view, name='start_consultation'),
    path('consultation/<int:queue_pk>/pause/', pause_consultation_view, name='pause_consultation'),
    path('consultation/<int:queue_pk>/resume/', resume_consultation_view, name='resume_consultation'),

    # -------------------------
    # 10. CONSULTATION SESSIONS URLS
    # -------------------------
    path('session/<int:queue_pk>/create', ConsultationSessionCreateView.as_view(), name='consultation_session_create'),
    path('session/<int:pk>/edit', ConsultationSessionUpdateView.as_view(), name='consultation_session_update'),
    path('session/<int:pk>/complete/', complete_consultation_session_view, name='complete_consultation_session'),

    # -------------------------
    # 11. CONSULTATION RECORDS & HISTORY URLS
    # -------------------------
    path('records/index', ConsultationRecordsListView.as_view(), name='consultation_records_list'),
    path('records/<int:pk>/detail', ConsultationRecordDetailView.as_view(), name='consultation_record_detail'),
    path('records/patient/<int:patient_pk>/history', PatientConsultationHistoryView.as_view(), name='patient_consultation_history'),

    # -------------------------
    # 12. DOCTOR SCHEDULE MANAGEMENT URLS
    # -------------------------
    path('schedule/create', DoctorScheduleCreateView.as_view(), name='doctor_schedule_create'),
    path('schedule/index', DoctorScheduleListView.as_view(), name='doctor_schedule_list'),
    path('schedule/<int:pk>/edit', DoctorScheduleUpdateView.as_view(), name='doctor_schedule_edit'),

    # -------------------------
    # 13. DASHBOARD & REPORTS URLS
    # -------------------------
    path('dashboard/', ConsultationDashboardView.as_view(), name='consultation_dashboard'),
    path('reports/', ConsultationReportsView.as_view(), name='consultation_reports'),
    path('reports/export-consultations/', export_consultation_data_view, name='export_consultation_data'),
    path('reports/export-payments/', export_payment_data_view, name='export_payment_data'),

    # -------------------------
    # 14. SETTINGS URLS
    # -------------------------
    path('settings/', ConsultationSettingsView.as_view(), name='consultation_settings'),

    # -------------------------
    # 15. AJAX/API ENDPOINTS
    # -------------------------

    # -------------------------
    # 15. AJAX/API ENDPOINTS (UPDATED)
    # -------------------------
    path('ajax/consultant-schedule/', get_consultant_schedule_ajax, name='get_consultant_schedule_ajax'),
    path('ajax/patient-vitals/<int:queue_pk>/', get_patient_vitals_ajax, name='get_patient_vitals_ajax'),
    path('ajax/patient-vitals/<int:queue_pk>/create', create_vitals_view, name='create_patient_vitals_ajax'),
    path('ajax/patient-vitals/<int:queue_pk>/update', update_patient_vitals_ajax, name='update_patient_vitals_ajax'),  # NEW
    path('ajax/queue-status/', queue_status_ajax, name='queue_status_ajax'),
    path('ajax/specialization-fee/', get_specialization_fee_ajax, name='get_specialization_fee_ajax'),
    path('ajax/search-patients/', search_patients_ajax, name='search_patients_ajax'),
    path('ajax/assign-consultant/<int:queue_pk>/', assign_consultant_ajax, name='assign_consultant_ajax'),
    path('ajax/change-doctor/<int:queue_pk>/', change_patient_doctor_ajax, name='change_patient_doctor_ajax'),  # NEW
    path('ajax/queue-data/', get_patient_queue_data_ajax, name='get_patient_queue_data_ajax'),  # NEW
    path('ajax/specialization-consultants/', get_specialization_consultants_ajax, name='get_specialization_consultants_ajax'),  # ENHANCED

    path('doctor-dashboard', doctor_dashboard, name='doctor_dashboard'),

    # Consultation management
    path('consultation/<int:consultation_id>/', consultation_page, name='consultation_page'),
    path('consultations/history/', consultation_history, name='consultation_history'),

    path('patient/<int:patient_id>/history-view/', patient_history_view, name='patient_history_view'),
    path('ajax/patient/<int:patient_id>/history-page/', patient_history_ajax, name='patient_history_ajax'),

    # AJAX endpoints for queue management
    path('ajax/call-next-patient/', ajax_call_next_patient, name='ajax_call_next_patient'),
    path('ajax/start-consultation/<int:queue_id>/', ajax_start_consultation, name='ajax_start_consultation'),
    path('ajax/pause-consultation/<int:consultation_id>/', ajax_pause_consultation,
         name='ajax_pause_consultation'),
    path('ajax/resume-consultation/<int:consultation_id>/', ajax_resume_consultation,
         name='ajax_resume_consultation'),
    path('ajax/complete-consultation/<int:consultation_id>/', ajax_complete_consultation,
         name='ajax_complete_consultation'),

    # AJAX endpoints for consultation management
    path('ajax/save-consultation/<int:consultation_id>/', ajax_save_consultation, name='ajax_save_consultation'),
    path('ajax/consultation/<int:consultation_id>/details/', ajax_consultation_details,
         name='ajax_consultation_details'),

    # AJAX endpoints for prescriptions
    path('ajax/search-drugs/', ajax_search_drugs, name='ajax_search_drugs'),
    path('ajax/search-drugs-consult/', ajax_drug_search_consult, name='ajax_drug_search_consult'),
    path('ajax/prescribe-drug/', ajax_prescribe_drug, name='ajax_prescribe_drug'),

    # AJAX endpoints for lab tests
    path('ajax/lab-templates/', ajax_lab_templates, name='ajax_lab_templates'),
    path('ajax/order-lab-test/', ajax_order_lab_test, name='ajax_order_lab_test'),

    # AJAX endpoints for scans
    path('ajax/scan-templates/', ajax_scan_templates, name='ajax_scan_templates'),
    path('ajax/order-scan/', ajax_order_scan, name='ajax_order_scan'),

    path('ajax/consultation/search-lab-templates/', ajax_lab_templates_search, name='ajax_lab_templates_search'),
    path('ajax/consultation/search-imaging-templates/', ajax_imaging_templates_search,
         name='ajax_imaging_templates_search'),

    # Add new multi-order URLs
    path('ajax/consultation/order-lab-tests/', ajax_order_multiple_lab_tests, name='order_multiple_lab_tests'),
    path('ajax/consultation/order-imaging/', ajax_order_multiple_imaging, name='order_multiple_imaging'),

    # Additional views for patient history, prescriptions, etc.
    path('patient/<int:patient_id>/history/', patient_history, name='patient_history'),
    path('patient/<int:patient_id>/prescriptions/', patient_prescriptions, name='patient_prescriptions'),
    path('patient/<int:patient_id>/test-results/', patient_test_results, name='patient_test_results'),
    path('prescription/<int:prescription_id>/', prescription_detail, name='prescription_detail'),
    path('lab-test/<int:test_id>/result/', lab_test_result, name='lab_test_result'),
    path('scan/<int:scan_id>/result/', scan_result, name='scan_result'),
    path('consultation/<int:consultation_id>/print/', print_consultation, name='print_consultation'),
    path('consultation/<int:consultation_id>/view/', view_consultation_detail, name='view_consultation_detail'),

    # New consultation (for walk-ins or special cases)
    path('consultation/new/', new_consultation, name='new_consultation'),
    path('ajax/create-consultation/', ajax_create_consultation, name='ajax_create_consultation'),
    path('ajax/update-allergy/<int:patient_id>/', update_patient_allergy, name='update_patient_allergy'),
    path('ajax/prescribe-multiple/', prescribe_multiple_view, name='prescribe_multiple'),
    
    # Add these to your urls.py
    path('ajax/edit-drug/<int:prescription_id>/', edit_drug_prescription, name='edit_drug_prescription'),
    path('ajax/delete-drug/<int:prescription_id>/', delete_drug_prescription, name='delete_drug_prescription'),
    path('ajax/edit-external-drug/<int:prescription_id>/', edit_external_prescription, name='edit_external_prescription'),
    path('ajax/delete-external-drug/<int:prescription_id>/', delete_external_prescription, name='delete_external_prescription'),
    path('ajax/edit-lab-test/<int:order_id>/', edit_lab_test_order, name='edit_lab_test_order'),
    path('ajax/delete-lab-test/<int:order_id>/', delete_lab_test_order, name='delete_lab_test_order'),
    path('ajax/edit-external-lab/<int:order_id>/', edit_external_lab_test, name='edit_external_lab_test'),
    path('ajax/delete-external-lab/<int:order_id>/', delete_external_lab_test, name='delete_external_lab_test'),
    path('ajax/edit-scan/<int:order_id>/', edit_scan_order, name='edit_scan_order'),
    path('ajax/delete-scan/<int:order_id>/', delete_scan_order, name='delete_scan_order'),
    path('ajax/edit-external-scan/<int:order_id>/', edit_external_scan, name='edit_external_scan'),
    path('ajax/delete-external-scan/<int:order_id>/', delete_external_scan, name='delete_external_scan'),

    path('ajax/search-services/', ajax_search_services, name='ajax_search_services'),
    path('ajax/search-service-items/', ajax_search_service_items, name='ajax_search_service_items'),
    path('ajax/order-services-items/', order_multiple_services_or_items, name='order_multiple_services_or_items'),
    path('ajax/delete-service-order/<int:order_id>/', delete_service_order, name='delete_service_order'),
    path('service-result/<int:result_id>/view/', view_service_result, name='view_service_result'),

    path('ajax/search-diagnoses/', ajax_search_diagnoses, name='ajax_search_diagnoses'),
    path('ajax/save-diagnosis/', ajax_save_diagnosis, name='ajax_save_diagnosis'),
    path('bulk-diagnosis-update/', bulk_diagnosis_update, name='bulk_diagnosis_update'),

]