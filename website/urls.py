from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name="home"),
    path('about/', views.AboutView.as_view(), name="about"),
    path('services/', views.ServicesView.as_view(), name="services"),
    path('doctors/', views.DoctorsView.as_view(), name="doctors"),
    path('contact/', views.ContactView.as_view(), name="contact"),

    # sub services
    path('services/in-patient/', views.InPatientServiceView.as_view(), name="in_patient"),
    path('services/out-patient/', views.OutPatientServiceView.as_view(), name="out_patient"),
    path('services/physiotherapy/', views.PhysiotherapyServiceView.as_view(), name="physiotherapy"),
    path('services/surgery/', views.SurgeryServiceView.as_view(), name="surgery"),
    path('services/eye-clinic/', views.EyeClinicServiceView.as_view(), name="eye_clinic"),
]
