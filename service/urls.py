from django.urls import path
from . import views


urlpatterns = [
    # Service Category URLs
    path('category/', views.ServiceCategoryListView.as_view(), name='service_category_list'),
    path('category/create/', views.ServiceCategoryCreateView.as_view(), name='service_category_create'),
    path('category/<int:pk>/update/', views.ServiceCategoryUpdateView.as_view(), name='service_category_update'),
    path('category/<int:pk>/delete/', views.ServiceCategoryDeleteView.as_view(), name='service_category_delete'),

    # Service URLs
    path('service/', views.ServiceListView.as_view(), name='service_list'),
    path('service/create/', views.ServiceCreateView.as_view(), name='service_create'),
    path('service/<int:pk>/update/', views.ServiceUpdateView.as_view(), name='service_update'),
    path('service/<int:pk>/delete/', views.ServiceDeleteView.as_view(), name='service_delete'),

    # Service Item (Inventory) URLs
    path('item/', views.ServiceItemListView.as_view(), name='service_item_list'),
    path('item/create/', views.ServiceItemCreateView.as_view(), name='service_item_create'),
    path('item/<int:pk>/detail/', views.ServiceItemDetailView.as_view(), name='service_item_detail'),
    path('item/<int:pk>/update/', views.ServiceItemUpdateView.as_view(), name='service_item_update'),
    path('item/<int:pk>/delete/', views.ServiceItemDeleteView.as_view(), name='item_delete'),

    # Stock Management URL
    path('item/<int:item_pk>/manage-stock/', views.manage_stock, name='service_manage_stock'),

    # AJAX URL
    path('ajax/load-services-items/', views.load_services_or_items_ajax, name='ajax_load_services_items'),
]
