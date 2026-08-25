from __future__ import annotations

import calendar
from datetime import datetime
from datetime import timedelta
from typing import Any

import stripe
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import BillingCustomer
from .models import CheckoutSession
from .models import Entitlement
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


def _stripe_request(path: str, data: dict[str, Any] | None = None, method: str = "POST") -> dict[str, Any]:
    if method != "POST":
        raise NotImplementedError("The Stripe SDK integration does not use generic HTTP requests.")
    payload = data or {}
    client = _stripe_client()
    if path == "/products":
        return _stripe_dict(client.v1.products.create(payload))
    if path == "/prices":
        return _stripe_dict(client.v1.prices.create(payload))
    raise NotImplementedError(f"Unsupported Stripe endpoint: {path}")


def _dt(value: Any) -> datetime | None:
    return datetime.fromtimestamp(int(value), tz=timezone.utc) if value else None


def _add_interval(start: datetime, interval: str, count: int) -> datetime:
    if interval == Price.Interval.DAY:
        return start + timedelta(days=count)
    if interval == Price.Interval.WEEK:
        return start + timedelta(weeks=count)
    if interval == Price.Interval.YEAR:
        month = start.month
        year = start.year + count
        day = min(start.day, calendar.monthrange(year, month)[1])
        return start.replace(year=year, day=day)
    if interval == Price.Interval.MONTH:
        month_index = start.month - 1 + count
        year, month_index = divmod(month_index, 12)
        month = month_index + 1
        day = min(start.day, calendar.monthrange(start.year + year, month)[1])
        return start.replace(year=start.year + year, month=month, day=day)
    raise ValueError(f"Unsupported entitlement interval: {interval}")


def create_stripe_customer(*, tenant, email: str = "", name: str = "") -> dict[str, Any]:
    customer = _stripe_client().v1.customers.create({"email": email or None, "name": name or None, "metadata": {"tenant_id": str(tenant.pk)}})
    return _stripe_dict(customer)


def create_portal_session(request) -> str:
    customer = BillingCustomer.objects.get(tenant=request.tenant, provider=Provider.STRIPE)
    session = _stripe_client().v1.billing_portal.sessions.create({"customer": customer.provider_customer_id, "return_url": request.build_absolute_uri("/billing/")})
    return str(session.url)


def cancel_subscription(subscription: Subscription, at_period_end: bool = True) -> Subscription:
    if subscription.provider != Provider.STRIPE:
        raise ValueError("This subscription is not managed by Stripe.")
    response = _stripe_client().v1.subscriptions.update(subscription.provider_subscription_id, {"cancel_at_period_end": at_period_end})
    return sync_subscription(_stripe_dict(response))


def change_subscription(subscription: Subscription, price: Price) -> Subscription:
    if subscription.provider != Provider.STRIPE:
        raise ValueError("This subscription is not managed by Stripe.")
    stripe_subscription = _stripe_client().v1.subscriptions.retrieve(subscription.provider_subscription_id)
    items = stripe_subscription.items.data
    if not items:
        raise ValueError("Stripe subscription has no subscription items.")
    response = _stripe_client().v1.subscriptions.update(subscription.provider_subscription_id, {"items": [{"id": items[0].id, "price": price.stripe_price_id}]})
    return sync_subscription(_stripe_dict(response))


