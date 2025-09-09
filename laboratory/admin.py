from django.contrib import admin
from laboratory.models import LabTestOrderModel, LabTestTemplateModel, LabTestResultModel


admin.site.register(LabTestOrderModel)
admin.site.register(LabTestTemplateModel)
admin.site.register(LabTestResultModel)

