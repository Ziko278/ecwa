# patient/urls.py
from django.urls import path
from .views import (
    RegistrationPaymentCreateView,
    RegistrationPaymentListView, RegistrationPaymentDetailView, print_receipt,
)

urlpatterns = [
    path('registration-payment/create', RegistrationPaymentCreateView.as_view(), name='registration_payment_create'),
    path('registration-payment/index', RegistrationPaymentListView.as_view(), name='registration_payment_index'),
    path('registration-payments/<int:pk>/', RegistrationPaymentDetailView.as_view(), name='registration_payment_detail'),
    path('registration-payments/<int:pk>/receipt/', print_receipt, name='print_registration_receipt'),
]