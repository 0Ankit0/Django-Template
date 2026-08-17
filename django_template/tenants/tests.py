from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from tenant_users.tenants.models import ExistsError

from django_template.tenants.email import InvitationEmailAdapter
from django_template.tenants.models import Invitation
from django_template.tenants.models import Tenant
from django_template.tenants.services import create_invitation
from django_template.tenants.services import send_invitation_notification
from django_template.tenants.tasks import send_invitation_email


@pytest.fixture
def tenant(_public_tenant):
    return Tenant.objects.get(schema_name="public")


@pytest.mark.django_db
def test_invitation_acceptance_grants_membership(user, tenant):
    invitation = Invitation.objects.create(
        tenant=tenant,
        user=user,
        invited_by=tenant.owner,
    )

    with patch.object(tenant, "add_user") as add_user:
        invitation.accept()

    add_user.assert_called_once_with(user)
    invitation.refresh_from_db()
    assert invitation.status == Invitation.Status.ACCEPTED
    assert invitation.accepted_at is not None


@pytest.mark.django_db
def test_expired_invitation_cannot_be_accepted(user, tenant):
    invitation = Invitation.objects.create(
        tenant=tenant,
        user=user,
        invited_by=tenant.owner,
        expires_at=timezone.now() - timedelta(minutes=1),
    )

    with pytest.raises(ValidationError, match="expired"):
        invitation.accept()

    invitation.refresh_from_db()
    assert invitation.status == Invitation.Status.EXPIRED


@pytest.mark.django_db
def test_invitation_notification_is_queued_without_count(user, tenant):
    invitation = Invitation.objects.create(
        tenant=tenant,
        user=user,
        invited_by=tenant.owner,
    )

    with patch("django_template.tenants.tasks.send_invitation_email.delay") as delay:
        assert send_invitation_notification(None, invitation) is None

    delay.assert_called_once_with(invitation.pk)
    invitation.refresh_from_db()
    assert invitation.sent_at is None
    assert not hasattr(invitation, "send_count")


@pytest.mark.django_db
def test_invitation_email_task_records_delivery(user, tenant):
    invitation = Invitation.objects.create(
        tenant=tenant,
        user=user,
        invited_by=tenant.owner,
    )

    with patch.object(InvitationEmailAdapter, "send_mail", return_value=1) as send_mail:
        assert send_invitation_email.run(invitation.pk) is True

    send_mail.assert_called_once()
    invitation.refresh_from_db()
    assert invitation.sent_at is not None


@pytest.mark.django_db
def test_invitation_email_uses_allauth_style_templates(user, tenant, settings):
    settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
    invitation = Invitation.objects.create(
        tenant=tenant,
        user=user,
        invited_by=tenant.owner,
    )

    with patch("django_template.tenants.email.render_to_string") as render:
        render.side_effect = ["Invitation to join Acme\n", "<p>HTML</p>", "TEXT"]
        message = InvitationEmailAdapter().render_mail(
            user.email,
            {
                "invitation": invitation,
                "tenant": tenant,
                "user": user,
                "invited_by": tenant.owner,
                "invitation_url": "https://example.com/tenants/invitations/token/",
                "expires_at": invitation.expires_at,
                "message": "Hello",
            },
        )

    assert message.subject == f"Invitation to join {tenant.name}"
    assert message.to == [user.email]
    assert message.alternatives[0][0] == "<p>HTML</p>"
    assert message.body == "TEXT"


@pytest.mark.django_db
def test_new_invitation_cancels_previous_pending_and_creates_new_row(user, tenant):
    first = create_invitation(tenant=tenant, user=user, invited_by=tenant.owner)
    second = create_invitation(tenant=tenant, user=user, invited_by=tenant.owner)

    first.refresh_from_db()
    second.refresh_from_db()
    assert first.pk != second.pk
    assert first.status == Invitation.Status.CANCELED
    assert second.status == Invitation.Status.PENDING
    assert Invitation.objects.filter(tenant=tenant, user=user).count() == 2


@pytest.mark.django_db
def test_invitation_handles_existing_membership(user, tenant):
    invitation = Invitation.objects.create(
        tenant=tenant,
        user=user,
        invited_by=tenant.owner,
    )

    with patch.object(tenant, "add_user", side_effect=ExistsError("already linked")):
        with pytest.raises(ValidationError, match="already a member"):
            invitation.accept()
