from django.urls import path
from inpatient.views import *

urlpatterns = [
    # Dashboard
    path('', inpatient_dashboard, name='inpatient_dashboard'),

    # Settings
    path('settings/', InpatientSettingsDetailView.as_view(), name='inpatient_settings_detail'),
    path('settings/edit/', InpatientSettingsUpdateView.as_view(), name='inpatient_settings_edit'),

    # Ward Management
    path('wards/', WardListView.as_view(), name='ward_index'),
    path('wards/create/', WardCreateView.as_view(), name='ward_create'),
    path('wards/<int:pk>/', WardDetailView.as_view(), name='ward_detail'),
    path('wards/<int:pk>/edit/', WardUpdateView.as_view(), name='ward_edit'),
    path('wards/<int:pk>/delete/', WardDeleteView.as_view(), name='ward_delete'),

    # Bed Management
    path('beds/create/', BedCreateView.as_view(), name='bed_create'),
    path('beds/<int:pk>/edit/', BedUpdateView.as_view(), name='bed_edit'),
    path('beds/<int:pk>/delete/', BedDeleteView.as_view(), name='bed_delete'),


    # Surgery Types
    path('surgery-types/', SurgeryTypeListView.as_view(), name='surgery_type_index'),
    path('surgery-types/create/', SurgeryTypeCreateView.as_view(), name='surgery_type_create'),
    path('surgery-types/<int:pk>/', SurgeryTypeDetailView.as_view(), name='surgery_type_detail'),
    path('surgery-types/<int:pk>/edit/', SurgeryTypeUpdateView.as_view(), name='surgery_type_edit'),

    # Surgery Type Package Management (AJAX)
    path('surgery-types/<int:pk>/add-drug/', add_drug_to_surgery, name='add_drug_to_surgery'),
    path('surgery-types/<int:pk>/remove-drug/<int:drug_id>/', remove_drug_from_surgery,
         name='remove_drug_from_surgery'),
    path('surgery-types/<int:pk>/add-lab/', add_lab_to_surgery, name='add_lab_to_surgery'),
    path('surgery-types/<int:pk>/remove-lab/<int:lab_id>/', remove_lab_from_surgery,
         name='remove_lab_from_surgery'),
    path('surgery-types/<int:pk>/add-scan/', add_scan_to_surgery, name='add_scan_to_surgery'),
    path('surgery-types/<int:pk>/remove-scan/<int:scan_id>/', remove_scan_from_surgery,
         name='remove_scan_from_surgery'),

    # Admissions
    path('admissions/', AdmissionListView.as_view(), name='admission_index'),
    path('admissions/search-patient/', admission_search_patient, name='admission_search_patient'),
    path('admissions/create/<int:patient_id>/', admission_create_for_patient,
         name='admission_create_for_patient'),
    path('admissions/<int:pk>/', AdmissionDetailView.as_view(), name='admission_detail'),
    path('admissions/<int:pk>/edit/', AdmissionUpdateView.as_view(), name='admission_edit'),

    # Admission Services Management (AJAX)
    path('admissions/<int:pk>/add-drug/', add_drug_to_admission, name='add_drug_to_admission'),
    path('admissions/<int:pk>/add-lab/', add_lab_to_admission, name='add_lab_to_admission'),
    path('admissions/<int:pk>/add-scan/', add_scan_to_admission, name='add_scan_to_admission'),

    # Surgeries
    path('surgeries/', SurgeryListView.as_view(), name='surgery_index'),
    path('surgeries/search-patient/', surgery_search_patient, name='surgery_search_patient'),
    path('surgeries/create/<int:patient_id>/', surgery_create_for_patient, name='surgery_create_for_patient'),
    path('surgeries/<int:pk>/', SurgeryDetailView.as_view(), name='surgery_detail'),
    path('surgeries/<int:pk>/edit/', SurgeryUpdateView.as_view(), name='surgery_edit'),

    # Search endpoints for AJAX
    path('search/drugs/', search_drugs_for_surgery, name='search_drugs_for_surgery'),
    path('search/lab-tests/', search_lab_tests_for_surgery, name='search_lab_tests_for_surgery'),
    path('search/scans/', search_scans_for_surgery, name='search_scans_for_surgery'),
    path('search/surgery-types/', search_surgery_types_ajax, name='search_surgery_types_ajax'),
    path('get-surgery-fees/<int:pk>/', get_surgery_type_details_ajax, name='get_surgery_type_details_ajax'),

    path('surgeries/<int:pk>/add-service/', add_service_order_to_surgery, name='add_service_order_to_surgery'),
    path('surgeries/<int:pk>/remove-service/<int:order_id>/', remove_service_order_from_surgery, name='remove_service_order_from_surgery'),

    path('ajax/surgery/prescribe-multiple/', surgery_prescribe_multiple, name='surgery_prescribe_multiple'),
    path('ajax/surgery/order-lab-tests/', surgery_order_multiple_labs, name='surgery_order_multiple_labs'),
    path('ajax/surgery/order-imaging/', surgery_order_multiple_imaging, name='surgery_order_multiple_imaging'),

]
