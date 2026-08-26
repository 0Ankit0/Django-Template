from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("pricing/", views.pricing, name="pricing"),
    path("checkout/<int:price_id>/", views.checkout, name="checkout"),
    path("portal/", views.portal, name="portal"),
    path("cancel/", views.cancel, name="cancel"),
    path("success/", views.success, name="success"),
    path("cancelled/", views.cancelled, name="cancelled"),
    path("invoices/<int:invoice_id>/download/", views.invoice_download, name="invoice-download"),
    path("callback/khalti/", views.khalti_callback, name="khalti-callback"),
    path("callback/esewa/", views.esewa_callback, name="esewa-callback"),
    path("webhooks/stripe/", views.webhook, name="stripe-webhook"),
]
