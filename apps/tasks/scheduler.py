import logging
from datetime import timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_tokens():
    """Clean up expired JWT tokens and sessions."""
    from rest_framework_simplejwt.token_blacklist.models import OutstandingToken

    logger.info("Starting cleanup of expired tokens")

    # Delete tokens that have expired more than 7 days ago
    expiry_date = timezone.now() - timedelta(days=7)

    try:
        # Get expired outstanding tokens
        expired_tokens = OutstandingToken.objects.filter(expires_at__lt=expiry_date)
        count = expired_tokens.count()
        expired_tokens.delete()

        logger.info(f"Deleted {count} expired tokens")
        return {"deleted_tokens": count}
    except Exception as e:
        logger.error(f"Error cleaning up tokens: {e}")
        return {"error": str(e)}


@shared_task
def schedule_task(task_name: str, task_data: dict, eta=None):
    """Generic task scheduler for deferred execution."""
    from importlib import import_module

    logger.info(f"Scheduling task: {task_name} with data: {task_data}")

    try:
        module_path, func_name = task_name.rsplit(".", 1)
        module = import_module(module_path)
        task_func = getattr(module, func_name)

        if eta:
            task_func.apply_async(kwargs=task_data, eta=eta)
        else:
            task_func.delay(**task_data)

        return {"status": "scheduled", "task": task_name}
    except Exception as e:
        logger.error(f"Error scheduling task: {e}")
        return {"error": str(e)}
