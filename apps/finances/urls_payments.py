"""Payment API URL configuration"""

from django.urls import path
from rest_framework.routers import DefaultRouter

from .views_payments import (
    PaymentTransactionViewSet,
    InitiatePaymentView,
    VerifyPaymentView,
    PaymentConfigView,
    PaymentWebhookView,
)

router = DefaultRouter()
router.register(r'payments/transactions', PaymentTransactionViewSet, basename='payment-transaction')

urlpatterns = [
    path('payments/initiate/', InitiatePaymentView.as_view(), name='payment-initiate'),
    path('payments/verify/', VerifyPaymentView.as_view(), name='payment-verify'),
    path('payments/config/', PaymentConfigView.as_view(), name='payment-config'),
    path('payments/webhook/<str:gateway>/', PaymentWebhookView.as_view(), name='payment-webhook'),
] + router.urls
