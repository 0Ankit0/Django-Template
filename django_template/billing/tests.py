import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
import stripe
from django.contrib import admin
from django.test import override_settings

from .models import BillingCustomer, Feature, Invoice, Payment, Price, Product, ProductFeature, Provider, ProviderConfiguration, Subscription, WebhookEvent
from .services import (
    STRIPE_WEBHOOK_EVENTS,
    add_price_interval,
    build_invoice_pdf,
    create_esewa_checkout,
    create_khalti_checkout,
    create_or_update_one_time_subscription,
    handle_webhook,
    process_stripe_webhook_event,
    verify_esewa_response,
)


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
    pdf = build_invoice_pdf(
        invoice_number="INV-KHALTI-00000001",
        tenant_name="Acme",
        provider=Provider.KHALTI,
        product_name="Pro",
        amount="100.00",
        currency="NPR",
        payment_reference="txn-123",
        issued_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )
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
    data = {
        "transaction_code": "000ABCD",
        "status": "COMPLETE",
        "total_amount": "100.00",
        "transaction_uuid": "test-uuid",
        "product_code": "EPAYTEST",
        "signed_field_names": "transaction_code,status,total_amount,transaction_uuid,product_code",
    }
    message = ",".join(f"{name}={data[name]}" for name in data["signed_field_names"].split(","))
    data["signature"] = base64.b64encode(hmac.new(b"test-secret", message.encode(), hashlib.sha256).digest()).decode()
    with override_settings(ESEWA_SECRET_KEY="test-secret"):
        assert verify_esewa_response(base64.b64encode(json.dumps(data).encode()).decode())["status"] == "COMPLETE"
        data["total_amount"] = "999.00"
        with pytest.raises(ValueError, match="Invalid eSewa response signature"):
            verify_esewa_response(base64.b64encode(json.dumps(data).encode()).decode())


def test_khalti_checkout_requires_npr_and_one_time_price(monkeypatch):
    request = SimpleNamespace(
        tenant=SimpleNamespace(pk=1),
        user=SimpleNamespace(name="Test User", email="test@example.com", phone="9800000000"),
        build_absolute_uri=lambda path: f"https://tenant.example{path}",
    )
    price = SimpleNamespace(currency="NPR", is_recurring=False, amount=10000, product=SimpleNamespace(name="Pro"))
    monkeypatch.setattr(
        "django_template.billing.services.providers._json_request",
        lambda *args, **kwargs: {"pidx": "pidx-test", "payment_url": "https://pay.test/khalti"},
    )
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


def test_one_time_duration_uses_selected_interval_and_count():
    start = datetime(2026, 1, 31, 12, 0, tzinfo=timezone.utc)
    assert add_price_interval(start, SimpleNamespace(interval=Price.Interval.MONTH, interval_count=1)) == datetime(2026, 2, 28, 12, 0, tzinfo=timezone.utc)
    assert add_price_interval(start, SimpleNamespace(interval=Price.Interval.MONTH, interval_count=3)) == datetime(2026, 4, 30, 12, 0, tzinfo=timezone.utc)
    assert add_price_interval(start, SimpleNamespace(interval=Price.Interval.YEAR, interval_count=2)) == datetime(2028, 1, 31, 12, 0, tzinfo=timezone.utc)
    assert add_price_interval(start, SimpleNamespace(interval=Price.Interval.WEEK, interval_count=2)) == datetime(2026, 2, 14, 12, 0, tzinfo=timezone.utc)


@pytest.mark.django_db
def test_one_time_price_keeps_duration_interval_instead_of_using_one_time_interval():
    product = Product.objects.create(name="Annual Pass", slug="annual-pass")
    price = Price.objects.create(product=product, amount=12000, currency="NPR", interval=Price.Interval.YEAR, interval_count=1, metadata={"one_time": True})
    assert price.is_one_time is True
    assert price.interval == Price.Interval.YEAR
    assert price.interval_count == 1
    assert " / " not in str(price)


@pytest.mark.django_db
def test_one_time_payment_creates_subscription_until_selected_duration(_public_tenant):
    product = Product.objects.create(name="90 Day Pass", slug="90-day-pass")
    price = Price.objects.create(product=product, amount=9000, currency="NPR", interval=Price.Interval.DAY, interval_count=90, metadata={"one_time": True})
    paid_at = datetime(2026, 8, 30, 10, 0, tzinfo=timezone.utc)
    payment = Payment.objects.create(tenant=_public_tenant, amount=price.amount, currency=price.currency, status=Payment.Status.SUCCEEDED, provider=Provider.KHALTI, provider_payment_id="khalti-txn-90-day", paid_at=paid_at, metadata={"pidx": "pidx-90-day"})
    subscription = create_or_update_one_time_subscription(payment, price, provider_reference="pidx-90-day")
    assert subscription.provider == Provider.KHALTI
    assert subscription.status == subscription.Status.ACTIVE
    assert subscription.current_period_start == paid_at
    assert subscription.current_period_end == paid_at + timedelta(days=90)
    assert subscription.cancel_at_period_end is True
    assert subscription.canceled_at is None
    payment.refresh_from_db()
    assert payment.subscription_id == subscription.pk


