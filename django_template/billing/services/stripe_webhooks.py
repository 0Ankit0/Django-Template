from __future__ import annotations

from typing import Any

import stripe
from django.db import IntegrityError, transaction
from django.utils import timezone

from ..models import CheckoutSession, Invoice, Payment, Provider, Subscription, WebhookEvent
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


def _subscription_period_data(data: dict[str, Any]) -> tuple[Any, Any]:
    items = data.get("items", {}).get("data", [])
    item = items[0] if items else {}
    return (
        data.get("current_period_start") or item.get("current_period_start"),
        data.get("current_period_end") or item.get("current_period_end"),
    )


def _apply_subscription_item_period(subscription: Subscription, data: dict[str, Any]) -> Subscription:
    period_start, period_end = _subscription_period_data(data)
    if period_start is not None:
        subscription.current_period_start = _dt(period_start)
    if period_end is not None:
        subscription.current_period_end = _dt(period_end)
    if period_start is not None or period_end is not None:
        subscription.save(update_fields=["current_period_start", "current_period_end", "updated_at"])
    return subscription


def _invoice_payment_intent(data: dict[str, Any]) -> str:
    direct = data.get("payment_intent")
    if direct:
        return str(direct)
    payments = data.get("payments", {}).get("data", [])
    for invoice_payment in payments:
        payment = invoice_payment.get("payment") or {}
        payment_intent = payment.get("payment_intent") or invoice_payment.get("payment_intent")
        if payment_intent:
            return str(payment_intent)
    return ""


def _create_invoice_settlement_payment(invoice: Invoice, data: dict[str, Any], log: list[dict[str, Any]]) -> Payment | None:
    if invoice.status != Invoice.Status.PAID:
        return None

    # A Stripe invoice can be marked paid by customer balance/credit without a
    # PaymentIntent. The invoice total is still the settled commercial amount,
    # while amount_due/amount_paid can both be zero because the balance covered it.
    amount = int(data.get("total") or invoice.amount_total or data.get("amount_paid") or 0)
    if amount <= 0:
        _append_log(log, "settlement_payment_skipped", "ok", reason="zero_invoice_total")
        return None

    payment_id = f"invoice:{invoice.provider_invoice_id}"
    defaults = {
        "tenant": invoice.tenant,
        "subscription": invoice.subscription,
        "amount": amount,
        "currency": str(data.get("currency") or invoice.currency).upper(),
        "status": Payment.Status.SUCCEEDED,
        "provider_invoice_id": invoice.provider_invoice_id,
        "paid_at": invoice.paid_at or timezone.now(),
        "metadata": {
            "invoice_id": invoice.provider_invoice_id,
            "settlement_type": "invoice_without_payment_intent",
            "payment_source": "customer_balance_or_other_non_payment_intent_settlement",
        },
    }
    try:
        payment, _ = Payment.objects.update_or_create(
            provider=Provider.STRIPE,
            provider_payment_id=payment_id,
            defaults=defaults,
        )
    except IntegrityError:
        payment = Payment.objects.get(provider=Provider.STRIPE, provider_payment_id=payment_id)
    _append_log(log, "invoice_settlement_payment_synced", payment_id=payment.pk, amount=amount, source=defaults["metadata"]["payment_source"])
    return payment


