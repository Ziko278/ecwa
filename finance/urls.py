# patient/urls.py
from django.urls import path
from finance.views import *
urlpatterns = [
    path('registration-payment/create', RegistrationPaymentCreateView.as_view(), name='registration_payment_create'),
    path('registration-payment/index', RegistrationPaymentListView.as_view(), name='registration_payment_index'),
    path('registration-payments/<int:pk>/', RegistrationPaymentDetailView.as_view(), name='registration_payment_detail'),
    path('registration-payments/<int:pk>/receipt/', print_receipt, name='print_registration_receipt'),

    path('funding/', patient_wallet_funding, name='patient_funding'),
    path('verify-patient/', verify_patient_ajax, name='finance_verify_patient_ajax'),
    path('calculate-total/', calculate_payment_total_ajax, name='calculate_total_ajax'),
    path('process-funding/', process_wallet_funding, name='process_funding'),
    path('process-payment/', process_wallet_payment, name='process_payment'),
    path('dashboard/<int:patient_id>/', patient_wallet_dashboard, name='patient_wallet_dashboard'),

    path('payment/select/', finance_payment_select, name='finance_payment_select'),
    path('payment/consultation/<int:patient_id>/', finance_consultation_patient_payment, name='finance_consultation_patient_payment'),
    path('payment/pharmacy/<int:patient_id>/', finance_pharmacy_patient_payment, name='finance_pharmacy_patient_payment'),
    path('payment/laboratory/<int:patient_id>/', finance_laboratory_patient_payment, name='finance_laboratory_patient_payment'),
    path('payment/scan/<int:patient_id>/', finance_scan_patient_payment, name='finance_scan_patient_payment'),
    path('payment/index/', PatientTransactionListView.as_view(), name='patient_transaction_index'),
    path('transactions/<int:pk>/', PatientTransactionDetailView.as_view(), name='patient_transaction_detail'),

    path('setting/create/', FinanceSettingCreateView.as_view(), name='finance_setting_create'),
    path('setting/<int:pk>/detail/', FinanceSettingDetailView.as_view(), name='finance_setting_detail'),
    path('setting/<int:pk>/edit/', FinanceSettingUpdateView.as_view(), name='finance_setting_edit'),

    path('expense-categories/', ExpenseCategoryListView.as_view(), name='expense_category_index'),
    path('expense-categories/create/', ExpenseCategoryCreateView.as_view(), name='expense_category_create'),
    path('expense-categories/<int:pk>/update/', ExpenseCategoryUpdateView.as_view(),
         name='expense_category_update'),
    path('expense-categories/<int:pk>/delete/', ExpenseCategoryDeleteView.as_view(),
         name='expense_category_delete'),

    # Quotation URLs
    path('quotations/', QuotationListView.as_view(), name='quotation_index'),
    path('quotations/create-self/', QuotationCreateSelfView.as_view(), name='quotation_create_self'),
    path('quotations/create-others/', QuotationCreateOthersView.as_view(), name='quotation_create_others'),
    path('quotations/<int:pk>/', QuotationDetailView.as_view(), name='quotation_detail'),
    path('quotations/<int:pk>/edit-self/', QuotationUpdateSelfView.as_view(), name='quotation_edit_self'),
    path('quotations/<int:pk>/edit-others/', QuotationUpdateOthersView.as_view(), name='quotation_edit_others'),

    # Quotation Approval URLs
    path('quotations/<int:pk>/dept-review/', QuotationDeptReviewView.as_view(), name='quotation_dept_review'),
    path('quotations/<int:pk>/general-review/', QuotationGeneralReviewView.as_view(),
         name='quotation_general_review'),
    path('quotations/<int:pk>/collect-money/', quotation_collect_money, name='quotation_collect_money'),

    # AJAX URLs for Quotation Items
    path('quotations/<int:quotation_pk>/items/create/', quotation_item_create_ajax,
         name='quotation_item_create_ajax'),
    path('quotation-items/<int:item_pk>/update/', quotation_item_update_ajax, name='quotation_item_update_ajax'),
    path('quotation-items/<int:item_pk>/delete/', quotation_item_delete_ajax, name='quotation_item_delete_ajax'),
    path('quotations/<int:quotation_pk>/items/', quotation_items_get_ajax, name='quotation_items_get_ajax'),

    # Expense URLs
    path('expenses/', ExpenseListView.as_view(), name='expense_index'),
    path('expenses/create/', ExpenseCreateView.as_view(), name='expense_create'),
    path('expenses/<int:pk>/', ExpenseDetailView.as_view(), name='expense_detail'),
    path('expenses/<int:pk>/edit/', ExpenseUpdateView.as_view(), name='expense_update'),

    # Income Category URLs (Simple Pattern)
    path('income-categories/', IncomeCategoryListView.as_view(), name='income_category_index'),
    path('income-categories/create/', IncomeCategoryCreateView.as_view(), name='income_category_create'),
    path('income-categories/<int:pk>/update/', IncomeCategoryUpdateView.as_view(), name='income_category_update'),
    path('income-categories/<int:pk>/delete/', IncomeCategoryDeleteView.as_view(), name='income_category_delete'),

    # Income URLs
    path('income/', IncomeListView.as_view(), name='income_index'),
    path('income/create/', IncomeCreateView.as_view(), name='income_create'),
    path('income/<int:pk>/', IncomeDetailView.as_view(), name='income_detail'),
    path('income/<int:pk>/edit/', IncomeUpdateView.as_view(), name='income_update'),

    # Staff Bank Detail URLs (Simple Pattern)
    path('staff-bank-details/', StaffBankDetailListView.as_view(), name='staff_bank_detail_index'),
    path('staff-bank-details/create/', StaffBankDetailCreateView.as_view(), name='staff_bank_detail_create'),
    path('staff-bank-details/<int:pk>/update/', StaffBankDetailUpdateView.as_view(),
         name='staff_bank_detail_update'),
    path('staff-bank-details/<int:pk>/delete/', StaffBankDetailDeleteView.as_view(),
         name='staff_bank_detail_delete'),

    # Salary Structure URLs
    path('salary-structures/', SalaryStructureListView.as_view(), name='salary_structure_index'),
    path('salary-structures/create/', SalaryStructureCreateView.as_view(), name='salary_structure_create'),
    path('salary-structures/<int:pk>/', SalaryStructureDetailView.as_view(), name='salary_structure_detail'),
    path('salary-structures/<int:pk>/edit/', SalaryStructureUpdateView.as_view(), name='salary_structure_update'),

    # Salary Record URLs
    path('salary-records/', SalaryRecordListView.as_view(), name='salary_record_index'),
    path('salary-records/create/', SalaryRecordCreateView.as_view(), name='salary_record_create'),
    path('salary-records/<int:pk>/', SalaryRecordDetailView.as_view(), name='salary_record_detail'),
    path('salary-records/<int:pk>/edit/', SalaryRecordUpdateView.as_view(), name='salary_record_update'),
    path('salary-records/<int:pk>/pay/', salary_record_pay, name='salary_record_pay'),
    path('salary-records/bulk-generate/', bulk_salary_generation, name='bulk_salary_generation'),

    # AJAX Helper URLs
    path('ajax/staff-salary-structure/<int:staff_id>/', get_staff_salary_structure_ajax,
         name='get_staff_salary_structure_ajax'),

]