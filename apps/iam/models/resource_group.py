"""Resource Group Model - Module Definition with Permissions"""

import uuid

from .permissions import Permission
from django.db import models

from apps.core.models.base import BaseModel

# Using string reference for Icon to avoid circular import from apps.core.models


class ResourceGroup(BaseModel):
    """
    Resource group representing a module with its permissions, display settings,
    and configuration. Each module in the system should have a corresponding resource group.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Module identifier (e.g., 'library', 'students')",
    )
    display_name = models.CharField(
        max_length=150, help_text="Human-readable module name"
    )
    description = models.TextField(
        blank=True, help_text="Module description shown to users"
    )

    # Module display settings
    icon = models.ForeignKey(
        "core.Icon",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="FontAwesome icon",
    )
    color = models.CharField(
        max_length=20,
        default="primary",
        help_text="Color theme (e.g., 'primary', 'blue')",
    )
    url = models.CharField(max_length=200, blank=True, help_text="Module base URL")
    app_name = models.CharField(max_length=100, help_text="Django app name")

    # Module settings
    order = models.IntegerField(default=0, help_text="Display order on dashboard")
    requires_organization = models.BooleanField(
        default=True, help_text="If module respects organization hierarchy"
    )

    # Permissions associated with this module
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="resource_groups",
        help_text="Django permissions associated with this module",
    )

    class Meta:
        db_table = "resource_groups"
        ordering = ["order", "display_name"]

    def __str__(self):
        return self.display_name
