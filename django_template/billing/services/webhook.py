from __future__ import annotations

from typing import Any

import stripe
from django.conf import settings
from django.db import transaction
from django.core.serializers.json import DjangoJSONEncoder
import json
from django_template.billing.models import Provider, WebhookEvent


def handle_webhook(payload: bytes, signature: str) -> WebhookEvent:
    secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not secret or not signature:
        raise ValueError("Stripe webhook secret/signature is not configured.")
    try:
        event = stripe.Webhook.construct_event(payload, signature, secret)
    except (ValueError, stripe.SignatureVerificationError) as exc:
        raise ValueError("Invalid Stripe webhook signature or payload.") from exc
    # event_data: dict[str, Any] = event.to_dict_recursive() if hasattr(event, "to_dict_recursive") else dict(event)
    event_data = json.loads(
        json.dumps(event.to_dict(), cls=DjangoJSONEncoder)
    )
    with transaction.atomic():
        webhook, created = WebhookEvent.objects.get_or_create(
            provider=Provider.STRIPE,
            event_id=event_data["id"],
            defaults={"event_type": event_data["type"], "payload": event_data},
        )
        if created:
            transaction.on_commit(lambda event_pk=webhook.pk: _enqueue(event_pk))
        return webhook


def _enqueue(webhook_event_id: int) -> None:
    from ..tasks import process_stripe_webhook
    process_stripe_webhook.delay(webhook_event_id)
