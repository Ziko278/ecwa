from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('portal/', include('admin_site.urls')),
    path('portal/consultation/', include('consultation.urls')),
    path('portal/finance/', include('finance.urls')),
    path('portal/human-resource/', include('human_resource.urls')),
    path('portal/insurance/', include('insurance.urls')),
    path('portal/inpatient/', include('inpatient.urls')),
    path('portal/laboratory/', include('laboratory.urls')),
    path('portal/patient/', include('patient.urls')),
    path('portal/pharmacy/', include('pharmacy.urls')),
    path('portal/scan/', include('scan.urls')),
    path('portal/service/', include('service.urls')),
    path('', include('website.urls')),
    path('django-admin/', admin.site.urls),
]

handler404 = 'admin_site.views.custom_404_view'
handler403 = 'admin_site.views.custom_403_view'
handler500 = 'admin_site.views.custom_500_view'

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)


