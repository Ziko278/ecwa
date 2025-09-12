from django.contrib import admin
from scan.models import ScanCategoryModel, ScanTemplateModel, ScanOrderModel, ScanImageModel, ScanResultModel


admin.site.register(ScanCategoryModel)
admin.site.register(ScanTemplateModel)
admin.site.register(ScanOrderModel)
admin.site.register(ScanImageModel)
admin.site.register(ScanResultModel)