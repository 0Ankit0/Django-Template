from django.contrib import admin
from unfold.admin import ModelAdmin
from django_tenants.admin import TenantAdminMixin

from .models import Domain
from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "schema_name", "owner", "created", "modified"]
    search_fields = ["name", "schema_name", "owner__email"]


@admin.register(Domain)
class DomainAdmin(ModelAdmin):
    list_display = ["domain", "tenant", "is_primary"]
    search_fields = ["domain", "tenant__name", "tenant__schema_name"]
