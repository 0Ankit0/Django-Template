from __future__ import annotations

import json
from typing import Any

import stripe
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction

from django_template.billing.models import Provider, WebhookEvent


def handle_webhook(payload: bytes, signature: str) -> WebhookEvent:
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not secret or not signature:
        raise ValueError("Stripe webhook secret/signature is not configured.")
    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise ValueError("Invalid Stripe webhook signature or payload.") from exc

    if hasattr(event, "to_dict_recursive"):
        event_dict = event.to_dict_recursive()
    elif hasattr(event, "to_dict"):
        event_dict = event.to_dict()
    else:
        event_dict = dict(event)
    event_data: dict[str, Any] = json.loads(json.dumps(event_dict, cls=DjangoJSONEncoder))

    with transaction.atomic():
        webhook, _ = WebhookEvent.objects.get_or_create(
            provider=Provider.STRIPE,
            event_id=event_data["id"],
            defaults={"event_type": event_data["type"], "payload": event_data},
        )
        # Stripe can resend the same event when our worker/broker is unavailable.
        # Re-enqueue every unprocessed event instead of only newly-created rows.
        if not webhook.processed and not webhook.processing:
            transaction.on_commit(lambda event_pk=webhook.pk: _enqueue(event_pk))
        return webhook


def _enqueue(webhook_event_id: int) -> None:
    from ..tasks import process_stripe_webhook

    try:
        process_stripe_webhook.delay(webhook_event_id)
    except Exception as exc:
        # The WebhookEvent is already durable. Recording the enqueue failure makes
        # the problem observable while retry_unprocessed_stripe_webhooks can safely
        # enqueue it again later.
        WebhookEvent.objects.filter(pk=webhook_event_id, processed=False).update(
            processing=False,
            error=f"Webhook task enqueue failed: {exc}",
        )
        raise
