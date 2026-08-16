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
from .models import Subscription
from .models import WebhookEvent

STRIPE_API_BASE = "https://api.stripe.com/v1"


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


def _stripe_request(path: str, data: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
    secret = settings.STRIPE_SECRET_KEY
    if not secret:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
    request = Request(
        f"{STRIPE_API_BASE}{path}",
        data=urlencode(_flatten(data or {}), doseq=True).encode() if method != "GET" else None,
        method=method,
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "django-template-billing/1.0",
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _dt(value: Any) -> datetime | None:
    return datetime.fromtimestamp(int(value), tz=timezone.utc) if value else None


def create_portal_session(request) -> str:
    customer = BillingCustomer.objects.get(tenant=request.tenant)
    session = _stripe_request(
        "/billing_portal/sessions",
        {"customer": customer.provider_customer_id, "return_url": request.build_absolute_uri("/billing/")},
    )
    return str(session["url"])


def cancel_subscription(subscription: Subscription, at_period_end: bool = True) -> Subscription:
    response = _stripe_request(
        f"/subscriptions/{subscription.provider_subscription_id}",
        {"cancel_at_period_end": at_period_end},
    )
    return sync_subscription(response)


def change_subscription(subscription: Subscription, price: Price) -> Subscription:
    item_id = _subscription_item_id(subscription)
    response = _stripe_request(
        f"/subscriptions/{subscription.provider_subscription_id}",
        {"items": [{"id": item_id, "price": price.provider_price_id}]},
    )
    return sync_subscription(response)


def _subscription_item_id(subscription: Subscription) -> str:
    response = _stripe_request(f"/subscriptions/{subscription.provider_subscription_id}", method="GET")
    items = response.get("items", {}).get("data", [])
    if not items:
        raise ValueError("Stripe subscription has no subscription items.")
    return str(items[0]["id"])


def sync_subscription(data: dict[str, Any]) -> Subscription:
    customer_id = str(data.get("customer") or "")
    billing_customer = BillingCustomer.objects.select_related("tenant").get(provider_customer_id=customer_id)
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
            "tenant": billing_customer.tenant,
            "price": price,
            "status": data.get("status", Subscription.Status.INCOMPLETE),
            "provider_customer_id": customer_id,
        },
    )
    subscription.tenant = billing_customer.tenant
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
    if data.get("status") == "paid":
        invoice.paid_at = invoice.paid_at or timezone.now()
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
    elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        sync_subscription(data)
    elif event_type == "customer.subscription.deleted":
        subscription = Subscription.objects.filter(provider_subscription_id=data.get("id", "")).first()
        if subscription:
            subscription.status = Subscription.Status.CANCELED
            subscription.cancel_at_period_end = False
            subscription.canceled_at = timezone.now()
            subscription.save(update_fields=["status", "cancel_at_period_end", "canceled_at", "updated_at"])
    elif event_type.startswith("invoice."):
        invoice = sync_invoice(data)
        if event_type == "invoice.paid" and data.get("payment_intent"):
            Payment.objects.update_or_create(
                provider_payment_id=str(data["payment_intent"]),
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
    elif event_type in {"payment_intent.succeeded", "payment_intent.payment_failed"}:
        customer_id = str(data.get("customer") or "")
        customer = BillingCustomer.objects.filter(provider_customer_id=customer_id).first()
        if customer:
            subscription = Subscription.objects.filter(
                provider_customer_id=customer_id,
                status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING],
            ).first()
            Payment.objects.update_or_create(
                provider_payment_id=data["id"],
                defaults={
                    "tenant": customer.tenant,
                    "subscription": subscription,
                    "amount": int(data.get("amount_received") or data.get("amount") or 0),
                    "currency": data.get("currency") or "usd",
                    "status": Payment.Status.SUCCEEDED if event_type.endswith("succeeded") else Payment.Status.FAILED,
                    "paid_at": timezone.now() if event_type.endswith("succeeded") else None,
                    "metadata": data.get("metadata") or {},
                },
            )
    elif event_type == "charge.refunded":
        payment = Payment.objects.filter(provider_payment_id=str(data.get("payment_intent") or "")).first()
        if payment:
            payment.status = Payment.Status.REFUNDED if data.get("refunded") else Payment.Status.PARTIALLY_REFUNDED
            payment.save(update_fields=["status", "updated_at"])


def verify_webhook_signature(payload: bytes, signature: str, tolerance: int = 300) -> bool:
    secret = settings.STRIPE_WEBHOOK_SECRET
    if not secret or not signature:
        return False
    timestamp: int | None = None
    signatures: list[str] = []
    for part in signature.split(","):
        key, _, value = part.partition("=")
        if key == "t":
            try:
                timestamp = int(value)
            except ValueError:
                return False
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
            defaults={"event_type": event["type"], "payload": event},
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
        .filter(
            tenant=tenant,
            status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING, Subscription.Status.PAST_DUE],
        )
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
