from django.db.models.signals import post_save
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.db import transaction

from .models import User
from .tasks import process_avatar


@receiver(pre_save, sender=User)
def track_avatar_change(sender, instance: User, **kwargs):
    if not instance.pk:
        instance._avatar_changed = bool(instance.avatar)
        return
    previous = sender.objects.filter(pk=instance.pk).only("avatar").first()
    instance._avatar_changed = bool(instance.avatar and (not previous or previous.avatar.name != instance.avatar.name))


@receiver(post_save, sender=User)
def queue_avatar_processing(sender, instance: User, **kwargs):
    if not getattr(instance, "_avatar_changed", False) or not instance.avatar:
        return
    transaction.on_commit(lambda: process_avatar.delay(instance.pk, instance.avatar.name))
