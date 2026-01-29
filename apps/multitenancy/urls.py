from django.urls import path

from . import views

app_name = 'multitenancy'

urlpatterns = [
    path('tenants/', views.TenantListView.as_view(), name='list'),
    path('tenants/create/', views.TenantCreateView.as_view(), name='create'),
    path('tenants/<str:pk>/', views.TenantDetailView.as_view(), name='detail'),
    path('tenants/<str:pk>/invite/', views.TenantInviteView.as_view(), name='invite'),
    path('tenants/<str:pk>/switch/', views.switch_tenant, name='switch'),
]
