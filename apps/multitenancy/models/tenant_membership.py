import hashid_field
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models import Q, UniqueConstraint
from django.utils.text import slugify

from core.models import BaseModel

from .. import constants
from ..managers import TenantMembershipManager
from . import Tenant


class TenantMembership(BaseModel):
    """
    Represents the membership of a user in a tenant. As well accepted as not accepted (invitations).

    Fields:
    - id: A unique identifier for the membership.
    - user: The user associated with the membership.
    - role: The role of the user in the tenant. Can be owner, admin or member.
    - tenant: The tenant to which the user belongs.
    - is_accepted: Indicates whether the membership invitation is accepted.
    - invitation_accepted_at: Timestamp when the invitation was accepted.
    - invitee_email_address: The email address of the invited user if not connected to an existing user.

    Constraints:
    - unique_non_null_user_and_tenant: Ensures the uniqueness of non-null user and tenant combinations.
    - unique_non_null_user_and_invitee_email_address: Ensures the uniqueness of non-null user and invitee email address
      combinations.
    """

    # User - Tenant connection fields
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tenant_memberships", null=True
    )
    role = models.CharField(choices=constants.TenantUserRole.choices, default=constants.TenantUserRole.OWNER)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="user_memberships")

    # Invitation connected fields
    is_accepted = models.BooleanField(default=False)
    invitation_accepted_at = models.DateTimeField(null=True)
    invitee_email_address = models.EmailField(
        # db_collation="case_insensitive",
        verbose_name="invitee email address",
        max_length=255,
        default="",
    )

    objects = TenantMembershipManager()

    class Meta:
        constraints = [
            UniqueConstraint(
                name="unique_non_null_user_and_tenant", fields=["user", "tenant"], condition=Q(user__isnull=False)
            ),
            UniqueConstraint(
                name="unique_non_null_user_and_invitee_email_address",
                fields=["invitee_email_address", "tenant"],
                condition=~Q(invitee_email_address__exact=""),
            ),
        ]

    def __str__(self):
        return f"{self.user.email} {self.tenant.name} {self.role}"
