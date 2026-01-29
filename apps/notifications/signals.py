from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save
from django.dispatch import receiver

from . import models


@receiver(post_save, sender=models.Notification)
def notify_about_entry(sender, instance: models.Notification, created, update_fields, **kwargs):
    if created:
        channel_layer = get_channel_layer()
        user_group = f"user_{instance.user.id}"

        # Send notification via WebSocket
        async_to_sync(channel_layer.group_send)(
            user_group,
            {
                "type": "notification_message",
                "message": {
                    "id": str(instance.id),
                    "type": instance.type,
                    "title": instance.data.get("title", ""),
                    "content": instance.data.get("content", ""),
                    "is_read": instance.is_read,
                    "created_at": instance.created_at.isoformat(),
                },
            },
        )
