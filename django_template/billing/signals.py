from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import BillingCustomer, Price, Product, Provider


@receiver(post_save, sender=Product)
def queue_product_stripe_sync(sender, instance: Product, created: bool, **kwargs) -> None:
    if not created or instance.provider_product_id:
        return
    transaction.on_commit(lambda pk=instance.pk: _queue("sync_product_to_stripe", pk))


@receiver(post_save, sender=Price)
def queue_price_stripe_sync(sender, instance: Price, created: bool, **kwargs) -> None:
    if not created or instance.provider_price_id:
        return
    transaction.on_commit(lambda pk=instance.pk: _queue("sync_price_to_stripe", pk))


@receiver(post_save, sender=BillingCustomer)
def queue_customer_stripe_sync(sender, instance: BillingCustomer, created: bool, **kwargs) -> None:
    if not created or instance.provider != Provider.STRIPE or instance.provider_customer_id:
        return
    transaction.on_commit(lambda pk=instance.pk: _queue("sync_customer_to_stripe", pk))


def _queue(task_name: str, pk: int) -> None:
    from . import tasks
    getattr(tasks, task_name).delay(pk)
