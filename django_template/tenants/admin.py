from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_tenants.admin import TenantAdminMixin
from unfold.admin import ModelAdmin

from .models import Domain
from .models import Invitation
from .models import Tenant
from .services import send_invitation_notification


@admin.register(Tenant)
class TenantAdmin(TenantAdminMixin, ModelAdmin):
    list_display = ["name", "schema_name", "owner", "created", "modified"]
    search_fields = ["name", "schema_name", "owner__email"]


@admin.register(Domain)
class DomainAdmin(ModelAdmin):
    list_display = ["domain", "tenant", "is_primary"]
    search_fields = ["domain", "tenant__name", "tenant__schema_name"]


@admin.register(Invitation)
class InvitationAdmin(ModelAdmin):
    list_display = [
        "tenant",
        "user",
        "invited_by",
        "status",
        "expires_at",
        "sent_at",
        "send_count",
    ]
    list_filter = ["status", "tenant"]
    search_fields = ["tenant__name", "user__email", "invited_by__email"]
    readonly_fields = ["token", "sent_at", "send_count", "accepted_at", "declined_at", "created_at", "updated_at"]
    autocomplete_fields = ["tenant", "user", "invited_by"]
    actions = ["send_invitation_notification"]

    @admin.action(description=_("Send invitation notification"))
    def send_invitation_notification(self, request, queryset):
        sent = 0
        skipped = 0
        for invitation in queryset.select_related("tenant", "user", "invited_by"):
            if invitation.status != Invitation.Status.PENDING or invitation.expires_at <= timezone.now():
                skipped += 1
                continue
            try:
                sent += send_invitation_notification(request, invitation)
            except Exception as exc:  # pragma: no cover - email backend dependent
                self.message_user(request, f"Could not send {invitation}: {exc}", level=messages.ERROR)
        if sent:
            self.message_user(request, _(f"Sent {sent} invitation notification(s)."), level=messages.SUCCESS)
        if skipped:
            self.message_user(request, _(f"Skipped {skipped} non-pending or expired invitation(s)."), level=messages.WARNING)

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)
