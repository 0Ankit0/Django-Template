from __future__ import annotations

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from .email import InvitationEmailAdapter
from .models import Invitation
from .services import invitation_url


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
    acks_late=True,
)
def send_invitation_email(self, invitation_id: int) -> bool:
    """Render and deliver one invitation email outside the web request."""
    try:
        invitation = Invitation.objects.select_related(
            "tenant",
            "user",
            "invited_by",
        ).get(pk=invitation_id)
    except ObjectDoesNotExist:
        return False

    if invitation.sent_at is not None:
        return True
    if invitation.status != Invitation.Status.PENDING:
        return False
    if invitation.expires_at <= timezone.now():
        invitation.status = Invitation.Status.EXPIRED
        invitation.save(update_fields=["status", "updated_at"])
        return False

    # The invitation URL is deliberately built from the configured public
    # tenant-users domain so the Celery worker doesn't need a request object.
    url = invitation_url(None, invitation)
    context = {
        "invitation": invitation,
        "tenant": invitation.tenant,
        "user": invitation.user,
        "invited_by": invitation.invited_by,
        "invitation_url": url,
        "expires_at": invitation.expires_at,
        "message": invitation.message,
    }

    delivered = InvitationEmailAdapter().send_mail(invitation.user.email, context)
    if delivered != 1:
        raise RuntimeError("Invitation email backend did not report a successful delivery")

    with transaction.atomic():
        updated = Invitation.objects.filter(
            pk=invitation.pk,
            sent_at__isnull=True,
            status=Invitation.Status.PENDING,
        ).update(sent_at=timezone.now(), updated_at=timezone.now())
    return bool(updated)
