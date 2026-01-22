from django.contrib import admin
from patient.models import PatientIDGeneratorModel, PatientWalletModel, RegistrationFeeModel, RegistrationPaymentModel


admin.site.register(PatientIDGeneratorModel)
admin.site.register(PatientWalletModel)
admin.site.register(RegistrationFeeModel)
admin.site.register(RegistrationPaymentModel)