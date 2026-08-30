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
    if interval == Price.Interval.MONTH:
        month_index = start.month - 1 + count
        year, month_index = divmod(month_index, 12)
        month = month_index + 1
        day = min(start.day, calendar.monthrange(start.year + year, month)[1])
        return start.replace(year=start.year + year, month=month, day=day)
    if interval == Price.Interval.YEAR:
        year = start.year + count
        day = min(start.day, calendar.monthrange(year, start.month)[1])
        return start.replace(year=year, day=day)
    raise ValueError(f"Unsupported price interval: {interval}")


def create_stripe_customer(*, tenant, email: str = "", name: str = "") -> dict[str, Any]:
    customer = _stripe_client().v1.customers.create({"email": email, "name": name, "metadata": {"tenant_id": str(tenant.pk)}})
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
    response = _stripe_client().v1.subscriptions.update(subscription.provider_subscription_id, {"items": [{"id": items[0].id, "price": price.provider_price_id}]})
    return sync_subscription(_stripe_dict(response))


def sync_subscription(data: dict[str, Any]) -> Subscription:
    customer_id = str(data.get("customer") or "")
    customer = BillingCustomer.objects.select_related("tenant").get(provider=Provider.STRIPE, provider_customer_id=customer_id)
    items = data.get("items", {}).get("data", [])
    if not items:
        raise ValueError("Stripe subscription has no price item.")
    price = Price.objects.filter(provider_price_id=str(items[0].get("price", {}).get("id", ""))).first()
    if not price:
        raise ValueError("No local billing price for the Stripe price.")
    subscription, _ = Subscription.objects.get_or_create(provider=Provider.STRIPE, provider_subscription_id=data["id"], defaults={"tenant": customer.tenant, "price": price, "status": data.get("status", Subscription.Status.INCOMPLETE), "provider_customer_id": customer_id})
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
    metadata = data.get("metadata") or {}
    local_price = Price.objects.filter(pk=metadata.get("price_id")).first() if metadata.get("price_id") else None
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
    invoice.paid_at = invoice.paid_at or (timezone.now() if data.get("status") == "paid" else None)
    invoice.metadata = {**metadata, **({"local_price_id": str(local_price.pk)} if local_price else {})}
    invoice.save()
    return invoice


def _price_from_event(data: dict[str, Any], *, session_id: str = "") -> Price | None:
    metadata = data.get("metadata") or {}
    if metadata.get("price_id"):
        price = Price.objects.filter(pk=metadata["price_id"]).first()
        if price:
            return price
    if session_id:
        session = CheckoutSession.objects.filter(provider=Provider.STRIPE, provider_session_id=session_id).select_related("price").first()
        return session.price if session else None
    return None


def sync_payment_intent(data: dict[str, Any]) -> Payment | None:
    payment_id = str(data.get("id") or "")
    if not payment_id:
        return None
    customer_id = str(data.get("customer") or "")
    metadata = data.get("metadata") or {}
    customer = BillingCustomer.objects.filter(provider=Provider.STRIPE, provider_customer_id=customer_id).select_related("tenant").first()
    session = CheckoutSession.objects.filter(provider=Provider.STRIPE, metadata__payment_intent=payment_id).select_related("tenant", "price").first()
    if not customer and session:
        customer = BillingCustomer.objects.filter(tenant=session.tenant, provider=Provider.STRIPE).first()
    if not customer and metadata.get("tenant_id"):
        customer = BillingCustomer.objects.filter(tenant_id=metadata["tenant_id"], provider=Provider.STRIPE).select_related("tenant").first()
    if not customer:
        return None
    subscription = Subscription.objects.filter(provider=Provider.STRIPE, provider_customer_id=customer_id, status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING, Subscription.Status.PAST_DUE]).order_by("-created_at").first()
    payment, _ = Payment.objects.get_or_create(provider=Provider.STRIPE, provider_payment_id=payment_id, defaults={"tenant": customer.tenant, "amount": int(data.get("amount_received") or data.get("amount") or 0), "currency": data.get("currency") or "usd", "status": Payment.Status.PENDING})
    payment.tenant = customer.tenant
    payment.subscription = subscription
    payment.amount = int(data.get("amount_received") or data.get("amount") or payment.amount)
    payment.currency = data.get("currency") or payment.currency
    payment.status = Payment.Status.SUCCEEDED if data.get("status") == "succeeded" else Payment.Status.FAILED if data.get("status") in {"requires_payment_method", "canceled"} else Payment.Status.PENDING
    if payment.status == Payment.Status.SUCCEEDED and not payment.paid_at:
        payment.paid_at = timezone.now()
    payment.metadata = metadata or payment.metadata
    payment.save()
    return payment


