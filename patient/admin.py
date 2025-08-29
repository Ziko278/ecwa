from django.contrib import admin
from patient.models import PatientIDGeneratorModel, PatientWalletModel, RegistrationFeeModel


admin.site.register(PatientIDGeneratorModel)
admin.site.register(PatientWalletModel)
admin.site.register(RegistrationFeeModel)