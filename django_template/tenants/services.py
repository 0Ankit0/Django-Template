from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import Invitation


def invitation_url(request, invitation: Invitation) -> str:
    path = reverse("tenants:invitation-accept", kwargs={"token": invitation.token})
    public_domain = settings.TENANT_USERS_DOMAIN
    if "://" in public_domain:
        base = public_domain.rstrip("/")
    else:
        scheme = request.scheme if request is not None else "https"
        base = f"{scheme}://{public_domain}"
    return f"{base}{path}"


def queue_invitation_notification(invitation: Invitation) -> None:
    """Queue invitation delivery after the current transaction commits."""
    from .tasks import send_invitation_email

    transaction.on_commit(lambda: send_invitation_email.delay(invitation.pk))


def send_invitation_notification(request, invitation: Invitation) -> None:
    """Backward-compatible entry point that queues, rather than sends, mail."""
    queue_invitation_notification(invitation)


@transaction.atomic
def create_invitation(*, tenant, user, invited_by, message="", expires_at=None):
    """Create a new invitation row, invalidating any older pending invitation."""
    Invitation.objects.filter(
        tenant=tenant,
        user=user,
        status=Invitation.Status.PENDING,
    ).update(status=Invitation.Status.CANCELED, updated_at=timezone.now())
    invitation = Invitation(
        tenant=tenant,
        user=user,
        invited_by=invited_by,
        message=message,
    )
    if expires_at is not None:
        invitation.expires_at = expires_at
    invitation.save()
    return invitation
