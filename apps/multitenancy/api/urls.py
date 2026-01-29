from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'multitenancy_api'

router = DefaultRouter()
router.register(r"tenants", views.TenantViewSet, basename="tenant")
router.register(r"memberships", views.TenantMembershipViewSet, basename="membership")
router.register(r"invitations", views.TenantInvitationViewSet, basename="invitation")

urlpatterns = router.urls
