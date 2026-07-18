from django.db import models
from tenant_users.tenants.models import TenantBase

class Client(TenantBase):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateField(auto_now_add=True)

    auto_create_schema = True