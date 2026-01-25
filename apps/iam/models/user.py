import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from .groups import Group
from .permissions import Permission
from core.models import BaseModel

class User(AbstractUser,BaseModel):
    groups = models.ManyToManyField(
        Group,
        verbose_name='groups',
        blank=True,
        help_text='The groups this user belongs to. A user will get all permissions granted to each of their groups.',
        related_name="user_set",
        related_query_name="user",
    )
    user_permissions = models.ManyToManyField(
        Permission,
        verbose_name='user permissions',
        blank=True,
        help_text='Specific permissions for this user.',
        related_name="user_set",
        related_query_name="user",
    )
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        db_table = 'auth_user'