from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from .models import CheckoutSession
from .models import Invoice
from .models import Payment
from .models import Provider
from .models import Subscription
from .models import WebhookEvent
from .services import _dt
from .services import _price_from_event
from .services import create_or_update_one_time_subscription
from .services import sync_invoice
from .services import sync_payment_intent
from .services import sync_subscription

STRIPE_WEBHOOK_EVENTS = (
    "checkout.session.completed",
    "checkout.session.async_payment_succeeded",
    "checkout.session.async_payment_failed",
    "checkout.session.expired",
    "payment_intent.created",
    "payment_intent.processing",
    "payment_intent.requires_action",
    "payment_intent.succeeded",
    "payment_intent.payment_failed",
    "payment_intent.canceled",
    "customer.subscription.created",
    "customer.subscription.updated",
    "customer.subscription.deleted",
    "customer.subscription.paused",
    "customer.subscription.resumed",
    "customer.subscription.pending_update_applied",
    "customer.subscription.pending_update_expired",
    "invoice.created",
    "invoice.finalized",
    "invoice.finalization_failed",
    "invoice.paid",
    "invoice.payment_action_required",
    "invoice.payment_failed",
    "invoice.payment_succeeded",
    "invoice.voided",
    "charge.refunded",
    "charge.refund.updated",
    "refund.created",
    "refund.updated",
    "refund.failed",
)


def _payment_from_refund(data: dict) -> Payment | None:
    payment_intent = str(data.get("payment_intent") or "")
    if payment_intent:
        return Payment.objects.filter(provider=Provider.STRIPE, provider_payment_id=payment_intent).first()
    return None


