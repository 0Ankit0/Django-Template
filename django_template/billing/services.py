import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request
from urllib.request import urlopen

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import BillingCustomer
from .models import CheckoutSession
from .models import Invoice
from .models import Payment
from .models import Price
from .models import Product
from .models import Subscription
from .models import WebhookEvent


STRIPE_API_BASE = "https://api.stripe.com/v1"


def _stripe_request(path: str, data: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
    secret = settings.STRIPE_SECRET_KEY
    if not secret:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")

    encoded = urlencode(_flatten(data or {}), doseq=True).encode()
    request = Request(
        f"{STRIPE_API_BASE}{path}",
        data=encoded if method != "GET" else None,
        method=method,
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "django-template-billing/1.0",
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _flatten(data: dict[str, Any], prefix: str = "") -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for key, value in data.items():
        name = f"{prefix}[{key}]" if prefix else key
        if isinstance(value, dict):
            result.extend(_flatten(value, name))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, dict):
                    result.extend(_flatten(item, f"{name}[{index}]"))
                else:
                    result.append((f"{name}[{index}]", str(item)))
        elif value is not None:
            result.append((name, str(value).lower() if isinstance(value, bool) else str(value)))
    return result


def _dt(value: Any) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc)


def create_or_get_customer(tenant, email: str = "", name: str = "") -> BillingCustomer:
    customer, created = BillingCustomer.objects.get_or_create(
        tenant=tenant,
        defaults={"provider_customer_id": "", "email": email, "name": name},
    )
    if customer.provider_customer_id:
        changed = False
        if email and customer.email != email:
            customer.email = email
            changed = True
        if name and customer.name != name:
            customer.name = name
            changed = True
        if changed:
            customer.save(update_fields=["email", "name", "updated_at"])
        return customer

    stripe_customer = _stripe_request(
        "/customers",
        {
            "email": email,
            "name": name,
            "metadata": {"tenant_id": str(tenant.pk)},
        },
    )
    customer.provider_customer_id = stripe_customer["id"]
    customer.email = email
    customer.name = name
    customer.save(update_fields=["provider_customer_id", "email", "name", "updated_at"])
    return customer


