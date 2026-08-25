from __future__ import annotations

from celery import shared_task
from django.db import close_old_connections
from django.utils import timezone

from .models import Entitlement
from .models import Provider
from .models import WebhookEvent
from .services import process_webhook_event


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 8},
)
def process_stripe_webhook(self, webhook_event_id: int) -> None:
    close_old_connections()
    event = WebhookEvent.objects.get(pk=webhook_event_id, provider=Provider.STRIPE)
    process_webhook_event(event)


@shared_task
def retry_unprocessed_stripe_webhooks() -> int:
    close_old_connections()
    ids = list(WebhookEvent.objects.filter(provider=Provider.STRIPE, processed=False, processing=False).values_list("pk", flat=True)[:100])
    for event_id in ids:
        process_stripe_webhook.delay(event_id)
    return len(ids)


@shared_task
def expire_entitlements() -> int:
    close_old_connections()
    return Entitlement.objects.filter(active=True, expires_at__lte=timezone.now()).update(active=False, updated_at=timezone.now())
