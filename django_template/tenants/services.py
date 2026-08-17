from django.conf import settings
from django.core.mail import send_mail
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
    """Send an invitation email and record notification delivery metadata."""
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
        now = timezone.now()
        invitation.sent_at = now
        invitation.send_count += 1
        invitation.save(update_fields=["sent_at", "send_count", "updated_at"])
    return sent
