from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"payment-intents", views.PaymentIntentViewSet, basename="payment-intent")
router.register(r"setup-intents", views.SetupIntentViewSet, basename="setup-intent")
router.register(r"payment-methods", views.PaymentMethodViewSet, basename="payment-method")
router.register(r"subscriptions", views.SubscriptionViewSet, basename="subscription")
router.register(r"subscription-schedules", views.SubscriptionScheduleViewSet, basename="subscription-schedule")

stripe_urls = [
    path("", include("djstripe.urls", namespace="djstripe")),
]

urlpatterns = [
    path("stripe/", include(stripe_urls)),
    path("", include(router.urls)),
]
