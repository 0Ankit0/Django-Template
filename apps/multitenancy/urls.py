from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"tenants", views.TenantViewSet, basename="tenant")
router.register(r"memberships", views.TenantMembershipViewSet, basename="membership")
router.register(r"invitations", views.TenantInvitationViewSet, basename="invitation")

urlpatterns = router.urls

urlpatterns += [
    path('tenants/', views.TenantListView.as_view(), name='list'),
    path('tenants/create/', views.TenantCreateView.as_view(), name='create'),
    path('tenants/<int:pk>/', views.TenantDetailView.as_view(), name='detail'),
    path('tenants/<int:pk>/invite/', views.TenantInviteView.as_view(), name='invite'),
    path('tenants/<int:pk>/switch/', views.switch_tenant, name='switch'),
]
