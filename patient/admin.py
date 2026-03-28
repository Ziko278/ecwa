from django.contrib import admin
from patient.models import *

admin.site.register(PatientIDGeneratorModel)
admin.site.register(PatientWalletModel)
admin.site.register(RegistrationFeeModel)
admin.site.register(RegistrationPaymentModel)
admin.site.register(PatientModel)