def create_or_update_one_time_subscription(payment: Payment, price: Price, *, provider_reference: str | None = None) -> Subscription:
    if not price.is_one_time:
        raise ValueError("Only one-time prices create an expiring local subscription.")
    reference = provider_reference or payment.provider_payment_id
    starts_at = payment.paid_at or timezone.now()
    expires_at = _add_interval(starts_at, price.interval, 1)
    subscription, _ = Subscription.objects.get_or_create(provider=payment.provider, provider_subscription_id=f"one-time:{reference}", defaults={"tenant": payment.tenant, "price": price, "status": Subscription.Status.ACTIVE})
    subscription.tenant = payment.tenant
    subscription.price = price
    subscription.status = Subscription.Status.ACTIVE if expires_at > timezone.now() else Subscription.Status.CANCELED
    subscription.provider_customer_id = payment.metadata.get("customer_id", "")
    subscription.current_period_start = starts_at
    subscription.current_period_end = expires_at
    subscription.cancel_at_period_end = True
    subscription.canceled_at = expires_at
    subscription.metadata = {**subscription.metadata, "one_time": True, "payment_id": payment.provider_payment_id}
    subscription.save()
    payment.subscription = subscription
    payment.save(update_fields=["subscription", "updated_at"])
    return subscription


def expire_one_time_subscriptions() -> int:
    now = timezone.now()
    return Subscription.objects.filter(cancel_at_period_end=True, current_period_end__lte=now, status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING, Subscription.Status.PAST_DUE]).update(status=Subscription.Status.CANCELED, canceled_at=now, updated_at=now)


def process_webhook_event(webhook: WebhookEvent) -> None:
    with transaction.atomic():
        locked = WebhookEvent.objects.select_for_update().get(pk=webhook.pk)
        if locked.processed or locked.processing:
            return
        locked.processing = True
        locked.save(update_fields=["processing"])
    try:
        with transaction.atomic():
            process_webhook(locked.payload)
    except Exception as exc:
        WebhookEvent.objects.filter(pk=locked.pk).update(processing=False, error=str(exc))
        raise
    WebhookEvent.objects.filter(pk=locked.pk).update(processing=False, processed=True, processed_at=timezone.now(), error="")