def sync_subscription(data: dict[str, Any]) -> Subscription:
    customer_id = str(data.get("customer") or "")
    customer = BillingCustomer.objects.select_related("tenant").get(provider=Provider.STRIPE, provider_customer_id=customer_id)
    items = data.get("items", {}).get("data", [])
    if not items:
        raise ValueError("Stripe subscription has no price item.")
    price = Price.objects.filter(stripe_price_id=str(items[0].get("price", {}).get("id", ""))).first()
    if not price:
        raise ValueError("No local billing price for the Stripe price.")
    subscription, _ = Subscription.objects.get_or_create(
        provider=Provider.STRIPE,
        provider_subscription_id=data["id"],
        defaults={"tenant": customer.tenant, "price": price, "status": data.get("status", Subscription.Status.INCOMPLETE), "provider_customer_id": customer_id},
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
    customer = BillingCustomer.objects.select_related("tenant").get(provider=Provider.STRIPE, provider_customer_id=customer_id)
    subscription = Subscription.objects.filter(provider=Provider.STRIPE, provider_subscription_id=data.get("subscription", "")).first()
    invoice, _ = Invoice.objects.get_or_create(provider=Provider.STRIPE, provider_invoice_id=data["id"], defaults={"tenant": customer.tenant, "subscription": subscription, "status": data.get("status") or "draft"})
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


def _price_from_event(data: dict[str, Any], *, session_id: str = "") -> Price | None:
    metadata = data.get("metadata") or {}
    price_id = metadata.get("price_id")
    if price_id:
        price = Price.objects.filter(pk=price_id).first()
        if price:
            return price
    if session_id:
        return CheckoutSession.objects.filter(provider=Provider.STRIPE, provider_session_id=session_id).values_list("price", flat=True).first() and Price.objects.filter(pk=CheckoutSession.objects.get(provider=Provider.STRIPE, provider_session_id=session_id).price_id).first()
    return None


def sync_payment_intent(data: dict[str, Any]) -> Payment | None:
    payment_id = str(data.get("id") or "")
    if not payment_id:
        return None
    customer_id = str(data.get("customer") or "")
    customer = BillingCustomer.objects.filter(provider=Provider.STRIPE, provider_customer_id=customer_id).select_related("tenant").first()
    session = CheckoutSession.objects.filter(provider=Provider.STRIPE, metadata__payment_intent=payment_id).first()
    if not customer and session:
        customer = BillingCustomer.objects.filter(tenant=session.tenant, provider=Provider.STRIPE).first()
    if not customer:
        return None
    subscription = Subscription.objects.filter(provider=Provider.STRIPE, provider_customer_id=customer_id).order_by("-created_at").first()
    payment, _ = Payment.objects.get_or_create(
        provider=Provider.STRIPE,
        provider_payment_id=payment_id,
        defaults={"tenant": customer.tenant, "amount": int(data.get("amount_received") or data.get("amount") or 0), "currency": data.get("currency") or "usd", "status": Payment.Status.PENDING},
    )
    payment.tenant = customer.tenant
    payment.subscription = subscription
    payment.amount = int(data.get("amount_received") or data.get("amount") or payment.amount)
    payment.currency = data.get("currency") or payment.currency
    payment.status = Payment.Status.SUCCEEDED if data.get("status") == "succeeded" else Payment.Status.FAILED if data.get("status") in {"requires_payment_method", "canceled"} else Payment.Status.PENDING
    payment.paid_at = timezone.now() if payment.status == Payment.Status.SUCCEEDED and not payment.paid_at else payment.paid_at
    payment.metadata = data.get("metadata") or payment.metadata
    payment.save()
    return payment


def grant_expiring_entitlement(payment: Payment, price: Price) -> Entitlement:
    if not price.is_expiring_purchase:
        raise ValueError("Only expiring prices can create expiring entitlements.")
    existing = Entitlement.objects.filter(provider=Provider.STRIPE, provider_reference=payment.provider_payment_id).first()
    if existing:
        return existing
    starts_at = payment.paid_at or timezone.now()
    return Entitlement.objects.create(
        tenant=payment.tenant,
        price=price,
        provider=Provider.STRIPE,
        provider_reference=payment.provider_payment_id,
        starts_at=starts_at,
        expires_at=_add_interval(starts_at, price.interval, price.interval_count),
        metadata={"payment_id": payment.provider_payment_id},
    )


def process_webhook_event(webhook: WebhookEvent) -> None:
    with transaction.atomic():
        locked = WebhookEvent.objects.select_for_update().get(pk=webhook.pk)
        if locked.processed or locked.processing:
            return
        locked.processing = True
        locked.save(update_fields=["processing"])
    try:
        process_webhook(locked.payload)
    except Exception as exc:
        WebhookEvent.objects.filter(pk=locked.pk).update(processing=False, error=str(exc))
        raise
    WebhookEvent.objects.filter(pk=locked.pk).update(processing=False, processed=True, processed_at=timezone.now(), error="")


def process_webhook(event: dict[str, Any]) -> None:
    event_type = event["type"]
    data = event.get("data", {}).get("object", {})
    if event_type == "checkout.session.completed":
        session = CheckoutSession.objects.filter(provider=Provider.STRIPE, provider_session_id=data.get("id", "")).first()
        if session:
            session.status = data.get("status", "complete")
            session.completed_at = timezone.now()
            session.metadata = {**session.metadata, **(data.get("metadata") or {})}
            if data.get("payment_intent"):
                session.metadata["payment_intent"] = str(data["payment_intent"])
            session.save(update_fields=["status", "completed_at", "metadata"])
            if data.get("payment_status") == "paid" and data.get("payment_intent"):
                payment = sync_payment_intent({"id": str(data["payment_intent"]), "customer": data.get("customer"), "amount": data.get("amount_total"), "currency": data.get("currency"), "status": "succeeded", "metadata": session.metadata})
                if payment and session.price.is_expiring_purchase:
                    grant_expiring_entitlement(payment, session.price)
    elif event_type in {"checkout.session.async_payment_succeeded"}:
        if data.get("payment_intent"):
            payment = sync_payment_intent({"id": str(data["payment_intent"]), "customer": data.get("customer"), "amount": data.get("amount_total"), "currency": data.get("currency"), "status": "succeeded", "metadata": data.get("metadata") or {}})
            session = CheckoutSession.objects.filter(provider=Provider.STRIPE, provider_session_id=data.get("id", "")).first()
            if payment and session and session.price.is_expiring_purchase:
                grant_expiring_entitlement(payment, session.price)
    elif event_type == "checkout.session.async_payment_failed":
        session = CheckoutSession.objects.filter(provider=Provider.STRIPE, provider_session_id=data.get("id", "")).first()
        if session:
            session.status = "expired"
            session.save(update_fields=["status"])
    elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.paused", "customer.subscription.resumed"}:
        sync_subscription(data)
    elif event_type == "customer.subscription.deleted":
        subscription = Subscription.objects.filter(provider=Provider.STRIPE, provider_subscription_id=data.get("id", "")).first()
        if subscription:
            subscription.status = Subscription.Status.CANCELED
            subscription.cancel_at_period_end = False
            subscription.canceled_at = _dt(data.get("canceled_at")) or timezone.now()
            subscription.save(update_fields=["status", "cancel_at_period_end", "canceled_at", "updated_at"])
    elif event_type.startswith("invoice."):
        invoice = sync_invoice(data)
        if event_type == "invoice.paid" and data.get("payment_intent"):
            Payment.objects.update_or_create(provider=Provider.STRIPE, provider_payment_id=str(data["payment_intent"]), defaults={"tenant": invoice.tenant, "subscription": invoice.subscription, "amount": int(data.get("amount_paid") or 0), "currency": data.get("currency") or "usd", "status": Payment.Status.SUCCEEDED, "provider_invoice_id": data["id"], "paid_at": timezone.now()})
        elif event_type == "invoice.payment_failed" and data.get("payment_intent"):
            Payment.objects.update_or_create(provider=Provider.STRIPE, provider_payment_id=str(data["payment_intent"]), defaults={"tenant": invoice.tenant, "subscription": invoice.subscription, "amount": int(data.get("amount_due") or 0), "currency": data.get("currency") or "usd", "status": Payment.Status.FAILED, "provider_invoice_id": data["id"]})
    elif event_type in {"payment_intent.succeeded", "payment_intent.payment_failed", "payment_intent.canceled"}:
        payment = sync_payment_intent(data)
        if payment and payment.status == Payment.Status.SUCCEEDED:
            price = _price_from_event(data)
            if price:
                grant_expiring_entitlement(payment, price) if price.is_expiring_purchase else None
    elif event_type in {"charge.refunded", "charge.refund.updated"}:
        payment = Payment.objects.filter(provider=Provider.STRIPE, provider_payment_id=str(data.get("payment_intent") or "")).first()
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
            defaults={"event_type": event_data["type"], "payload": event_data},
        )
        if created:
            transaction.on_commit(lambda event_pk=webhook.pk: _enqueue_stripe_webhook(event_pk))
        return webhook


def _enqueue_stripe_webhook(webhook_event_id: int) -> None:
    from .tasks import process_stripe_webhook

    process_stripe_webhook.delay(webhook_event_id)


def get_current_subscription(tenant) -> Subscription | None:
    return Subscription.objects.select_related("price__product").filter(tenant=tenant, status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING, Subscription.Status.PAST_DUE]).order_by("-created_at").first()


def get_active_entitlement(tenant, feature_key: str | None = None) -> Entitlement | None:
    now = timezone.now()
    query = Entitlement.objects.select_related("price__product").filter(tenant=tenant, active=True, starts_at__lte=now, expires_at__gt=now)
    if feature_key:
        query = query.filter(price__product__product_features__feature__key=feature_key, price__product__product_features__feature__active=True, price__product__product_features__enabled=True)
    return query.order_by("-expires_at").first()


def has_feature(tenant, feature_key: str) -> bool:
    if get_current_subscription(tenant):
        if Subscription.objects.filter(tenant=tenant, status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING, Subscription.Status.PAST_DUE], price__product__product_features__feature__key=feature_key, price__product__product_features__feature__active=True, price__product__product_features__enabled=True).exists():
            return True
    return get_active_entitlement(tenant, feature_key) is not None