def create_checkout_session(request, price: Price) -> CheckoutSession:
    tenant = request.tenant
    customer = create_or_get_customer(
        tenant,
        email=getattr(request.user, "email", ""),
        name=getattr(request.user, "name", "") or str(request.user),
    )

    mode = "subscription" if price.is_recurring else "payment"
    success_url = request.build_absolute_uri("/billing/success/") + "?session_id={CHECKOUT_SESSION_ID}"
    cancel_url = request.build_absolute_uri("/billing/pricing/")

    stripe_session = _stripe_request(
        "/checkout/sessions",
        {
            "mode": mode,
            "customer": customer.provider_customer_id,
            "line_items": [{"price": price.provider_price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "client_reference_id": str(tenant.pk),
            "metadata": {
                "tenant_id": str(tenant.pk),
                "price_id": str(price.pk),
            },
            "subscription_data": {
                "metadata": {
                    "tenant_id": str(tenant.pk),
                    "price_id": str(price.pk),
                }
            }
            if price.is_recurring
            else None,
        },
    )

    return CheckoutSession.objects.create(
        tenant=tenant,
        price=price,
        provider_session_id=stripe_session["id"],
        mode=mode,
        status=stripe_session.get("status", "open"),
        url=stripe_session.get("url", ""),
        metadata=stripe_session.get("metadata") or {},
    )


def create_portal_session(request) -> str:
    customer = BillingCustomer.objects.get(tenant=request.tenant)
    session = _stripe_request(
        "/billing_portal/sessions",
        {
            "customer": customer.provider_customer_id,
            "return_url": request.build_absolute_uri("/billing/") if request.path != "/billing/" else request.build_absolute_uri(),
        },
    )
    return str(session["url"])


def cancel_subscription(subscription: Subscription, at_period_end: bool = True) -> Subscription:
    response = _stripe_request(
        f"/subscriptions/{subscription.provider_subscription_id}",
        {"cancel_at_period_end": at_period_end},
    )
    return sync_subscription(response)


def change_subscription(subscription: Subscription, price: Price) -> Subscription:
    response = _stripe_request(
        f"/subscriptions/{subscription.provider_subscription_id}",
        {"items": [{"id": _subscription_item_id(subscription), "price": price.provider_price_id}]},
    )
    return sync_subscription(response)


def _subscription_item_id(subscription: Subscription) -> str:
    response = _stripe_request(f"/subscriptions/{subscription.provider_subscription_id}", method="GET")
    items = response.get("items", {}).get("data", [])
    if not items:
        raise ValueError("Stripe subscription has no subscription items.")
    return str(items[0]["id"])


def sync_product(data: dict[str, Any]) -> Product:
    product, _ = Product.objects.get_or_create(
        provider_product_id=data["id"],
        defaults={
            "name": data.get("name", data["id"]),
            "slug": data["id"],
        },
    )
    product.name = data.get("name") or product.name
    product.description = data.get("description") or ""
    product.active = bool(data.get("active", True))
    product.metadata = data.get("metadata") or {}
    product.save(update_fields=["name", "description", "active", "metadata", "updated_at"])
    return product


def sync_price(data: dict[str, Any]) -> Price | None:
    product_id = data.get("product")
    product = Product.objects.filter(provider_product_id=product_id).first()
    if not product:
        return None
    recurring = data.get("recurring") or {}
    interval = recurring.get("interval") or Price.Interval.ONE_TIME
    price, _ = Price.objects.get_or_create(
        provider_price_id=data["id"],
        defaults={
            "product": product,
            "amount": int(data.get("unit_amount") or 0),
            "currency": data.get("currency", "usd"),
            "interval": interval,
            "interval_count": int(recurring.get("interval_count") or 1),
        },
    )
    price.product = product
    price.amount = int(data.get("unit_amount") or 0)
    price.currency = data.get("currency", price.currency)
    price.interval = interval
    price.interval_count = int(recurring.get("interval_count") or 1)
    price.active = bool(data.get("active", True))
    price.metadata = data.get("metadata") or {}
    price.save()
    return price


def sync_subscription(data: dict[str, Any]) -> Subscription:
    customer_id = str(data.get("customer") or "")
    billing_customer = BillingCustomer.objects.select_related("tenant").get(provider_customer_id=customer_id)
    tenant = billing_customer.tenant
    items = data.get("items", {}).get("data", [])
    if not items:
        raise ValueError("Stripe subscription has no price item.")
    stripe_price_id = str(items[0].get("price", {}).get("id", ""))
    price = Price.objects.filter(provider_price_id=stripe_price_id).first()
    if not price:
        raise ValueError(f"No local billing price for Stripe price {stripe_price_id}.")

    subscription, _ = Subscription.objects.get_or_create(
        provider_subscription_id=data["id"],
        defaults={
            "tenant": tenant,
            "price": price,
            "status": data.get("status", Subscription.Status.INCOMPLETE),
            "provider_customer_id": customer_id,
        },
    )
    subscription.tenant = tenant
    subscription.price = price
    subscription.status = data.get("status", subscription.status)
    subscription.provider_customer_id = customer_id
    subscription.current_period_start = _dt(data.get("current_period_start"))
    subscription.current_period_end = _dt(data.get("current_period_end"))
    subscription.cancel_at_period_end = bool(data.get("cancel_at_period_end", False))
    subscription.canceled_at = _dt(data.get("canceled_at"))
    subscription.trial_end = _dt(data.get("trial_end"))
    subscription.metadata = data.get("metadata") or {}
    subscription.save()
    return subscription


def sync_invoice(data: dict[str, Any]) -> Invoice:
    customer_id = str(data.get("customer") or "")
    billing_customer = BillingCustomer.objects.select_related("tenant").get(provider_customer_id=customer_id)
    subscription = Subscription.objects.filter(provider_subscription_id=data.get("subscription", "")).first()
    invoice, _ = Invoice.objects.get_or_create(
        provider_invoice_id=data["id"],
        defaults={"tenant": billing_customer.tenant, "subscription": subscription, "status": data.get("status") or "draft"},
    )
    invoice.tenant = billing_customer.tenant
    invoice.subscription = subscription
    invoice.number = data.get("number") or ""
    invoice.status = data.get("status") or invoice.status
    invoice.amount_due = int(data.get("amount_due") or 0)
    invoice.amount_paid = int(data.get("amount_paid") or 0)
    invoice.currency = data.get("currency") or invoice.currency
    invoice.hosted_invoice_url = data.get("hosted_invoice_url") or ""
    invoice.invoice_pdf = data.get("invoice_pdf") or ""
    invoice.period_start = _dt(data.get("period_start"))
    invoice.period_end = _dt(data.get("period_end"))
    invoice.paid_at = timezone.now() if data.get("status") == "paid" else invoice.paid_at
    invoice.metadata = data.get("metadata") or {}
    invoice.save()
    return invoice


def process_webhook(event: dict[str, Any]) -> None:
    event_type = event["type"]
    data = event.get("data", {}).get("object", {})
    if event_type == "checkout.session.completed":
        session = CheckoutSession.objects.filter(provider_session_id=data.get("id", "")).first()
        if session:
            session.status = data.get("status", "complete")
            session.completed_at = timezone.now()
            session.metadata = data.get("metadata") or session.metadata
            session.save(update_fields=["status", "completed_at", "metadata"])
    elif event_type == "customer.subscription.created" or event_type == "customer.subscription.updated":
        sync_subscription(data)
    elif event_type == "customer.subscription.deleted":
        subscription = Subscription.objects.filter(provider_subscription_id=data.get("id", "")).first()
        if subscription:
            subscription.status = Subscription.Status.CANCELED
            subscription.cancel_at_period_end = False
            subscription.canceled_at = timezone.now()
            subscription.save(update_fields=["status", "cancel_at_period_end", "canceled_at", "updated_at"])
    elif event_type.startswith("invoice."):
        sync_invoice(data)
        if event_type == "invoice.paid":
            payment_intent = data.get("payment_intent")
            if payment_intent:
                invoice = Invoice.objects.get(provider_invoice_id=data["id"])
                Payment.objects.update_or_create(
                    provider_payment_id=str(payment_intent),
                    defaults={
                        "tenant": invoice.tenant,
                        "subscription": invoice.subscription,
                        "amount": int(data.get("amount_paid") or 0),
                        "currency": data.get("currency") or "usd",
                        "status": Payment.Status.SUCCEEDED,
                        "provider_invoice_id": data["id"],
                        "paid_at": timezone.now(),
                    },
                )
    elif event_type == "payment_intent.succeeded":
        customer_id = str(data.get("customer") or "")
        customer = BillingCustomer.objects.filter(provider_customer_id=customer_id).first()
        if customer:
            subscription = Subscription.objects.filter(provider_customer_id=customer_id, status__in=["active", "trialing"]).first()
            Payment.objects.update_or_create(
                provider_payment_id=data["id"],
                defaults={
                    "tenant": customer.tenant,
                    "subscription": subscription,
                    "amount": int(data.get("amount_received") or data.get("amount") or 0),
                    "currency": data.get("currency") or "usd",
                    "status": Payment.Status.SUCCEEDED,
                    "paid_at": timezone.now(),
                    "metadata": data.get("metadata") or {},
                },
            )
    elif event_type == "payment_intent.payment_failed":
        customer_id = str(data.get("customer") or "")
        customer = BillingCustomer.objects.filter(provider_customer_id=customer_id).first()
        if customer:
            Payment.objects.update_or_create(
                provider_payment_id=data["id"],
                defaults={
                    "tenant": customer.tenant,
                    "amount": int(data.get("amount") or 0),
                    "currency": data.get("currency") or "usd",
                    "status": Payment.Status.FAILED,
                    "metadata": data.get("metadata") or {},
                },
            )
    elif event_type == "charge.refunded":
        payment_intent = str(data.get("payment_intent") or "")
        payment = Payment.objects.filter(provider_payment_id=payment_intent).first()
        if payment:
            payment.status = Payment.Status.REFUNDED if data.get("refunded") else Payment.Status.PARTIALLY_REFUNDED
            payment.save(update_fields=["status", "updated_at"])


def verify_webhook_signature(payload: bytes, signature: str, tolerance: int = 300) -> bool:
    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    timestamp = None
    signatures: list[str] = []
    for part in signature.split(","):
        key, _, value = part.partition("=")
        if key == "t":
            timestamp = int(value)
        elif key == "v1":
            signatures.append(value)
    if timestamp is None or abs(int(time.time()) - timestamp) > tolerance:
        return False
    signed_payload = f"{timestamp}.{payload.decode('utf-8')}".encode()
    expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, value) for value in signatures)


