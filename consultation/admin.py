from django.contrib import admin
from consultation.models import PatientQueueModel, ConsultationPaymentModel

admin.site.register(PatientQueueModel)
admin.site.register(ConsultationPaymentModel)