def process_stripe_webhook_event(webhook: WebhookEvent) -> None:
    with transaction.atomic():
        locked = WebhookEvent.objects.select_for_update().get(pk=webhook.pk)
        if locked.processed or locked.processing:
            return
        locked.processing = True
        locked.save(update_fields=["processing"])

    try:
        with transaction.atomic():
            event = locked.payload
            event_type = event["type"]
            data = event.get("data", {}).get("object", {})

            if event_type == "checkout.session.completed":
                session = (
                    CheckoutSession.objects.filter(
                        provider=Provider.STRIPE,
                        provider_session_id=data.get("id", ""),
                    )
                    .select_related("price")
                    .first()
                )
                if session:
                    session.status = data.get("status", "complete")
                    session.completed_at = session.completed_at or timezone.now()
                    session.metadata = {**session.metadata, **(data.get("metadata") or {})}
                    if data.get("payment_intent"):
                        session.metadata["payment_intent"] = str(data["payment_intent"])
                    session.save(update_fields=["status", "completed_at", "metadata"])
                    if (
                        session.mode == CheckoutSession.Mode.PAYMENT
                        and data.get("payment_intent")
                        and data.get("payment_status") == "paid"
                        and session.price.is_one_time
                    ):
                        payment = sync_payment_intent(
                            {
                                "id": str(data["payment_intent"]),
                                "customer": data.get("customer"),
                                "amount": data.get("amount_total"),
                                "currency": data.get("currency"),
                                "status": "succeeded",
                                "metadata": session.metadata,
                            },
                        )
                        if payment:
                            create_or_update_one_time_subscription(payment, session.price)

            elif event_type in {"checkout.session.async_payment_succeeded"}:
                session = (
                    CheckoutSession.objects.filter(
                        provider=Provider.STRIPE,
                        provider_session_id=data.get("id", ""),
                    )
                    .select_related("price")
                    .first()
                )
                if session and data.get("payment_intent"):
                    payment = sync_payment_intent(
                        {
                            "id": str(data["payment_intent"]),
                            "customer": data.get("customer"),
                            "amount": data.get("amount_total"),
                            "currency": data.get("currency"),
                            "status": "succeeded",
                            "metadata": data.get("metadata") or session.metadata,
                        },
                    )
                    if payment and session.price.is_one_time:
                        create_or_update_one_time_subscription(payment, session.price)

            elif event_type in {"checkout.session.async_payment_failed", "checkout.session.expired"}:
                CheckoutSession.objects.filter(
                    provider=Provider.STRIPE,
                    provider_session_id=data.get("id", ""),
                ).update(status="expired")

            elif event_type in {
                "customer.subscription.created",
                "customer.subscription.updated",
                "customer.subscription.paused",
                "customer.subscription.resumed",
                "customer.subscription.pending_update_applied",
            }:
                sync_subscription(data)

            elif event_type == "customer.subscription.pending_update_expired":
                subscription = Subscription.objects.filter(
                    provider=Provider.STRIPE,
                    provider_subscription_id=data.get("id", ""),
                ).first()
                if subscription:
                    metadata = {**subscription.metadata, "pending_update_expired": True}
                    subscription.metadata = metadata
                    subscription.save(update_fields=["metadata", "updated_at"])

            elif event_type == "customer.subscription.deleted":
                subscription = Subscription.objects.filter(
                    provider=Provider.STRIPE,
                    provider_subscription_id=data.get("id", ""),
                ).first()
                if subscription:
                    subscription.status = Subscription.Status.CANCELED
                    subscription.cancel_at_period_end = False
                    subscription.canceled_at = _dt(data.get("canceled_at")) or timezone.now()
                    subscription.save(update_fields=["status", "cancel_at_period_end", "canceled_at", "updated_at"])

            elif event_type.startswith("invoice."):
                invoice = sync_invoice(data)
                payment_intent = data.get("payment_intent")
                if payment_intent:
                    if event_type in {"invoice.paid", "invoice.payment_succeeded"}:
                        status = Payment.Status.SUCCEEDED
                        paid_at = timezone.now()
                    elif event_type in {"invoice.payment_failed", "invoice.payment_action_required"}:
                        status = Payment.Status.FAILED if event_type == "invoice.payment_failed" else Payment.Status.PENDING
                        paid_at = None
                    else:
                        status = Payment.Status.PENDING
                        paid_at = None
                    Payment.objects.update_or_create(
                        provider=Provider.STRIPE,
                        provider_payment_id=str(payment_intent),
                        defaults={
                            "tenant": invoice.tenant,
                            "subscription": invoice.subscription,
                            "amount": int(data.get("amount_paid") or data.get("amount_due") or 0),
                            "currency": data.get("currency") or "usd",
                            "status": status,
                            "provider_invoice_id": data["id"],
                            "paid_at": paid_at,
                            "metadata": data.get("metadata") or {},
                        },
                    )
                elif event_type in {"invoice.finalization_failed", "invoice.voided"}:
                    invoice.metadata = {**invoice.metadata, "event_type": event_type}
                    invoice.save(update_fields=["metadata", "updated_at"])

            elif event_type in {
                "payment_intent.created",
                "payment_intent.processing",
                "payment_intent.requires_action",
                "payment_intent.succeeded",
                "payment_intent.payment_failed",
                "payment_intent.canceled",
            }:
                payment = sync_payment_intent(data)
                if payment and payment.status == Payment.Status.SUCCEEDED:
                    price = _price_from_event(data)
                    if price and price.is_one_time:
                        create_or_update_one_time_subscription(payment, price)

            elif event_type in {"charge.refunded", "charge.refund.updated", "refund.created", "refund.updated", "refund.failed"}:
                payment = _payment_from_refund(data)
                if payment:
                    refund_status = data.get("status")
                    if event_type == "refund.failed" or refund_status == "failed":
                        payment.status = Payment.Status.PENDING
                    elif data.get("refunded") or refund_status == "succeeded" or event_type in {"charge.refunded", "refund.updated", "refund.created"}:
                        payment.status = Payment.Status.REFUNDED
                    payment.metadata = {**payment.metadata, "refund": data}
                    payment.save(update_fields=["status", "metadata", "updated_at"])

        WebhookEvent.objects.filter(pk=locked.pk).update(
            processing=False,
            processed=True,
            processed_at=timezone.now(),
            error="",
        )
    except Exception as exc:
        WebhookEvent.objects.filter(pk=locked.pk).update(processing=False, error=str(exc))
        raise
