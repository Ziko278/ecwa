from django.contrib.auth.models import User
from django.db import models
from admin_site.model_info import *


class SiteInfoModel(models.Model):
    name = models.CharField(max_length=150)
    short_name = models.CharField(max_length=50)
    mobile_1 = models.CharField(max_length=20)
    mobile_2 = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(max_length=100)
    address = models.CharField(max_length=255, null=True, blank=True)

    logo = models.FileField(upload_to='images/setting/logo')

    # social media handles
    facebook_handle = models.CharField(max_length=100, null=True, blank=True)
    twitter_handle = models.CharField(max_length=100, null=True, blank=True)
    linkedin_handle = models.CharField(max_length=100, null=True, blank=True)
    youtube_handle = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return self.short_name.upper()


class DaysModel(models.Model):
    name = models.CharField(max_length=10)

    def __str__(self):
        return self.name.upper()


class ActivityLogModel(models.Model):
    log = models.TextField()
    category = models.CharField(max_length=50)
    sub_category = models.CharField(max_length=50)
    keywords = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
