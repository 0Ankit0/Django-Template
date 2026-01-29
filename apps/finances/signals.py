import logging

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
import stripe

from multitenancy.models import Tenant

from .services import subscriptions

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Tenant)
def create_free_plan_subscription(sender, instance, created, **kwargs):
    if not settings.STRIPE_ENABLED:
        return

    if created:
        try:
            subscriptions.initialize_tenant(tenant=instance)
        except stripe.AuthenticationError as e:
            logger.error(msg=e._message, exc_info=e)
            return
        except Exception as e:
            raise e
