from django.urls import path
from .views import (
    finance_payment_select,
    # Registration Payments
    RegistrationPaymentCreateView,
    RegistrationPaymentListView,
    RegistrationPaymentDetailView,
    print_receipt,

    # Wallet & Patient Payments
    patient_wallet_funding,
    verify_patient_ajax,
    process_wallet_funding,
    patient_wallet_dashboard,
    finance_payment_select,
    finance_consultation_patient_payment,
    finance_pharmacy_patient_payment,
    finance_laboratory_patient_payment,
    finance_scan_patient_payment,
    PatientTransactionListView,
    PatientTransactionDetailView,

    # Finance Settings
    FinanceSettingCreateView,
    FinanceSettingDetailView,
    FinanceSettingUpdateView,

    # Expense Categories
    ExpenseCategoryListView,
    ExpenseCategoryCreateView,
    ExpenseCategoryUpdateView,
    ExpenseCategoryDeleteView,

    # Expenses
    ExpenseListView,
    ExpenseCreateView,
    ExpenseDetailView,
    ExpenseUpdateView,

    # Income Categories
    IncomeCategoryListView,
    IncomeCategoryCreateView,
    IncomeCategoryUpdateView,
    IncomeCategoryDeleteView,

    # Income
    IncomeListView,
    IncomeCreateView,
    IncomeDetailView,
    IncomeUpdateView,

    # Staff Bank Details
    StaffBankDetailListView,
    StaffBankDetailCreateView,
    StaffBankDetailUpdateView,
    StaffBankDetailDeleteView,

    # Salary Structures
    SalaryStructureListView,
    SalaryStructureCreateView,
    SalaryStructureDetailView,
    SalaryStructureUpdateView,

    # New Payroll System
    process_payroll_view,
    export_payroll_to_excel, payroll_dashboard_view, remittance_dashboard_view, create_remittance_view,
    RemittanceDetailView, RemittanceListView, get_staff_remittance_details_ajax, finance_dashboard,
    finance_dashboard_print, OtherPaymentServiceListView, OtherPaymentServiceCreateView, OtherPaymentServiceDetailView,
    OtherPaymentServiceUpdateView, OtherPaymentServiceDeleteView, process_other_payment_ajax, OtherPaymentView,
    ajax_process_admission_funding, AdmissionSurgeryFundingView, staff_remittance_detail_view,
    finance_service_patient_payment, finance_wallet_tools_entry, finance_wallet_history, finance_wallet_withdrawal,
    finance_process_refund, process_direct_payment, transaction_list, transaction_detail, wallet_funding_only_page,
    UnifiedPaymentView, ajax_process_consultation_payment, ajax_reuse_consultation_payment,
    ajax_get_admission_surgery_details, ajax_process_other_payment, StaffTransactionHistoryView,
    PersonalStaffCollectionExcelView, PersonalStaffCollectionView, AllStaffCollectionsView,
    AllStaffCollectionsExcelView,
    AllStaffCollectionsPDFView, StaffTransactionHistoryExcelView, PersonalStaffCollectionPDFView,
    StaffTransactionHistoryPDFView,
)