def process_webhook(event: dict[str, Any]) -> None:
    event_type = event["type"]
    data = event.get("data", {}).get("object", {})
    if event_type == "checkout.session.completed":
        session = CheckoutSession.objects.filter(provider=Provider.STRIPE, provider_session_id=data.get("id", "")).select_related("price").first()
        if session:
            session.status = data.get("status", "complete")
            session.completed_at = timezone.now()
            session.metadata = {**session.metadata, **(data.get("metadata") or {})}
            if data.get("payment_intent"):
                session.metadata["payment_intent"] = str(data["payment_intent"])
            session.save(update_fields=["status", "completed_at", "metadata"])
            if data.get("payment_intent") and session.mode == CheckoutSession.Mode.PAYMENT and data.get("payment_status") == "paid":
                payment = sync_payment_intent({"id": str(data["payment_intent"]), "customer": data.get("customer"), "amount": data.get("amount_total"), "currency": data.get("currency"), "status": "succeeded", "metadata": session.metadata})
                if payment and session.price.is_one_time:
                    create_or_update_one_time_subscription(payment, session.price)
    elif event_type == "checkout.session.async_payment_succeeded":
        session = CheckoutSession.objects.filter(provider=Provider.STRIPE, provider_session_id=data.get("id", "")).select_related("price").first()
        if session and data.get("payment_intent"):
            payment = sync_payment_intent({"id": str(data["payment_intent"]), "customer": data.get("customer"), "amount": data.get("amount_total"), "currency": data.get("currency"), "status": "succeeded", "metadata": data.get("metadata") or {}})
            if payment and session.price.is_one_time:
                create_or_update_one_time_subscription(payment, session.price)
    elif event_type == "checkout.session.async_payment_failed":
        CheckoutSession.objects.filter(provider=Provider.STRIPE, provider_session_id=data.get("id", "")).update(status="expired")
    elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.paused", "customer.subscription.resumed", "customer.subscription.deleted"}:
        subscription = sync_subscription(data) if event_type != "customer.subscription.deleted" else Subscription.objects.filter(provider=Provider.STRIPE, provider_subscription_id=data.get("id", "")).first()
        if event_type == "customer.subscription.deleted" and subscription:
            subscription.status = Subscription.Status.CANCELED
            subscription.cancel_at_period_end = False
            subscription.canceled_at = _dt(data.get("canceled_at")) or timezone.now()
            subscription.save(update_fields=["status", "cancel_at_period_end", "canceled_at", "updated_at"])
    elif event_type.startswith("invoice."):
        invoice = sync_invoice(data)
        payment_intent = data.get("payment_intent")
        if payment_intent:
            defaults = {"tenant": invoice.tenant, "subscription": invoice.subscription, "amount": int(data.get("amount_paid") or data.get("amount_due") or 0), "currency": data.get("currency") or "usd", "provider_invoice_id": data["id"], "status": Payment.Status.SUCCEEDED if event_type == "invoice.paid" else Payment.Status.FAILED if event_type == "invoice.payment_failed" else Payment.Status.PENDING, "paid_at": timezone.now() if event_type == "invoice.paid" else None}
            Payment.objects.update_or_create(provider=Provider.STRIPE, provider_payment_id=str(payment_intent), defaults=defaults)
    elif event_type in {"payment_intent.succeeded", "payment_intent.payment_failed", "payment_intent.canceled", "payment_intent.processing"}:
        payment = sync_payment_intent(data)
        if payment and payment.status == Payment.Status.SUCCEEDED:
            price = _price_from_event(data)
            if price and price.is_one_time:
                create_or_update_one_time_subscription(payment, price)
    elif event_type in {"charge.refunded", "charge.refund.updated"}:
        payment = Payment.objects.filter(provider=Provider.STRIPE, provider_payment_id=str(data.get("payment_intent") or "")).first()
        if payment:
            payment.status = Payment.Status.REFUNDED if data.get("refunded") or data.get("status") == "succeeded" else Payment.Status.PARTIALLY_REFUNDED
            payment.save(update_fields=["status", "updated_at"])


def handle_webhook(payload: bytes, signature: str) -> WebhookEvent:
    if not settings.STRIPE_WEBHOOK_SECRET or not signature:
        raise ValueError("Stripe webhook secret/signature is not configured.")
    try:
        event = stripe.Webhook.construct_event(payload, signature, settings.STRIPE_WEBHOOK_SECRET)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise ValueError("Invalid Stripe webhook signature or payload.") from exc
    event_data = _stripe_dict(event)
    with transaction.atomic():
        webhook, created = WebhookEvent.objects.get_or_create(provider=Provider.STRIPE, event_id=event_data["id"], defaults={"event_type": event_data["type"], "payload": event_data})
        if created:
            transaction.on_commit(lambda event_pk=webhook.pk: _enqueue_stripe_webhook(event_pk))
        return webhook


def _enqueue_stripe_webhook(webhook_event_id: int) -> None:
    from .tasks import process_stripe_webhook
    process_stripe_webhook.delay(webhook_event_id)


def get_current_subscription(tenant) -> Subscription | None:
    now = timezone.now()
    return Subscription.objects.select_related("price__product").filter(tenant=tenant, status__in=[Subscription.Status.ACTIVE, Subscription.Status.TRIALING, Subscription.Status.PAST_DUE], current_period_end__gt=now).order_by("-created_at").first()


def has_feature(tenant, feature_key: str) -> bool:
    subscription = get_current_subscription(tenant)
    return bool(subscription and subscription.price.product.product_features.filter(feature__key=feature_key, feature__active=True, enabled=True).exists())
