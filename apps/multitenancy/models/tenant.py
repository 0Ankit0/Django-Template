import hashid_field
from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models import Q, UniqueConstraint
from django.utils.text import slugify

from core.models import BaseModel

from .. import constants
from ..managers import TenantManager


class Tenant(BaseModel):
    """
    Represents a tenant within the application.

    Fields:
    - id: A unique identifier for the tenant.
    - created_by: The user who created the tenant.
    - name: The name of the tenant.
    - slug: A URL-friendly version of the name.
    - type: The type of the tenant.
    - billing_email: Address used for billing purposes and it is provided to Stripe
    - members: Many-to-many relationship with users through TenantMembership.

    Methods:
    - save: Overrides the default save method to ensure unique slug generation based on the name field.

    Initialization:
    - __original_name: Private attribute to track changes to the name field during the instance's lifecycle.

    Slug Generation:
    - The save method ensures the generation of a unique slug for the tenant. If the name is modified or the slug is
      not provided, it generates a slug based on the name. In case of a name collision, a counter is appended to the
      base slug to ensure uniqueness.
    """

    name: str = models.CharField(max_length=100, unique=False)
    slug: str = models.SlugField(max_length=100, unique=True)
    type: str = models.CharField(choices=constants.TenantType.choices)
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="TenantMembership",
        related_name="tenants",
        blank=True,
        through_fields=("tenant", "user"),
    )
    billing_email = models.EmailField(
        db_collation="case_insensitive",
        verbose_name="billing email address",
        max_length=255,
        unique=False,
        blank=True,
    )

    objects = TenantManager()

    MAX_SAVE_ATTEMPTS = 10

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        counter = 0
        while counter < self.MAX_SAVE_ATTEMPTS:
            try:
                with transaction.atomic():
                    if not counter:
                        self.slug = slugify(self.name)
                    else:
                        self.slug = f"{slugify(self.name)}-{counter}"
                    super().save(*args, **kwargs)
                    break
            except IntegrityError as e:
                if "duplicate key" in str(e).lower():
                    counter += 1
                else:
                    raise e

    @property
    def email(self):
        return self.billing_email if self.billing_email else self.created_by.email

    @property
    def owners_count(self):
        """
        Calculate the total number of tenant owners for this tenant.
        Returns the count of tenant owners.
        """
        return self.members.filter(tenant_memberships__role=constants.TenantUserRole.OWNER).count()

    @property
    def owners(self):
        """
        Returns the list of Users with an owner role.
        """
        return self.members.filter(tenant_memberships__role=constants.TenantUserRole.OWNER).all()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_name = self.name