import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


@shared_task
def send_email_task(to_email: str, subject: str, template_name: str, context: dict = None):
    """Send an email using a template."""
    context = context or {}

    try:
        html_content = render_to_string(f"emails/{template_name}.html", context)
        text_content = render_to_string(f"emails/{template_name}.txt", context)

        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to_email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()

        logger.info(f"Email sent to {to_email}: {subject}")
        return {"status": "sent", "to": to_email}
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return {"error": str(e)}


@shared_task
def send_welcome_email(user_id: int):
    """Send welcome email to new user."""
    from users.models import User

    try:
        user = User.objects.get(id=user_id)
        send_email_task.delay(
            to_email=user.email,
            subject="Welcome to E-Commerce Platform",
            template_name="welcome",
            context={"user": {"email": user.email, "first_name": user.first_name}},
        )
        return {"status": "sent", "user_id": user_id}
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {"error": "User not found"}


@shared_task
def send_password_reset_email(user_id: int, reset_token: str):
    """Send password reset email."""
    from users.models import User

    try:
        user = User.objects.get(id=user_id)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"

        send_email_task.delay(
            to_email=user.email,
            subject="Reset Your Password",
            template_name="password_reset",
            context={"user": {"email": user.email}, "reset_url": reset_url},
        )
        return {"status": "sent", "user_id": user_id}
    except User.DoesNotExist:
        logger.error(f"User {user_id} not found")
        return {"error": "User not found"}


@shared_task
def send_tenant_invitation_email(invitation_id: int):
    """Send tenant invitation email."""
    from multitenancy.models import TenantInvitation

    try:
        invitation = TenantInvitation.objects.select_related("tenant", "invited_by").get(id=invitation_id)
        invite_url = f"{settings.FRONTEND_URL}/accept-invitation?token={invitation.token}"

        send_email_task.delay(
            to_email=invitation.email,
            subject=f"You're invited to join {invitation.tenant.name}",
            template_name="tenant_invitation",
            context={
                "tenant_name": invitation.tenant.name,
                "invited_by": invitation.invited_by.email,
                "invite_url": invite_url,
                "role": invitation.role,
            },
        )
        return {"status": "sent", "invitation_id": invitation_id}
    except TenantInvitation.DoesNotExist:
        logger.error(f"Invitation {invitation_id} not found")
        return {"error": "Invitation not found"}
