import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
import stripe
from django.contrib import admin
from django.test import override_settings

from .models import Feature, Price, Product, ProductFeature, Provider, ProviderConfiguration
from .services import STRIPE_WEBHOOK_EVENTS, build_invoice_pdf, create_esewa_checkout, create_khalti_checkout, handle_webhook, verify_esewa_response


@pytest.mark.django_db
def test_price_amount_is_smallest_currency_unit():
    product = Product.objects.create(name="Pro", slug="pro")
    price = Price.objects.create(product=product, amount=2999, currency="USD")
    assert price.amount_decimal == 29.99
    assert str(price) == "Pro - 29.99 USD / month"


@pytest.mark.django_db
def test_product_features_are_unique_and_feature_gate_data_is_persisted():
    product = Product.objects.create(name="Pro", slug="pro")
    feature = Feature.objects.create(key="advanced-reports", name="Advanced Reports")
    ProductFeature.objects.create(product=product, feature=feature)
    assert product.product_features.get().feature == feature
    with pytest.raises(Exception):
        ProductFeature.objects.create(product=product, feature=feature)


@pytest.mark.django_db
def test_provider_configuration_is_seedable_and_unique():
    for provider in Provider:
        ProviderConfiguration.objects.create(provider=provider)
    assert ProviderConfiguration.objects.count() == 3


def test_stripe_webhook_event_scope_is_payment_and_billing_only():
    assert "checkout.session.completed" in STRIPE_WEBHOOK_EVENTS
    assert "payment_intent.succeeded" in STRIPE_WEBHOOK_EVENTS
    assert "invoice.paid" in STRIPE_WEBHOOK_EVENTS
    assert "customer.subscription.updated" in STRIPE_WEBHOOK_EVENTS
    assert "refund.updated" in STRIPE_WEBHOOK_EVENTS
    assert "balance.available" not in STRIPE_WEBHOOK_EVENTS


def test_local_invoice_pdf_is_valid_pdf_bytes():
    pdf = build_invoice_pdf(invoice_number="INV-KHALTI-00000001", tenant_name="Acme", provider=Provider.KHALTI, product_name="Pro", amount="100.00", currency="NPR", payment_reference="txn-123", issued_at=datetime(2026, 8, 25, tzinfo=timezone.utc))
    assert pdf.startswith(b"%PDF-1.4")
    assert b"INV-KHALTI-00000001" in pdf
    assert pdf.endswith(b"%%EOF\n")


def test_stripe_webhook_uses_official_sdk(monkeypatch, settings):
    event = {"id": "evt_test", "type": "test.event", "data": {"object": {}}}
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda payload, signature, secret: SimpleNamespace(to_dict_recursive=lambda: event))
    settings.STRIPE_WEBHOOK_SECRET = "whsec_test"
    webhook = handle_webhook(b"{}", "test-signature")
    assert webhook.event_id == "evt_test"


def test_esewa_signature_verification_rejects_tampering():
    data = {"transaction_code": "000ABCD", "status": "COMPLETE", "total_amount": "100.00", "transaction_uuid": "test-uuid", "product_code": "EPAYTEST", "signed_field_names": "transaction_code,status,total_amount,transaction_uuid,product_code"}
    message = ",".join(f"{name}={data[name]}" for name in data["signed_field_names"].split(","))
    data["signature"] = base64.b64encode(hmac.new(b"test-secret", message.encode(), hashlib.sha256).digest()).decode()
    with override_settings(ESEWA_SECRET_KEY="test-secret"):
        assert verify_esewa_response(base64.b64encode(json.dumps(data).encode()).decode())["status"] == "COMPLETE"
        data["total_amount"] = "999.00"
        with pytest.raises(ValueError, match="Invalid eSewa response signature"):
            verify_esewa_response(base64.b64encode(json.dumps(data).encode()).decode())


def test_khalti_checkout_requires_npr_and_one_time_price(monkeypatch):
    request = SimpleNamespace(tenant=SimpleNamespace(pk=1), user=SimpleNamespace(name="Test User", email="test@example.com", phone="9800000000"), build_absolute_uri=lambda path: f"https://tenant.example{path}")
    price = SimpleNamespace(currency="NPR", is_recurring=False, amount=10000, product=SimpleNamespace(name="Pro"))
    monkeypatch.setattr("django_template.billing.services.providers._json_request", lambda *args, **kwargs: {"pidx": "pidx-test", "payment_url": "https://pay.test/khalti"})
    with override_settings(KHALTI_SECRET_KEY="test-key", KHALTI_ENVIRONMENT="sandbox"):
        result = create_khalti_checkout(request, price)
    assert result.provider == Provider.KHALTI
    assert result.reference == "pidx-test"


def test_khalti_checkout_rejects_recurring_price():
    request = SimpleNamespace(tenant=SimpleNamespace(pk=1), build_absolute_uri=lambda path: f"https://tenant.example{path}")
    price = SimpleNamespace(currency="NPR", is_recurring=True, amount=10000, product=SimpleNamespace(name="Pro"))
    with pytest.raises(ValueError, match="one-time checkout"):
        create_khalti_checkout(request, price)


def test_esewa_checkout_builds_signed_uat_form():
    request = SimpleNamespace(tenant=SimpleNamespace(pk=1), build_absolute_uri=lambda path: f"https://tenant.example{path}")
    price = SimpleNamespace(currency="NPR", is_recurring=False, amount=10000, product=SimpleNamespace(name="Pro"))
    with override_settings(ESEWA_SECRET_KEY="test-secret", ESEWA_PRODUCT_CODE="EPAYTEST", ESEWA_ENVIRONMENT="sandbox"):
        result = create_esewa_checkout(request, price)
    assert result.provider == Provider.ESEWA
    assert result.form_fields["total_amount"] == "100.00"


def test_billing_models_are_registered_in_admin():
    assert ProviderConfiguration in admin.site._registry
    assert Product in admin.site._registry
    assert Price in admin.site._registry
