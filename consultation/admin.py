from django.contrib import admin
from consultation.models import PatientQueueModel, ConsultationSessionModel, PatientVitalsModel

admin.site.register(PatientQueueModel)
admin.site.register(ConsultationSessionModel)
admin.site.register(PatientVitalsModel)
