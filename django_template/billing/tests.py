import base64
import hashlib
import hmac
import json
import time
from types import SimpleNamespace

import pytest
from django.contrib import admin
from django.test import override_settings

from .models import Feature
from .models import Price
from .models import Product
from .models import ProductFeature
from .models import Provider
from .models import ProviderConfiguration
from .providers import create_esewa_checkout
from .providers import create_khalti_checkout
from .providers import verify_esewa_response
from .services import verify_webhook_signature


@pytest.mark.django_db
def test_price_amount_is_smallest_currency_unit():
    product = Product.objects.create(name="Pro", slug="pro")
    price = Price.objects.create(product=product, amount=2999, currency="usd")

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
    assert set(ProviderConfiguration.objects.values_list("provider", flat=True)) == {
        Provider.STRIPE,
        Provider.KHALTI,
        Provider.ESEWA,
    }


def test_stripe_signature_verification():
    payload = json.dumps({"id": "evt_test", "type": "test"}).encode()
    secret = "whsec_test"
    timestamp = int(time.time())
    signed = f"{timestamp}.{payload.decode()}".encode()
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()

    with override_settings(STRIPE_WEBHOOK_SECRET=secret):
        assert verify_webhook_signature(payload, f"t={timestamp},v1={digest}") is True
        assert verify_webhook_signature(payload, f"t={timestamp},v1=bad") is False
        assert verify_webhook_signature(payload, f"t={timestamp - 301},v1={digest}") is False


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
    digest = hmac.new(b"test-secret", message.encode(), hashlib.sha256).digest()
    data["signature"] = base64.b64encode(digest).decode()

    with override_settings(ESEWA_SECRET_KEY="test-secret"):
        assert verify_esewa_response(base64.b64encode(json.dumps(data).encode()).decode())["status"] == "COMPLETE"
        data["total_amount"] = "999.00"
        with pytest.raises(ValueError, match="Invalid eSewa response signature"):
            verify_esewa_response(base64.b64encode(json.dumps(data).encode()).decode())


def test_khalti_checkout_requires_npr_and_one_time_price(monkeypatch):
    product = SimpleNamespace(name="Pro")
    request = SimpleNamespace(
        tenant=SimpleNamespace(pk=1),
        user=SimpleNamespace(name="Test User", email="test@example.com", phone="9800000000"),
        build_absolute_uri=lambda path: f"https://tenant.example{path}",
    )
    price = SimpleNamespace(currency="npr", is_recurring=False, amount=10000, product=product)
    monkeypatch.setattr(
        "django_template.billing.providers._json_request",
        lambda *args, **kwargs: {"pidx": "pidx-test", "payment_url": "https://pay.test/khalti"},
    )

    with override_settings(KHALTI_SECRET_KEY="test-key", KHALTI_ENVIRONMENT="sandbox"):
        result = create_khalti_checkout(request, price)

    assert result.provider == Provider.KHALTI
    assert result.reference == "pidx-test"
    assert result.redirect_url == "https://pay.test/khalti"


def test_khalti_checkout_rejects_recurring_price():
    request = SimpleNamespace(tenant=SimpleNamespace(pk=1), build_absolute_uri=lambda path: f"https://tenant.example{path}")
    price = SimpleNamespace(currency="npr", is_recurring=True, amount=10000, product=SimpleNamespace(name="Pro"))

    with pytest.raises(ValueError, match="one-time checkout"):
        create_khalti_checkout(request, price)


def test_esewa_checkout_builds_signed_uat_form():
    request = SimpleNamespace(
        tenant=SimpleNamespace(pk=1),
        build_absolute_uri=lambda path: f"https://tenant.example{path}",
    )
    price = SimpleNamespace(currency="npr", is_recurring=False, amount=10000, product=SimpleNamespace(name="Pro"))

    with override_settings(ESEWA_SECRET_KEY="test-secret", ESEWA_PRODUCT_CODE="EPAYTEST", ESEWA_ENVIRONMENT="sandbox"):
        result = create_esewa_checkout(request, price)

    assert result.provider == Provider.ESEWA
    assert result.form_action.endswith("/api/epay/main/v2/form")
    assert result.form_fields["product_code"] == "EPAYTEST"
    assert result.form_fields["total_amount"] == "100.00"
    assert result.form_fields["signed_field_names"] == "total_amount,transaction_uuid,product_code"
    message = (
        f"total_amount={result.form_fields['total_amount']},"
        f"transaction_uuid={result.form_fields['transaction_uuid']},"
        f"product_code={result.form_fields['product_code']}"
    )
    expected = base64.b64encode(hmac.new(b"test-secret", message.encode(), hashlib.sha256).digest()).decode()
    assert result.form_fields["signature"] == expected


def test_billing_models_are_registered_in_admin():
    assert ProviderConfiguration in admin.site._registry
    assert Product in admin.site._registry
    assert Price in admin.site._registry
    assert Feature in admin.site._registry
