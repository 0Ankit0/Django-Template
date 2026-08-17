from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.utils import timezone
from tenant_users.tenants.models import ExistsError

from django_template.tenants.models import Invitation
from django_template.tenants.models import Tenant
from django_template.tenants.services import send_invitation_notification


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
def test_invitation_notification_records_delivery(user, tenant, settings):
    settings.DEFAULT_FROM_EMAIL = "noreply@example.com"
    settings.TENANT_USERS_DOMAIN = "testserver"
    invitation = Invitation.objects.create(
        tenant=tenant,
        user=user,
        invited_by=tenant.owner,
    )
    request = RequestFactory().get("/tenants/invitations/")

    with patch("django_template.tenants.services.send_mail", return_value=1):
        assert send_invitation_notification(request, invitation) == 1

    invitation.refresh_from_db()
    assert invitation.send_count == 1
    assert invitation.sent_at is not None


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
