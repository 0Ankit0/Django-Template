import datetime

import hashid_field
from django.conf import settings
from django.db import models
from django.utils import timezone

from . import managers


class Notification(models.Model):
    id: str = hashid_field.HashidAutoField(primary_key=True)
    user: settings.AUTH_USER_MODEL = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    type: str = models.CharField(max_length=64)

    created_at: datetime.datetime = models.DateTimeField(auto_now_add=True)
    read_at: datetime.datetime | None = models.DateTimeField(null=True, blank=True)

    data: dict = models.JSONField(default=dict)

    issuer: settings.AUTH_USER_MODEL = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name="notifications_issued"
    )

    objects = managers.NotificationManager()

    def __str__(self) -> str:
        return str(self.id)

    @property
    def is_read(self) -> bool:
        return self.read_at is not None

    @is_read.setter
    def is_read(self, val: bool):
        self.read_at = timezone.now() if val else None


class ScheduledNotification(models.Model):
    """Model for scheduled notifications to be sent at a future time."""

    id: str = hashid_field.HashidAutoField(primary_key=True)
    user: settings.AUTH_USER_MODEL = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="scheduled_notifications"
    )
    type: str = models.CharField(max_length=64)
    data: dict = models.JSONField(default=dict)

    scheduled_for: datetime.datetime = models.DateTimeField()
    sent: bool = models.BooleanField(default=False)
    sent_at: datetime.datetime | None = models.DateTimeField(null=True, blank=True)

    created_at: datetime.datetime = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_for"]
        indexes = [
            models.Index(fields=["scheduled_for", "sent"]),
        ]

    def __str__(self) -> str:
        return f"Scheduled: {self.type} for {self.user} at {self.scheduled_for}"


class NotificationPreference(models.Model):
    """User notification preferences."""

    class Channels(models.TextChoices):
        EMAIL = "email", "Email"
        PUSH = "push", "Push Notification"
        IN_APP = "in_app", "In-App"

    user: settings.AUTH_USER_MODEL = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notification_preferences"
    )
    notification_type: str = models.CharField(max_length=64)
    channel: Channels = models.CharField(max_length=20, choices=Channels.choices)
    enabled: bool = models.BooleanField(default=True)

    class Meta:
        unique_together = ["user", "notification_type", "channel"]

    def __str__(self) -> str:
        status = "enabled" if self.enabled else "disabled"
        return f"{self.user}: {self.notification_type} via {self.channel} ({status})"