urlpatterns = [
    # Registration Payments
    path('registration-payment/create/', RegistrationPaymentCreateView.as_view(), name='registration_payment_create'),
    path('registration-payment/index/', RegistrationPaymentListView.as_view(), name='registration_payment_index'),
    path('registration-payments/<int:pk>/', RegistrationPaymentDetailView.as_view(), name='registration_payment_detail'),
    path('registration-payments/<int:pk>/receipt/', print_receipt, name='print_registration_receipt'),

    # Wallet & Patient Payments
    path('funding/', patient_wallet_funding, name='patient_funding'),
    #path('verify-patient/', verify_patient_ajax, name='finance_verify_patient_ajax'),
    path('process-funding/', process_wallet_funding, name='process_funding'),
    path('wallet/dashboard/<int:patient_id>/', patient_wallet_dashboard, name='patient_wallet_dashboard'),
    path('payment/select/', finance_payment_select, name='finance_payment_select'),
    path('payment/consultation/<int:patient_id>/', finance_consultation_patient_payment, name='finance_consultation_patient_payment'),
    path('payment/pharmacy/<int:patient_id>/', finance_pharmacy_patient_payment, name='finance_pharmacy_patient_payment'),
    path('payment/laboratory/<int:patient_id>/', finance_laboratory_patient_payment, name='finance_laboratory_patient_payment'),
    path('payment/scan/<int:patient_id>/', finance_scan_patient_payment, name='finance_scan_patient_payment'),
    path('payment/service/<int:patient_id>/', finance_service_patient_payment, name='finance_service_patient_payment'),
    path('transactions/', PatientTransactionListView.as_view(), name='patient_transaction_index'),
    #path('transactions/<int:pk>/', PatientTransactionDetailView.as_view(), name='patient_transaction_detail'),
    path('payment/other/', OtherPaymentView.as_view(), name='finance_other_payment'),
    path('ajax/payment/other/process/', process_other_payment_ajax, name='ajax_process_other_payment'),
    path('funding/admission/<int:patient_id>/', AdmissionSurgeryFundingView.as_view(), name='finance_admission_funding'),
    path('ajax/funding/process/', ajax_process_admission_funding, name='ajax_process_admission_funding'),


    # Finance Settings
    path('setting/create/', FinanceSettingCreateView.as_view(), name='finance_setting_create'),
    path('setting/<int:pk>/detail/', FinanceSettingDetailView.as_view(), name='finance_setting_detail'),
    path('setting/<int:pk>/edit/', FinanceSettingUpdateView.as_view(), name='finance_setting_edit'),

    # Expense Categories
    path('expense-categories/', ExpenseCategoryListView.as_view(), name='expense_category_index'),
    path('expense-categories/create/', ExpenseCategoryCreateView.as_view(), name='expense_category_create'),
    path('expense-categories/<int:pk>/update/', ExpenseCategoryUpdateView.as_view(), name='expense_category_update'),
    path('expense-categories/<int:pk>/delete/', ExpenseCategoryDeleteView.as_view(), name='expense_category_delete'),


    # Expenses
    path('expenses/', ExpenseListView.as_view(), name='expense_index'),
    path('expenses/create/', ExpenseCreateView.as_view(), name='expense_create'),
    path('expenses/<int:pk>/', ExpenseDetailView.as_view(), name='expense_detail'),
    path('expenses/<int:pk>/edit/', ExpenseUpdateView.as_view(), name='expense_update'),

    # Income Categories
    path('income-categories/', IncomeCategoryListView.as_view(), name='income_category_index'),
    path('income-categories/create/', IncomeCategoryCreateView.as_view(), name='income_category_create'),
    path('income-categories/<int:pk>/update/', IncomeCategoryUpdateView.as_view(), name='income_category_update'),
    path('income-categories/<int:pk>/delete/', IncomeCategoryDeleteView.as_view(), name='income_category_delete'),

    # Income
    path('income/', IncomeListView.as_view(), name='income_index'),
    path('income/create/', IncomeCreateView.as_view(), name='income_create'),
    path('income/<int:pk>/', IncomeDetailView.as_view(), name='income_detail'),
    path('income/<int:pk>/edit/', IncomeUpdateView.as_view(), name='income_update'),

    path('other-services/', OtherPaymentServiceListView.as_view(), name='other_payment_service_list'),
    path('other-services/create/', OtherPaymentServiceCreateView.as_view(), name='other_payment_service_create'),
    path('other-services/<int:pk>/', OtherPaymentServiceDetailView.as_view(), name='other_payment_service_detail'),
    path('other-services/<int:pk>/edit/', OtherPaymentServiceUpdateView.as_view(), name='other_payment_service_edit'),
    path('other-services/<int:pk>/delete/', OtherPaymentServiceDeleteView.as_view(),
         name='other_payment_service_delete'),

    # Staff Bank Details
    path('staff-bank-details/', StaffBankDetailListView.as_view(), name='staff_bank_detail_index'),
    path('staff-bank-details/create/', StaffBankDetailCreateView.as_view(), name='staff_bank_detail_create'),
    path('staff-bank-details/<int:pk>/update/', StaffBankDetailUpdateView.as_view(), name='staff_bank_detail_update'),
    path('staff-bank-details/<int:pk>/delete/', StaffBankDetailDeleteView.as_view(), name='staff_bank_detail_delete'),

    # Salary Structures
    path('salary-structures/', SalaryStructureListView.as_view(), name='salary_structure_index'),
    path('salary-structures/create/', SalaryStructureCreateView.as_view(), name='salary_structure_create'),
    path('salary-structures/<int:pk>/', SalaryStructureDetailView.as_view(), name='salary_structure_detail'),
    path('salary-structures/<int:pk>/edit/', SalaryStructureUpdateView.as_view(), name='salary_structure_update'),

    # New Payroll System
    path('payroll/process/', process_payroll_view, name='process_payroll'),
    path('payroll/export/<int:year>/<int:month>/', export_payroll_to_excel, name='export_payroll_to_excel'),
    path('payroll/dashboard/', payroll_dashboard_view, name='payroll_dashboard'),

    path('remittance/dashboard/', remittance_dashboard_view, name='remittance_dashboard'),
    path('remittance/create/', create_remittance_view, name='remittance_create'),
    path('remittance/list/', RemittanceListView.as_view(), name='remittance_list'),
    path('remittance/<int:pk>/', RemittanceDetailView.as_view(), name='remittance_detail'),
    path('remittance/staff-detail/<int:staff_id>/', staff_remittance_detail_view, name='staff_remittance_detail'),

    # AJAX Helper URL
    path('ajax/get-remittance-details/', get_staff_remittance_details_ajax, name='get_staff_remittance_details_ajax'),

    path('dashboard/', finance_dashboard, name='finance_dashboard'),
    path('dashboard/print/', finance_dashboard_print, name='finance_dashboard_print'),

    path('wallet/tools/', finance_wallet_tools_entry, name='finance_wallet_tools_entry'),

    # New Wallet Views
    path('wallet/history/<int:patient_id>/', finance_wallet_history, name='finance_wallet_history'),
    path('wallet/withdrawal/<int:patient_id>/', finance_wallet_withdrawal, name='finance_wallet_withdrawal'),
    path('wallet/refund/<int:patient_id>/', finance_process_refund, name='finance_process_refund'),

    # NEW: Direct payment processing
    path('process-direct-payment/', process_direct_payment, name='process_direct_payment'),

    # EXISTING: Keep wallet funding for those who want to fund wallet only
    path('process-wallet-funding/', process_wallet_funding, name='process_wallet_funding'),

    # NEW: Separate wallet funding page (optional)
    path('wallet-funding-only/', wallet_funding_only_page, name='wallet_funding_only'),

    # Transaction views
    path('transactions/', transaction_list, name='patient_transaction_index'),
    path('transactions/<int:transaction_id>/', transaction_detail, name='transaction_detail'),

    # Patient verification AJAX
    path('verify-patient-ajax/', verify_patient_ajax, name='finance_verify_patient_ajax'),

    # Print receipt
    path('transactions/<int:transaction_id>/print/', print_receipt, name='print_receipt'),

    path('payment/unified/', UnifiedPaymentView.as_view(), name='finance_unified_payment'),


    # AJAX endpoints for consultation
    path('ajax/consultation/payment/', ajax_process_consultation_payment,
         name='ajax_process_consultation_payment'),
    path('ajax/consultation/reuse/', ajax_reuse_consultation_payment, name='ajax_reuse_consultation_payment'),

    # AJAX endpoints for admission/surgery
    path('ajax/admission-surgery/details/', ajax_get_admission_surgery_details,
         name='ajax_get_admission_surgery_details'),
    path('ajax/admission-surgery/payment/', ajax_process_admission_funding,
         name='ajax_process_admission_funding'),

    # AJAX endpoint for other payments
    path('ajax/payment/other/', ajax_process_other_payment, name='ajax_process_other_payment'),


    path('personal-collection/',PersonalStaffCollectionView.as_view(),name='personal_staff_collection'),
    path('personal-collection/export/excel/', PersonalStaffCollectionExcelView.as_view(),name='personal_collection_export_excel'),
    path('personal-collection/export/pdf/', PersonalStaffCollectionPDFView.as_view(),name='personal_collection_export_pdf'),

    # ==== ALL STAFF COLLECTIONS ====
    path('all-staff-collections/', AllStaffCollectionsView.as_view(), name='all_staff_collections'),
    path('all-staff-collections/export/excel/', AllStaffCollectionsExcelView.as_view(), name='all_staff_export_excel'),
    path('all-staff-collections/export/pdf/', AllStaffCollectionsPDFView.as_view(), name='all_staff_export_pdf'),

    # ==== STAFF TRANSACTION HISTORY ====
    path('transaction-history/', StaffTransactionHistoryView.as_view(), name='staff_transaction_history'),
    path('transaction-history/export/excel/', StaffTransactionHistoryExcelView.as_view(), name='staff_history_export_excel'),
    path('transaction-history/export/pdf/', StaffTransactionHistoryPDFView.as_view(), name='staff_history_export_pdf'),
   ]

