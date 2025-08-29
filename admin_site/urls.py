from django.urls import path
from admin_site.views import *

urlpatterns = [
    path('', dashboard, name='admin_dashboard'),
    
    path('sign-in', user_sign_in_view, name='login'),
    path('sign-out', user_sign_out_view, name='logout'),

    path('site-info/create', SiteInfoCreateView.as_view(), name='site_info_create'),
    path('site-info/<int:pk>/detail', SiteInfoDetailView.as_view(), name='site_info_detail'),
    path('site-info/<int:pk>/edit', SiteInfoUpdateView.as_view(), name='site_info_edit'),


    path('wallet', dashboard, name='patient_wallet_fund'),

]

