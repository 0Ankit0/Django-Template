import hashlib
import hmac
import json
import time
from datetime import datetime
from typing import Any

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import BillingCustomer
from .models import CheckoutSession
from .models import Invoice
from .models import Payment
from .models import Price
from .models import Provider
from .models import Subscription
from .models import WebhookEvent


def _stripe_client() -> stripe.StripeClient:
    if not settings.STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
    return stripe.StripeClient(settings.STRIPE_SECRET_KEY)


def _stripe_dict(resource: Any) -> dict[str, Any]:
    if hasattr(resource, "to_dict_recursive"):
        return resource.to_dict_recursive()
    if isinstance(resource, dict):
        return resource
    return dict(resource)


def _dt(value: Any) -> datetime | None:
    return datetime.fromtimestamp(int(value), tz=timezone.utc) if value else None


def create_stripe_customer(*, tenant, email: str = "", name: str = "") -> dict[str, Any]:
    customer = _stripe_client().v1.customers.create(
        {
            "email": email or None,
            "name": name or None,
            "metadata": {"tenant_id": str(tenant.pk)},
        },
    )
    return _stripe_dict(customer)


def create_portal_session(request) -> str:
    customer = BillingCustomer.objects.get(tenant=request.tenant, provider=Provider.STRIPE)
    session = _stripe_client().v1.billing_portal.sessions.create(
        {
            "customer": customer.provider_customer_id,
            "return_url": request.build_absolute_uri("/billing/"),
        },
    )
    return str(session.url)


def cancel_subscription(subscription: Subscription, at_period_end: bool = True) -> Subscription:
    if subscription.provider != Provider.STRIPE:
        raise ValueError("This subscription is not managed by Stripe.")
    response = _stripe_client().v1.subscriptions.update(
        subscription.provider_subscription_id,
        {"cancel_at_period_end": at_period_end},
    )
    return sync_subscription(_stripe_dict(response))


def change_subscription(subscription: Subscription, price: Price) -> Subscription:
    if subscription.provider != Provider.STRIPE:
        raise ValueError("This subscription is not managed by Stripe.")
    stripe_subscription = _stripe_client().v1.subscriptions.retrieve(subscription.provider_subscription_id)
    items = stripe_subscription.items.data
    if not items:
        raise ValueError("Stripe subscription has no subscription items.")
    response = _stripe_client().v1.subscriptions.update(
        subscription.provider_subscription_id,
        {"items": [{"id": items[0].id, "price": price.stripe_price_id}]},
    )
    return sync_subscription(_stripe_dict(response))


def sync_subscription(data: dict[str, Any]) -> Subscription:
    customer_id = str(data.get("customer") or "")
    customer = BillingCustomer.objects.select_related("tenant").get(
        provider=Provider.STRIPE,
        provider_customer_id=customer_id,
    )
    items = data.get("items", {}).get("data", [])
    if not items:
        raise ValueError("Stripe subscription has no price item.")
    price = Price.objects.filter(stripe_price_id=str(items[0].get("price", {}).get("id", ""))).first()
    if not price:
        raise ValueError("No local billing price for the Stripe price.")
    subscription, _ = Subscription.objects.get_or_create(
        provider=Provider.STRIPE,
        provider_subscription_id=data["id"],
        defaults={
            "tenant": customer.tenant,
            "price": price,
            "status": data.get("status", Subscription.Status.INCOMPLETE),
            "provider_customer_id": customer_id,
        },
    )
    subscription.tenant = customer.tenant
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
    customer = BillingCustomer.objects.select_related("tenant").get(
        provider=Provider.STRIPE,
        provider_customer_id=customer_id,
    )
    subscription = Subscription.objects.filter(
        provider=Provider.STRIPE,
        provider_subscription_id=data.get("subscription", ""),
    ).first()
    invoice, _ = Invoice.objects.get_or_create(
        provider=Provider.STRIPE,
        provider_invoice_id=data["id"],
        defaults={
            "tenant": customer.tenant,
            "subscription": subscription,
            "status": data.get("status") or "draft",
        },
    )
    invoice.tenant = customer.tenant
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
        session = CheckoutSession.objects.filter(
            provider=Provider.STRIPE,
            provider_session_id=data.get("id", ""),
        ).first()
        if session:
            session.status = data.get("status", "complete")
            session.completed_at = timezone.now()
            session.metadata = data.get("metadata") or session.metadata
            session.save(update_fields=["status", "completed_at", "metadata"])
    elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        sync_subscription(data)
    elif event_type == "customer.subscription.deleted":
        subscription = Subscription.objects.filter(
            provider=Provider.STRIPE,
            provider_subscription_id=data.get("id", ""),
        ).first()
        if subscription:
            subscription.status = Subscription.Status.CANCELED
            subscription.cancel_at_period_end = False
            subscription.canceled_at = timezone.now()
            subscription.save(update_fields=["status", "cancel_at_period_end", "canceled_at", "updated_at"])
    elif event_type.startswith("invoice."):
        invoice = sync_invoice(data)
        if event_type == "invoice.paid" and data.get("payment_intent"):
            Payment.objects.update_or_create(
                provider=Provider.STRIPE,
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
        customer = BillingCustomer.objects.filter(
            provider=Provider.STRIPE,
            provider_customer_id=customer_id,
        ).first()
        if customer:
            subscription = Subscription.objects.filter(
                provider=Provider.STRIPE,
                provider_customer_id=customer_id,
                status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING],
            ).first()
            Payment.objects.update_or_create(
                provider=Provider.STRIPE,
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
        payment = Payment.objects.filter(
            provider=Provider.STRIPE,
            provider_payment_id=str(data.get("payment_intent") or ""),
        ).first()
        if payment:
            payment.status = Payment.Status.REFUNDED if data.get("refunded") else Payment.Status.PARTIALLY_REFUNDED
            payment.save(update_fields=["status", "updated_at"])


def handle_webhook(payload: bytes, signature: str) -> WebhookEvent:
    if not settings.STRIPE_WEBHOOK_SECRET or not signature:
        raise ValueError("Stripe webhook secret/signature is not configured.")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise ValueError("Invalid Stripe webhook signature or payload.") from exc
    event_data = _stripe_dict(event)
    with transaction.atomic():
        webhook, created = WebhookEvent.objects.get_or_create(
            provider=Provider.STRIPE,
            event_id=event_data["id"],
            defaults={
                "event_type": event_data["type"],
                "payload": event_data,
            },
        )
        if not created and webhook.processed:
            return webhook
        process_webhook(event_data)
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
            status__in=[
                Subscription.Status.ACTIVE,
                Subscription.Status.TRIALING,
                Subscription.Status.PAST_DUE,
            ],
        )
        .order_by("-created_at")
        .first()
    )


def has_feature(tenant, feature_key: str) -> bool:
    subscription = get_current_subscription(tenant)
    return bool(
        subscription
        and subscription.price.product.product_features.filter(
            feature__key=feature_key,
            feature__active=True,
            enabled=True,
        ).exists()
    )
