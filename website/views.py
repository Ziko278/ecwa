from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = "website/home.html"


class AboutView(TemplateView):
    template_name = "website/about.html"


class ServicesView(TemplateView):
    template_name = "website/services.html"


class DoctorsView(TemplateView):
    template_name = "website/doctors.html"


class ContactView(TemplateView):
    template_name = "website/contact.html"


class InPatientServiceView(TemplateView):
    template_name = "website/services/in_patient.html"


class OutPatientServiceView(TemplateView):
    template_name = "website/services/out_patient.html"


class PhysiotherapyServiceView(TemplateView):
    template_name = "website/services/physiotherapy.html"


class SurgeryServiceView(TemplateView):
    template_name = "website/services/surgery.html"


class EyeClinicServiceView(TemplateView):
    template_name = "website/services/eye_clinic.html"
