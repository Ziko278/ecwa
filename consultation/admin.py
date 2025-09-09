from django.contrib import admin
from consultation.models import PatientQueueModel, ConsultationSessionModel

admin.site.register(PatientQueueModel)
admin.site.register(ConsultationSessionModel)
