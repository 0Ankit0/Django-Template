import uuid
from django.db import models
from core.models import BaseModel
from .user import User


class UserSession(BaseModel):
    """Track active user sessions"""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    session_key = models.CharField(max_length=40, unique=True, db_index=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    device_type = models.CharField(max_length=50, blank=True)
    country = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = "user_sessions"
        ordering = ["-last_activity"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["session_key"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.device_type} - {self.created_at}"

    def is_expired(self):
        from django.utils import timezone

        return timezone.now() > self.expires_at
