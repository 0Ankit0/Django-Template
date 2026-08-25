from __future__ import annotations

from datetime import timedelta

from celery import shared_task
from django.db import close_old_connections
from django.db.models import Q
from django.utils import timezone

from .models import Provider
from .models import WebhookEvent
from .services import expire_one_time_subscriptions
from .stripe_webhooks import process_stripe_webhook_event


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
    process_stripe_webhook_event(event)


@shared_task
def retry_unprocessed_stripe_webhooks() -> int:
    close_old_connections()
    stale_before = timezone.now() - timedelta(minutes=10)
    ids = list(
        WebhookEvent.objects.filter(provider=Provider.STRIPE, processed=False)
        .filter(Q(processing=False) | Q(processing=True, created_at__lt=stale_before))
        .values_list("pk", flat=True)[:100]
    )
    for event_id in ids:
        process_stripe_webhook.delay(event_id)
    return len(ids)


@shared_task
def expire_one_time_purchases() -> int:
    close_old_connections()
    return expire_one_time_subscriptions()
