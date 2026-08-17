from django.conf import settings
from django.core.mail import send_mail
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
        base = f"{request.scheme}://{public_domain}"
    return f"{base}{path}"


def send_invitation_notification(request, invitation: Invitation) -> int:
    """Send one invitation email without mutating invitation count state."""
    url = invitation_url(request, invitation)
    subject = f"Invitation to join {invitation.tenant.name}"
    body = (
        f"You have been invited to join {invitation.tenant.name}.\n\n"
        f"Accept the invitation: {url}\n\n"
        f"This invitation expires on {invitation.expires_at:%Y-%m-%d %H:%M %Z}.\n"
    )
    if invitation.message:
        body += f"\nMessage from {invitation.invited_by}:\n{invitation.message}\n"
    sent = send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [invitation.user.email],
        fail_silently=False,
    )
    if sent:
        invitation.sent_at = timezone.now()
        invitation.save(update_fields=["sent_at", "updated_at"])
    return sent


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
