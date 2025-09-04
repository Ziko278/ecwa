from django.contrib import admin
from finance.models import PatientTransactionModel, FinanceSettingModel


admin.site.register(PatientTransactionModel)
admin.site.register(FinanceSettingModel)