def handle_webhook(payload: bytes, signature: str) -> WebhookEvent:
    if not verify_webhook_signature(payload, signature):
        raise ValueError("Invalid Stripe webhook signature.")
    event = json.loads(payload.decode("utf-8"))
    with transaction.atomic():
        webhook, created = WebhookEvent.objects.get_or_create(
            event_id=event["id"],
            defaults={
                "event_type": event["type"],
                "payload": event,
            },
        )
        if not created and webhook.processed:
            return webhook
        try:
            process_webhook(event)
        except Exception as exc:
            webhook.error = str(exc)
            webhook.save(update_fields=["error"])
            raise
        webhook.processed = True
        webhook.processed_at = timezone.now()
        webhook.error = ""
        webhook.save(update_fields=["processed", "processed_at", "error"])
        return webhook


def get_current_subscription(tenant) -> Subscription | None:
    return (
        Subscription.objects.select_related("price__product")
        .filter(tenant=tenant, status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING, Subscription.Status.PAST_DUE])
        .order_by("-created_at")
        .first()
    )


def has_feature(tenant, feature_key: str) -> bool:
    subscription = get_current_subscription(tenant)
    if not subscription:
        return False
    return subscription.price.product.product_features.filter(
        feature__key=feature_key,
        feature__active=True,
        enabled=True,
    ).exists()
