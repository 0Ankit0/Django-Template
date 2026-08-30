from __future__ import annotations

import calendar
from datetime import datetime, timedelta

from django.db import transaction
from django.utils import timezone

from ..models import Payment, Price, Subscription


def add_price_interval(start: datetime, price: Price) -> datetime:
    """Calculate access expiry from the Price interval and interval count."""
    count = price.interval_count
    if count < 1:
        raise ValueError("Price interval_count must be at least 1.")
    if price.interval == Price.Interval.DAY:
        return start + timedelta(days=count)
    if price.interval == Price.Interval.WEEK:
        return start + timedelta(weeks=count)
    if price.interval == Price.Interval.MONTH:
        month_index = start.month - 1 + count
        year_delta, month_index = divmod(month_index, 12)
        month = month_index + 1
        day = min(start.day, calendar.monthrange(start.year + year_delta, month)[1])
        return start.replace(year=start.year + year_delta, month=month, day=day)
    if price.interval == Price.Interval.YEAR:
        year = start.year + count
        day = min(start.day, calendar.monthrange(year, start.month)[1])
        return start.replace(year=year, day=day)
    raise ValueError(f"Unsupported one-time price interval: {price.interval}")


@transaction.atomic
def create_or_update_one_time_subscription(
    payment: Payment,
    price: Price,
    *,
    provider_reference: str | None = None,
) -> Subscription:
    """Create or refresh local access for a successful one-time payment."""
    if not price.is_one_time:
        raise ValueError("Only one-time prices create an expiring local subscription.")
    if payment.status != Payment.Status.SUCCEEDED:
        raise ValueError("Only successful payments create an active local subscription.")

    starts_at = payment.paid_at or timezone.now()
    expires_at = add_price_interval(starts_at, price)
    reference = provider_reference or payment.provider_payment_id
    if not reference:
        raise ValueError("A provider payment reference is required.")

    subscription, _ = Subscription.objects.get_or_create(
        provider=payment.provider,
        provider_subscription_id=f"one-time:{reference}",
        defaults={"tenant": payment.tenant, "price": price, "status": Subscription.Status.ACTIVE},
    )
    subscription.tenant = payment.tenant
    subscription.price = price
    subscription.status = Subscription.Status.ACTIVE if expires_at > timezone.now() else Subscription.Status.CANCELED
    subscription.provider_customer_id = payment.metadata.get("customer_id") or None
    subscription.current_period_start = starts_at
    subscription.current_period_end = expires_at
    subscription.cancel_at_period_end = True
    subscription.canceled_at = None if subscription.status == Subscription.Status.ACTIVE else expires_at
    subscription.metadata = {
        **subscription.metadata,
        "one_time": True,
        "payment_id": payment.provider_payment_id,
        "provider_reference": reference,
    }
    subscription.save()

    if payment.subscription_id != subscription.pk:
        payment.subscription = subscription
        payment.save(update_fields=["subscription", "updated_at"])
    return subscription
