from django.contrib import admin
from pharmacy.models import DrugOrderModel, DrugModel, GenericDrugModel


admin.site.register(DrugOrderModel)
admin.site.register(DrugModel)
admin.site.register(GenericDrugModel)