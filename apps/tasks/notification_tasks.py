import logging

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def create_notification(user_id: int, notification_type: str, data: dict = None):
    """Create a notification and send it via WebSocket."""
    from notifications.models import Notification

    try:
        notification = Notification.objects.create(
            user_id=user_id,
            type=notification_type,
            data=data or {},
        )

        # Send via WebSocket
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"notifications_{user_id}",
            {
                "type": "notification_message",
                "notification": {
                    "id": str(notification.id),
                    "type": notification.type,
                    "data": notification.data,
                    "is_read": notification.is_read,
                    "created_at": notification.created_at.isoformat(),
                },
            },
        )

        logger.info(f"Notification created for user {user_id}: {notification_type}")
        return {"notification_id": str(notification.id)}
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        return {"error": str(e)}


@shared_task
def send_scheduled_notifications():
    """Send all scheduled notifications that are due."""
    from notifications.models import ScheduledNotification

    now = timezone.now()
    due_notifications = ScheduledNotification.objects.filter(scheduled_for__lte=now, sent=False)

    sent_count = 0
    for scheduled in due_notifications:
        create_notification.delay(user_id=scheduled.user_id, notification_type=scheduled.type, data=scheduled.data)
        scheduled.sent = True
        scheduled.sent_at = now
        scheduled.save()
        sent_count += 1

    logger.info(f"Sent {sent_count} scheduled notifications")
    return {"sent_count": sent_count}


@shared_task
def broadcast_notification(notification_type: str, data: dict = None, tenant_id: str = None):
    """Broadcast a notification to all users or all users in a tenant."""
    from multitenancy.models import TenantMembership
    from iam.models import User

    if tenant_id:
        user_ids = TenantMembership.objects.filter(tenant_id=tenant_id, is_active=True).values_list(
            "user_id", flat=True
        )
    else:
        user_ids = User.objects.filter(is_active=True).values_list("id", flat=True)

    for user_id in user_ids:
        create_notification.delay(user_id=user_id, notification_type=notification_type, data=data)

    logger.info(f"Broadcast notification to {len(user_ids)} users")
    return {"broadcast_to": len(user_ids)}


@shared_task
def mark_old_notifications_read(user_id: int, days: int = 30):
    """Mark notifications older than specified days as read."""
    from datetime import timedelta

    from notifications.models import Notification

    cutoff_date = timezone.now() - timedelta(days=days)

    updated = Notification.objects.filter(user_id=user_id, is_read=False, created_at__lt=cutoff_date).update(
        is_read=True, read_at=timezone.now()
    )

    logger.info(f"Marked {updated} old notifications as read for user {user_id}")
    return {"marked_read": updated}
