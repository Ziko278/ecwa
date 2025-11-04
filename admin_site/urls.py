from django.urls import path
from admin_site.views import *

urlpatterns = [
    path('', dashboard, name='admin_dashboard'),
    
    path('sign-in', user_sign_in_view, name='login'),
    path('sign-out', user_sign_out_view, name='logout'),
    path('change-password/', change_password_view, name='change_password'),

    path('site-info/create', SiteInfoCreateView.as_view(), name='site_info_create'),
    path('site-info/<int:pk>/detail', SiteInfoDetailView.as_view(), name='site_info_detail'),
    path('site-info/<int:pk>/edit', SiteInfoUpdateView.as_view(), name='site_info_edit'),


    path('wallet', dashboard, name='patient_wallet_fund'),

    path('reports/lab/financial/', LabFinancialReportView.as_view(), name='lab_report_financial'),
    path('reports/lab/financial/export/excel/', LabFinancialReportExportExcelView.as_view(), name='lab_report_financial_export_excel'),
    path('reports/lab/financial/export/pdf/', LabFinancialReportExportPDFView.as_view(), name='lab_report_financial_export_pdf'),

    path('reports/scan/financial/', ScanFinancialReportView.as_view(), name='scan_report_financial'),
    path('reports/scan/financial/export/excel/', ScanFinancialReportExportExcelView.as_view(), name='scan_report_financial_export_excel'),
    path('reports/scan/financial/export/pdf/', ScanFinancialReportExportPDFView.as_view(), name='scan_report_financial_export_pdf'),

    path('reports/consultation/', ConsultationReportView.as_view(), name='consultation_report'),
    path('reports/consultation/export/excel/', ConsultationReportExportExcelView.as_view(), name='consultation_report_export_excel'),
    path('reports/consultation/export/pdf/', ConsultationReportExportPDFView.as_view(), name='consultation_report_export_pdf'),

    path('reports/general-financial/', GeneralFinancialReportView.as_view(), name='general_financial_report'),
    path('reports/general-financial/export/excel/', GeneralFinancialReportExcelView.as_view(), name='general_financial_export_excel'),
    path('reports/general-financial/export/pdf/', GeneralFinancialReportPDFView.as_view(), name='general_financial_export_pdf'),


]

