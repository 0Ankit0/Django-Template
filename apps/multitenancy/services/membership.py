from django.contrib.auth import get_user_model

from ..constants import TenantUserRole
from ..models import Tenant, TenantMembership
from ..notifications import TenantInvitationEmail, send_tenant_invitation_notification
from ..tokens import tenant_invitation_token

User = get_user_model()


def create_tenant_membership(
    tenant: Tenant,
    user: User = None,
    created_by: User = None,
    invitee_email_address: str = "",
    role: TenantUserRole = TenantUserRole.MEMBER,
    is_accepted: bool = False,
):
    membership = TenantMembership.objects.create(
        user=user,
        tenant=tenant,
        role=role,
        invitee_email_address=invitee_email_address,
        is_accepted=is_accepted,
        created_by=created_by,
    )
    if not is_accepted:
        token = tenant_invitation_token.make_token(
            user_email=invitee_email_address if invitee_email_address else user.email, tenant_membership=membership
        )
        # Use the membership ID directly instead of GraphQL global ID
        tenant_membership_id = str(membership.id)
        TenantInvitationEmail(
            to=user.email if user else invitee_email_address,
            data={"tenant_membership_id": tenant_membership_id, "token": token},
        ).send()

        if user:
            send_tenant_invitation_notification(membership, tenant_membership_id, token)

    return membership
