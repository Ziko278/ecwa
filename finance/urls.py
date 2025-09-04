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

]