@pytest.mark.django_db
def test_one_time_payment_requires_success(_public_tenant):
    product = Product.objects.create(name="Pro", slug="pro-payment-status")
    price = Price.objects.create(product=product, amount=1000, currency="NPR", interval=Price.Interval.MONTH, interval_count=1, metadata={"one_time": True})
    payment = Payment.objects.create(tenant=_public_tenant, amount=1000, currency="NPR", status=Payment.Status.PENDING, provider=Provider.ESEWA, provider_payment_id="esewa-pending")
    with pytest.raises(ValueError, match="successful payments"):
        create_or_update_one_time_subscription(payment, price, provider_reference="esewa-pending")


@pytest.mark.django_db
def test_stripe_invoice_paid_reconciles_subscription_and_payment_when_subscription_event_arrives_late(monkeypatch, _public_tenant):
    product = Product.objects.create(name="Pro", slug="stripe-pro")
    price = Price.objects.create(product=product, amount=1500, currency="USD", provider_price_id="price_stripe")
    BillingCustomer.objects.create(tenant=_public_tenant, provider=Provider.STRIPE, provider_customer_id="cus_test", email="test@example.com", name="Test User")
    webhook = WebhookEvent.objects.create(
        provider=Provider.STRIPE,
        event_id="evt_invoice_paid_late_subscription",
        event_type="invoice.paid",
        payload={"id": "evt_invoice_paid_late_subscription", "type": "invoice.paid", "data": {"object": {"id": "in_test", "customer": "cus_test", "subscription": "sub_test", "payment_intent": "pi_test", "status": "paid", "amount_due": 1500, "amount_paid": 1500, "currency": "usd", "number": "INV-TEST", "period_start": 1788150000, "period_end": 1790742000, "metadata": {"tenant_id": str(_public_tenant.pk), "price_id": str(price.pk)}}}},
    )

    objects = {
        "subscription": {"id": "sub_test", "customer": "cus_test", "status": "active", "items": {"data": [{"price": {"id": "price_stripe"}}]}, "current_period_start": 1788150000, "current_period_end": 1790742000, "cancel_at_period_end": False, "metadata": {"tenant_id": str(_public_tenant.pk), "price_id": str(price.pk)}},
        "payment_intent": {"id": "pi_test", "customer": "cus_test", "amount": 1500, "amount_received": 1500, "currency": "usd", "status": "succeeded", "metadata": {"tenant_id": str(_public_tenant.pk), "price_id": str(price.pk)}},
    }
    monkeypatch.setattr("django_template.billing.services.stripe_webhooks._stripe_retrieve", lambda kind, object_id: objects[kind])

    process_stripe_webhook_event(webhook)

    subscription = Subscription.objects.get(provider_subscription_id="sub_test")
    invoice = Invoice.objects.get(provider_invoice_id="in_test")
    payment = Payment.objects.get(provider_payment_id="pi_test")
    webhook.refresh_from_db()
    assert subscription.status == Subscription.Status.ACTIVE
    assert invoice.subscription_id == subscription.pk
    assert invoice.status == Invoice.Status.PAID
    assert payment.subscription_id == subscription.pk
    assert payment.status == Payment.Status.SUCCEEDED
    assert payment.provider_invoice_id == invoice.provider_invoice_id
    assert webhook.processed is True
    assert webhook.error == ""
    assert any(item["step"] == "processing_completed" for item in webhook.processing_log)


@pytest.mark.django_db
def test_stripe_webhook_failure_is_recorded_and_event_remains_retryable(_public_tenant):
    webhook = WebhookEvent.objects.create(
        provider=Provider.STRIPE,
        event_id="evt_bad_invoice",
        event_type="invoice.paid",
        payload={"id": "evt_bad_invoice", "type": "invoice.paid", "data": {"object": {"id": "in_missing_customer", "customer": "cus_missing", "status": "paid"}}},
    )
    with pytest.raises(Exception):
        process_stripe_webhook_event(webhook)
    webhook.refresh_from_db()
    assert webhook.processed is False
    assert webhook.processing is False
    assert webhook.error
    assert any(item["step"] == "processing_failed" for item in webhook.processing_log)


def test_billing_models_are_registered_in_admin():
    assert ProviderConfiguration in admin.site._registry
    assert Product in admin.site._registry
    assert Price in admin.site._registry
