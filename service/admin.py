from django.contrib import admin
from service.models import Service, PatientServiceTransaction, ServiceResult


admin.site.register(Service)
admin.site.register(PatientServiceTransaction)
admin.site.register(ServiceResult)
