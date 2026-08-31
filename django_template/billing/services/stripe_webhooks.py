from __future__ import annotations

from typing import Any

import stripe
from django.db import transaction
from django.utils import timezone

from ..models import CheckoutSession, Payment, Provider, Subscription, WebhookEvent
from .payment import create_or_update_one_time_subscription
from .stripe import _dt, _price_from_event, _stripe_client, _stripe_dict, sync_invoice, sync_payment_intent, sync_subscription

STRIPE_WEBHOOK_EVENTS = (
    "checkout.session.completed", "checkout.session.async_payment_succeeded", "checkout.session.async_payment_failed", "checkout.session.expired",
    "payment_intent.created", "payment_intent.processing", "payment_intent.requires_action", "payment_intent.succeeded", "payment_intent.payment_failed", "payment_intent.canceled",
    "customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted", "customer.subscription.paused", "customer.subscription.resumed",
    "customer.subscription.pending_update_applied", "customer.subscription.pending_update_expired",
    "invoice.created", "invoice.finalized", "invoice.finalization_failed", "invoice.paid", "invoice.payment_action_required", "invoice.payment_failed", "invoice.payment_succeeded", "invoice.voided",
    "charge.refunded", "charge.refund.updated", "refund.created", "refund.updated", "refund.failed",
)


def _stripe_retrieve(kind: str, object_id: str) -> dict[str, Any]:
    if not object_id:
        raise ValueError(f"Stripe {kind} ID is missing.")
    client = _stripe_client()
    if kind == "subscription":
        return _stripe_dict(client.v1.subscriptions.retrieve(object_id))
    if kind == "invoice":
        return _stripe_dict(client.v1.invoices.retrieve(object_id))
    if kind == "payment_intent":
        return _stripe_dict(client.v1.payment_intents.retrieve(object_id))
    if kind == "checkout_session":
        return _stripe_dict(client.v1.checkout.sessions.retrieve(object_id))
    raise ValueError(f"Unsupported Stripe resource: {kind}")


def _payment_from_refund(data: dict) -> Payment | None:
    payment_intent = str(data.get("payment_intent") or "")
    return Payment.objects.filter(provider=Provider.STRIPE, provider_payment_id=payment_intent).first() if payment_intent else None


def _append_log(log: list[dict[str, Any]], step: str, status: str = "ok", **details: Any) -> None:
    entry = {"at": timezone.now().isoformat(), "step": step, "status": status}
    if details:
        entry["details"] = details
    log.append(entry)


def _process_invoice(data: dict[str, Any], event_type: str, log: list[dict[str, Any]]):
    subscription_id = str(data.get("subscription") or "")
    subscription = Subscription.objects.filter(
        provider=Provider.STRIPE,
        provider_subscription_id=subscription_id,
    ).first() if subscription_id else None

    # Stripe does not guarantee webhook delivery order. If invoice.paid arrives
    # before customer.subscription.created, hydrate the authoritative subscription
    # from Stripe before creating the local invoice/payment records.
    if subscription_id and not subscription:
        _append_log(log, "subscription_dependency_missing", "retry", subscription_id=subscription_id)
        subscription = sync_subscription(_stripe_retrieve("subscription", subscription_id))
        _append_log(log, "subscription_reconciled", subscription_id=subscription.pk)

    invoice = sync_invoice(data)
    _append_log(log, "invoice_synced", invoice_id=invoice.pk, stripe_invoice_id=invoice.provider_invoice_id)

    payment_intent = str(data.get("payment_intent") or "")
    if not payment_intent:
        _append_log(log, "payment_sync_skipped", "ok", reason="invoice_has_no_payment_intent")
        return invoice

    # Always retrieve the PaymentIntent from Stripe instead of trusting a possibly
    # partial webhook object. This also makes retries idempotent.
    payment_data = _stripe_retrieve("payment_intent", payment_intent)
    payment_data["metadata"] = {**(data.get("metadata") or {}), **(payment_data.get("metadata") or {})}
    payment = sync_payment_intent(payment_data)
    if payment is None:
        raise RuntimeError(f"Unable to associate Stripe PaymentIntent {payment_intent} with a local customer.")
    payment.provider_invoice_id = invoice.provider_invoice_id
    if event_type in {"invoice.paid", "invoice.payment_succeeded"}:
        payment.status = Payment.Status.SUCCEEDED
        payment.paid_at = payment.paid_at or timezone.now()
    elif event_type == "invoice.payment_failed":
        payment.status = Payment.Status.FAILED
    payment.save(update_fields=["provider_invoice_id", "status", "paid_at", "updated_at"])
    _append_log(log, "payment_synced", payment_id=payment.pk, stripe_payment_intent=payment_intent)
    return invoice


