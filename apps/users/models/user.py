from tenant_users.tenants.models import UserProfile
from django.db import models

class TenantUser(UserProfile):
    name = models.CharField(max_length=200)