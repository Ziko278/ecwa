from django.contrib import admin
from scan.models import ScanCategoryModel, ScanTemplateModel, ScanOrderModel


admin.site.register(ScanCategoryModel)
admin.site.register(ScanTemplateModel)
admin.site.register(ScanOrderModel)