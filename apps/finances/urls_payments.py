"""Payment API URL configuration"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    PaymentMethodViewSet,
    SetupIntentViewSet,
)
from .views_payments import (
    InitiatePaymentView,
    PaymentConfigView,
    PaymentTransactionViewSet,
    PaymentWebhookView,
    VerifyPaymentView,
)

router = DefaultRouter()
router.register(r"transactions", PaymentTransactionViewSet, basename="payment-transaction")
router.register(r"setup_intents", SetupIntentViewSet, basename="setup-intent")
router.register(r"payment_methods", PaymentMethodViewSet, basename="payment-method")

urlpatterns = [
    path("payments/initiate/", InitiatePaymentView.as_view(), name="payment-initiate"),
    path("payments/verify/", VerifyPaymentView.as_view(), name="payment-verify"),
    path("payments/config/", PaymentConfigView.as_view(), name="payment-config"),
    path("payments/webhook/<str:gateway>/", PaymentWebhookView.as_view(), name="payment-webhook"),
] + router.urls