def _process_invoice(data: dict[str, Any], event_type: str, log: list[dict[str, Any]]):
    invoice_id = str(data.get("id") or "")
    if not invoice_id:
        raise ValueError("Stripe invoice ID is missing.")

    # Webhook payloads can be intentionally small. Re-read the authoritative
    # invoice so payment references, total, balance, subscription and metadata
    # are not lost because the event snapshot was incomplete.
    remote_invoice = _stripe_retrieve("invoice", invoice_id)
    invoice_data = {**data, **remote_invoice}

    subscription_id = str(invoice_data.get("subscription") or "")
    subscription = Subscription.objects.filter(provider=Provider.STRIPE, provider_subscription_id=subscription_id).first() if subscription_id else None

    if subscription_id and not subscription:
        _append_log(log, "subscription_dependency_missing", "retry", subscription_id=subscription_id)
        remote_subscription = _stripe_retrieve("subscription", subscription_id)
        subscription = sync_subscription(remote_subscription)
        _apply_subscription_item_period(subscription, remote_subscription)
        _append_log(log, "subscription_reconciled", subscription_id=subscription.pk)
    elif subscription_id:
        remote_subscription = _stripe_retrieve("subscription", subscription_id)
        subscription = _apply_subscription_item_period(subscription, remote_subscription)
        _append_log(log, "subscription_period_reconciled", subscription_id=subscription.pk)

    invoice = sync_invoice(invoice_data)
    invoice.amount_total = int(invoice_data.get("total") or invoice.amount_total or invoice_data.get("amount_due") or invoice_data.get("amount_paid") or 0)
    invoice.subscription = subscription or invoice.subscription
    invoice.save(update_fields=["amount_total", "subscription", "updated_at"])
    _append_log(log, "invoice_synced", invoice_id=invoice.pk, stripe_invoice_id=invoice.provider_invoice_id, amount_total=invoice.amount_total, amount_due=invoice.amount_due, amount_paid=invoice.amount_paid)

    payment_intent = _invoice_payment_intent(invoice_data)
    if payment_intent:
        payment_data = _stripe_retrieve("payment_intent", payment_intent)
        payment_data["metadata"] = {**(invoice_data.get("metadata") or {}), **(payment_data.get("metadata") or {})}
        payment = sync_payment_intent(payment_data)
        if payment is None:
            raise RuntimeError(f"Unable to associate Stripe PaymentIntent {payment_intent} with a local customer.")
        if subscription:
            payment.subscription = subscription
        payment.provider_invoice_id = invoice.provider_invoice_id
        if invoice.status == Invoice.Status.PAID or event_type in {"invoice.paid", "invoice.payment_succeeded"}:
            payment.status = Payment.Status.SUCCEEDED
            payment.paid_at = payment.paid_at or timezone.now()
        elif event_type == "invoice.payment_failed":
            payment.status = Payment.Status.FAILED
        payment.save(update_fields=["subscription", "provider_invoice_id", "status", "paid_at", "updated_at"])
        _append_log(log, "payment_synced", payment_id=payment.pk, stripe_payment_intent=payment_intent, amount=payment.amount)
    elif invoice.status == Invoice.Status.PAID and event_type in {"invoice.paid", "invoice.payment_succeeded"}:
        _create_invoice_settlement_payment(invoice, invoice_data, log)

    return invoice


def process_stripe_webhook_event(webhook: WebhookEvent) -> None:
    with transaction.atomic():
        locked = WebhookEvent.objects.select_for_update().get(pk=webhook.pk)
        if locked.processed or locked.processing:
            return
        locked.processing = True
        locked.error = ""
        locked.save(update_fields=["processing", "error"])
        log = list(locked.processing_log or [])

    _append_log(log, "processing_started", attempt=sum(1 for item in log if item.get("step") == "processing_started") + 1)
    try:
        with transaction.atomic():
            event = locked.payload
            event_type = event["type"]
            data = event.get("data", {}).get("object", {})
            _append_log(log, "event_loaded", event_type=event_type, stripe_object_id=data.get("id"))

            if event_type == "checkout.session.completed":
                session = CheckoutSession.objects.filter(provider=Provider.STRIPE, provider_session_id=data.get("id", "")).select_related("price").first()
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
                    if not subscription_id:
                        raise ValueError(f"Completed subscription CheckoutSession {session.pk} has no Stripe subscription ID.")
                    remote_subscription = _stripe_retrieve("subscription", subscription_id)
                    subscription = sync_subscription(remote_subscription)
                    _apply_subscription_item_period(subscription, remote_subscription)
                    _append_log(log, "subscription_synced", subscription_id=subscription.pk, stripe_subscription_id=subscription_id)
                    invoice_id = str(data.get("invoice") or "")
                    if invoice_id:
                        invoice = _process_invoice({"id": invoice_id}, "invoice.paid", log)
                        _append_log(log, "checkout_invoice_reconciled", invoice_id=invoice.pk)

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
                subscription_data = _stripe_retrieve("subscription", str(data.get("id")))
                subscription = sync_subscription(subscription_data)
                _apply_subscription_item_period(subscription, subscription_data)
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
        WebhookEvent.objects.filter(pk=locked.pk).update(processing=False, processed=True, processed_at=timezone.now(), error="", processing_log=log)
    except Exception as exc:
        _append_log(log, "processing_failed", "error", error=str(exc), error_type=type(exc).__name__)
        WebhookEvent.objects.filter(pk=locked.pk).update(processing=False, processed=False, error=str(exc), processing_log=log)
        raise
