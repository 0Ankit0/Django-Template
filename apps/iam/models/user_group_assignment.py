"""User Group Assignment Model"""

import uuid

from django.db import models

from core.models import BaseModel

from .group import Group
from .user import User


class UserGroupAssignment(BaseModel):
    """
    Track user-group assignments with metadata.
    Groups contain permissions that grant access to modules and features.
    """

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="group_assignments"
    )
    group = models.ForeignKey(
        Group, on_delete=models.CASCADE, related_name="user_assignments"
    )

    class Meta:
        db_table = "user_group_assignments"
        unique_together = ["user", "group"]
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.email} - {self.group.name}"
