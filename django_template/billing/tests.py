import hashlib
import hmac
import json
import time

import pytest
from django.test import override_settings

from .models import Feature
from .models import Price
from .models import Product
from .services import has_feature
from .services import verify_webhook_signature


@pytest.mark.django_db
def test_price_amount_is_smallest_currency_unit():
    product = Product.objects.create(name="Pro", slug="pro")
    price = Price.objects.create(product=product, amount=2999, currency="usd")

    assert price.amount_decimal == 29.99
    assert str(price) == "Pro - 29.99 USD / month"


@pytest.mark.django_db
def test_feature_is_available_only_when_subscription_is_active(tenant):
    product = Product.objects.create(name="Pro", slug="pro")
    price = Price.objects.create(product=product, amount=2900)
    feature = Feature.objects.create(key="api", name="API")
    product.product_features.create(feature=feature)

    assert has_feature(tenant, "api") is False


def test_stripe_signature_verification():
    payload = json.dumps({"id": "evt_test", "type": "test"}).encode()
    secret = "whsec_test"
    timestamp = int(time.time())
    signed = f"{timestamp}.{payload.decode()}".encode()
    digest = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()

    with override_settings(STRIPE_WEBHOOK_SECRET=secret):
        assert verify_webhook_signature(payload, f"t={timestamp},v1={digest}") is True
        assert verify_webhook_signature(payload, f"t={timestamp},v1=bad") is False
