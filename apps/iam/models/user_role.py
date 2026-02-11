import uuid

from django.db import models

from core.models import BaseModel

from .role import Role
from .user import User


class UserRole(BaseModel):
    """
    User-Role assignment
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="user_roles")
    role = models.ForeignKey(Role, on_delete=models.CASCADE)

    class Meta:
        db_table = "user_roles"
        unique_together = ["user", "role"]

    def __str__(self):
        return f"{self.user.username} - {self.role.name}"
