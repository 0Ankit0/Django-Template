from django.db import models
from core.models import BaseModel


class Role(BaseModel):
    """
    Role model for user role assignment
    """

    name = models.CharField(max_length=100, unique=True)
    hierarchy_level = models.IntegerField(default=0)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def can_assign_role(self, target_role):
        """Check if this role can assign target_role"""
        return self.hierarchy_level >= target_role.hierarchy_level
