# insurance/urls.py
from django.urls import path
from insurance.views import *


urlpatterns = [
    # Dashboard & summaries
    path("", InsuranceDashboardView.as_view(), name="insurance_dashboard"),
    path("summary/", PatientInsuranceSummaryView.as_view(), name="summary"),
    path("reports/", InsuranceReportView.as_view(), name="report"),
    path("reports/print/summary/", PrintPatientInsuranceSummaryView.as_view(), name="report_print_summary"),
    path("reports/print/insurance/", PrintInsuranceReportView.as_view(), name="report_print"),

    # AJAX / helper endpoints
    path("ajax/coverage-plans/", get_coverage_plans, name="ajax_coverage_plans"),
    path("ajax/patient-insurance-status/", patient_insurance_status, name="ajax_patient_insurance_status"),

    # Bulk / multi-entity actions
    path("providers/multi-action/", multi_provider_action, name="multi_provider_action"),

    # Pending verification & bulk verify
    path("patient-insurance/pending-verification/", PendingVerificationListView.as_view(), name="pending_verification"),
    path("patient-insurance/bulk-verify/", bulk_verify_insurance, name="bulk_verify_insurance"),
    path("patient-insurance/<int:pk>/deactivate/", deactivate_patient_insurance, name="deactivate_patient_insurance"),
    path("patient-insurance/<int:pk>/reactivate/", reactivate_patient_insurance, name="reactivate_patient_insurance"),

    # Insurance Providers (CRUD)
    path("providers/", InsuranceProviderListView.as_view(), name="insurance_provider_index"),
    path("providers/create/", InsuranceProviderCreateView.as_view(), name="insurance_provider_create"),
    path("providers/<int:pk>/detail/", InsuranceProviderDetailView.as_view(), name="insurance_provider_detail"),
    path("providers/<int:pk>/update/", InsuranceProviderUpdateView.as_view(), name="insurance_provider_update"),
    path("providers/<int:pk>/delete/", InsuranceProviderDeleteView.as_view(), name="insurance_provider_delete"),

    # HMOs (CRUD + detail)
    path("hmos/", HMOListView.as_view(), name="hmo_index"),
    path("hmos/create/", HMOCreateView.as_view(), name="hmo_create"),
    path("hmos/<int:pk>/", HMODetailView.as_view(), name="hmo_detail"),
    path("hmos/<int:pk>/update/", HMOUpdateView.as_view(), name="hmo_update"),
    path("hmos/<int:pk>/delete/", HMODeleteView.as_view(), name="hmo_delete"),

    # Coverage Plans (CRUD + detail)
    path("coverage-plans/", HMOCoveragePlanListView.as_view(), name="coverage_plan_index"),
    path("coverage-plans/create/", HMOCoveragePlanCreateView.as_view(), name="coverage_plan_create"),
    path("coverage-plans/<int:pk>/", HMOCoveragePlanDetailView.as_view(), name="coverage_plan_detail"),
    path("coverage-plans/<int:pk>/update/", HMOCoveragePlanUpdateView.as_view(), name="coverage_plan_update"),
    path("coverage-plans/<int:pk>/delete/", HMOCoveragePlanDeleteView.as_view(), name="coverage_plan_delete"),

    path("coverage-plans/<int:pk>/add-drug/", add_drug_to_plan, name="coverage_plan_add_drug"),
    path("coverage-plans/<int:pk>/remove-drug/<int:drug_id>/", remove_drug_from_plan, name="coverage_plan_remove_drug"),
    path("coverage-plans/<int:pk>/add-lab/", add_lab_to_plan, name="coverage_plan_add_lab"),
    path("coverage-plans/<int:pk>/remove-lab/<int:lab_id>/", remove_lab_from_plan, name="coverage_plan_remove_lab"),
    path("coverage-plans/<int:pk>/add-radiology/", add_radiology_to_plan, name="coverage_plan_add_radiology"),
    path("coverage-plans/<int:pk>/remove-radiology/<int:scan_id>/", remove_radiology_from_plan, name="coverage_plan_remove_radiology"),

    path('hmo-plans/<int:hmo_id>/', get_hmo_coverage_plans_api, name='get_hmo_coverage_plans'),
    path('plan-details/<int:plan_id>/', get_coverage_plan_details_api, name='get_coverage_plan_details'),


    # Search helpers for selecting items
    path("search/drugs/", search_drugs, name="search_drugs"),
    path("search/lab-tests/", search_lab_tests, name="search_lab_tests"),
    path("search/scans/", search_scans, name="search_scans"),

    # Patient Insurance (CRUD + verify)
    path("patient-insurance/", PatientInsuranceListView.as_view(), name="patient_insurance_list"),
    path("patient-insurance/create/", PatientInsuranceCreateView.as_view(), name="patient_insurance_create"),
    path("patient-insurance/<int:pk>/", PatientInsuranceDetailView.as_view(), name="patient_insurance_detail"),
    path("patient-insurance/<int:pk>/update/", PatientInsuranceUpdateView.as_view(), name="patient_insurance_update"),
    path("patient-insurance/<int:pk>/verify/", verify_patient_insurance, name="verify_patient_insurance"),
    path('patient-insurance/<int:pk>/verify/', patient_insurance_verify, name='patient_insurance_verify'),
    path('patient-insurance/<int:pk>/deactivate/', patient_insurance_deactivate, name='patient_insurance_deactivate'),
    path('patient-insurance/<int:pk>/activate/', patient_insurance_activate, name='patient_insurance_activate'),

    # Patient's claims overview
    path("patient/<int:patient_id>/claims/", PatientClaimsView.as_view(), name="patient_claims"),

    # Claims (CRUD + detail)
    path("claims/", InsuranceClaimListView.as_view(), name="claim_list"),
    path("claims/create/", InsuranceClaimCreateView.as_view(), name="claim_create"),
    path("claims/<int:pk>/", InsuranceClaimDetailView.as_view(), name="claim_detail"),
    path("claims/<int:pk>/update/", InsuranceClaimUpdateView.as_view(), name="claim_update"),
    path("claims/<int:pk>/delete/", InsuranceClaimDeleteView.as_view(), name="claim_delete"),

    # Claim actions
    path("claims/<int:pk>/approve/", approve_claim, name="approve_claim"),
    path("claims/<int:pk>/reject/", reject_claim, name="reject_claim"),
    path("claims/<int:pk>/process/", process_claim, name="process_claim"),
    path("claims/bulk-action/", bulk_claim_action, name="bulk_claim_action"),

    # Utilities
    path("calculate-coverage/", calculate_coverage, name="calculate_coverage"),
    path("api/statistics/", insurance_statistics_api, name="insurance_statistics_api"),
]
