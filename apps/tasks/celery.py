import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("ecommerce")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks(
    [
        "tasks",
    ]
)

# Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    "sync-content-every-hour": {
        "task": "tasks.content_tasks.sync_content",
        "schedule": crontab(minute=0),
    },
    "send-scheduled-notifications": {
        "task": "tasks.notification_tasks.send_scheduled_notifications",
        "schedule": crontab(minute="*/5"),
    },
    "cleanup-expired-tokens": {
        "task": "tasks.scheduler.cleanup_expired_tokens",
        "schedule": crontab(hour=0, minute=0),
    },
}

app.conf.timezone = "UTC"
