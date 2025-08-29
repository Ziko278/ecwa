from django.contrib.auth.models import User
from django.db import models
from admin_site.model_info import TEMPORAL_STATUS, RECEIPT_FORMAT


class FinanceSettingModel(models.Model):
    default_receipt_format = models.CharField(max_length=50, choices=RECEIPT_FORMAT, blank=True, null=True)
    receipt_signature = models.FileField(upload_to='finance/setting/receipt', blank=True, null=True)