def process_stripe_webhook_event(webhook: WebhookEvent) -> None:
    # Claim the event in a short transaction. The actual business transaction is
    # separate so a failure cannot leave the event permanently marked as processing.
    with transaction.atomic():
        locked = WebhookEvent.objects.select_for_update().get(pk=webhook.pk)
        if locked.processed:
            return
        if locked.processing:
            return
        locked.processing = True
        locked.error = ""
        locked.save(update_fields=["processing", "error"])
        log = list(locked.processing_log or [])

    _append_log(log, "processing_started", attempt=len(log) + 1)
    try:
        with transaction.atomic():
            event = locked.payload
            event_type = event["type"]
            data = event.get("data", {}).get("object", {})
            _append_log(log, "event_loaded", event_type=event_type, stripe_object_id=data.get("id"))

            if event_type == "checkout.session.completed":
                session = CheckoutSession.objects.filter(
                    provider=Provider.STRIPE,
                    provider_session_id=data.get("id", ""),
                ).select_related("price").first()
                if not session:
                    raise ValueError(f"Local CheckoutSession not found for {data.get('id')}")
                session.status = data.get("status", "complete")
                session.completed_at = session.completed_at or timezone.now()
                session.metadata = {**session.metadata, **(data.get("metadata") or {})}
                if data.get("payment_intent"):
                    session.metadata["payment_intent"] = str(data["payment_intent"])
                if data.get("subscription"):
                    session.metadata["subscription_id"] = str(data["subscription"])
                session.save(update_fields=["status", "completed_at", "metadata"])
                _append_log(log, "checkout_session_synced", session_id=session.pk, stripe_session_id=session.provider_session_id)

                if session.mode == CheckoutSession.Mode.SUBSCRIPTION:
                    subscription_id = str(data.get("subscription") or session.metadata.get("subscription_id") or "")
                    if subscription_id:
                        subscription = sync_subscription(_stripe_retrieve("subscription", subscription_id))
                        _append_log(log, "subscription_synced", subscription_id=subscription.pk, stripe_subscription_id=subscription_id)
                    invoice_id = str(data.get("invoice") or "")
                    if invoice_id:
                        invoice = _process_invoice(_stripe_retrieve("invoice", invoice_id), "invoice.paid", log)
                        _append_log(log, "checkout_invoice_reconciled", invoice_id=invoice.pk)
                elif data.get("payment_intent") and data.get("payment_status") == "paid" and session.price.is_one_time:
                    payment_data = _stripe_retrieve("payment_intent", str(data["payment_intent"]))
                    payment_data["metadata"] = {**session.metadata, **(payment_data.get("metadata") or {})}
                    payment = sync_payment_intent(payment_data)
                    if not payment:
                        raise RuntimeError("Unable to associate completed Checkout payment with a local customer.")
                    create_or_update_one_time_subscription(payment, session.price)
                    _append_log(log, "one_time_payment_reconciled", payment_id=payment.pk)

            elif event_type == "checkout.session.async_payment_succeeded":
                session = CheckoutSession.objects.filter(provider=Provider.STRIPE, provider_session_id=data.get("id", "")).select_related("price").first()
                if not session:
                    raise ValueError(f"Local CheckoutSession not found for {data.get('id')}")
                if data.get("payment_intent"):
                    payment_data = _stripe_retrieve("payment_intent", str(data["payment_intent"]))
                    payment_data["metadata"] = {**session.metadata, **(payment_data.get("metadata") or {})}
                    payment = sync_payment_intent(payment_data)
                    if not payment:
                        raise RuntimeError("Unable to associate async Checkout payment with a local customer.")
                    if session.price.is_one_time:
                        create_or_update_one_time_subscription(payment, session.price)
                    _append_log(log, "async_payment_reconciled", payment_id=payment.pk)

            elif event_type in {"checkout.session.async_payment_failed", "checkout.session.expired"}:
                CheckoutSession.objects.filter(provider=Provider.STRIPE, provider_session_id=data.get("id", "")).update(status="expired")
                _append_log(log, "checkout_session_expired", stripe_session_id=data.get("id"))

            elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.paused", "customer.subscription.resumed", "customer.subscription.pending_update_applied"}:
                subscription = sync_subscription(data)
                _append_log(log, "subscription_synced", subscription_id=subscription.pk, stripe_subscription_id=subscription.provider_subscription_id)

            elif event_type == "customer.subscription.pending_update_expired":
                subscription = Subscription.objects.filter(provider=Provider.STRIPE, provider_subscription_id=data.get("id", "")).first()
                if subscription:
                    subscription.metadata = {**subscription.metadata, "pending_update_expired": True}
                    subscription.save(update_fields=["metadata", "updated_at"])
                else:
                    raise ValueError(f"Local subscription not found for {data.get('id')}")
                _append_log(log, "subscription_pending_update_expired", subscription_id=subscription.pk)

            elif event_type == "customer.subscription.deleted":
                subscription = Subscription.objects.filter(provider=Provider.STRIPE, provider_subscription_id=data.get("id", "")).first()
                if subscription:
                    subscription.status = Subscription.Status.CANCELED
                    subscription.cancel_at_period_end = False
                    subscription.canceled_at = _dt(data.get("canceled_at")) or timezone.now()
                    subscription.save(update_fields=["status", "cancel_at_period_end", "canceled_at", "updated_at"])
                else:
                    raise ValueError(f"Local subscription not found for {data.get('id')}")
                _append_log(log, "subscription_canceled", subscription_id=subscription.pk)

            elif event_type.startswith("invoice."):
                _process_invoice(data, event_type, log)

            elif event_type in {"payment_intent.created", "payment_intent.processing", "payment_intent.requires_action", "payment_intent.succeeded", "payment_intent.payment_failed", "payment_intent.canceled"}:
                payment = sync_payment_intent(data)
                if payment is None:
                    raise RuntimeError(f"Unable to associate PaymentIntent {data.get('id')} with a local customer.")
                _append_log(log, "payment_intent_synced", payment_id=payment.pk, stripe_payment_intent=payment.provider_payment_id)
                if payment.status == Payment.Status.SUCCEEDED:
                    price = _price_from_event(data)
                    if price and price.is_one_time:
                        create_or_update_one_time_subscription(payment, price)
                        _append_log(log, "one_time_subscription_synced", payment_id=payment.pk)

            elif event_type in {"charge.refunded", "charge.refund.updated", "refund.created", "refund.updated", "refund.failed"}:
                payment = _payment_from_refund(data)
                if payment:
                    payment.status = Payment.Status.PENDING if event_type == "refund.failed" or data.get("status") == "failed" else Payment.Status.REFUNDED
                    payment.metadata = {**payment.metadata, "refund": data}
                    payment.save(update_fields=["status", "metadata", "updated_at"])
                    _append_log(log, "refund_synced", payment_id=payment.pk)
                else:
                    _append_log(log, "refund_sync_skipped", "ok", reason="payment_not_found", stripe_payment_intent=data.get("payment_intent"))

            else:
                _append_log(log, "event_ignored", "ok", event_type=event_type)

        _append_log(log, "processing_completed", processed=True)
        WebhookEvent.objects.filter(pk=locked.pk).update(
            processing=False,
            processed=True,
            processed_at=timezone.now(),
            error="",
            processing_log=log,
        )
    except Exception as exc:
        _append_log(log, "processing_failed", "error", error=str(exc), error_type=type(exc).__name__)
        WebhookEvent.objects.filter(pk=locked.pk).update(
            processing=False,
            processed=False,
            error=str(exc),
            processing_log=log,
        )
        raise
