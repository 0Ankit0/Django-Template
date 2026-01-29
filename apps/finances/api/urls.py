from django.urls import include, path
from rest_framework.routers import DefaultRouter
from finances import views as api_views
from . import admin_refund as views_admin

app_name = 'finances_api'

router = DefaultRouter()
router.register(r"payment-intents", api_views.PaymentIntentViewSet, basename="payment-intent")
router.register(r"setup-intents", api_views.SetupIntentViewSet, basename="setup-intent")
router.register(r"payment-methods", api_views.PaymentMethodViewSet, basename="payment-method")
router.register(r"subscriptions", api_views.SubscriptionViewSet, basename="subscription")
router.register(r"subscription-schedules", api_views.SubscriptionScheduleViewSet, basename="subscription-schedule")

stripe_urls = [
    path("", include("djstripe.urls", namespace="djstripe")),
]

admin_urls = [
    path(r"payment-intent/<str:pk>/refund/", views_admin.AdminRefundView.as_view(), name="payment-intent-refund"),
]

urlpatterns = [
    path("stripe/", include(stripe_urls)),
    path("", include(router.urls)),
    path("", include(admin_urls)),
]
