from django import forms
from django.contrib import admin
from django.contrib import messages
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_tenants.admin import TenantAdminMixin
from unfold.admin import ModelAdmin

from .models import Domain
from .models import Invitation
from .models import Tenant
from .services import send_invitation_notification as send_invitation


class InvitationAdminForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ["tenant", "user", "message", "expires_at"]
        widgets = {"expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"})}

    def clean(self):
        cleaned = super().clean()
        tenant = cleaned.get("tenant")
        user = cleaned.get("user")
        if tenant and user:
            if tenant.user_set.filter(pk=user.pk).exists():
                self.add_error("user", _("This user is already a member of the tenant."))
            elif Invitation.objects.filter(
                tenant=tenant,
                user=user,
                status=Invitation.Status.PENDING,
            ).exclude(pk=self.instance.pk).exists():
                self.add_error("user", _("There is already a pending invitation for this user."))
        return cleaned


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
    form = InvitationAdminForm
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
    readonly_fields = [
        "token",
        "status",
        "invited_by",
        "sent_at",
        "send_count",
        "accepted_at",
        "declined_at",
        "created_at",
        "updated_at",
    ]
    autocomplete_fields = ["tenant", "user"]
    actions = ["send_invitation_notification"]

    @admin.action(description=_("Send invitation notification"))
    def send_invitation_notification(self, request, queryset):
        sent = 0
        skipped = 0
        for invitation in queryset.select_related("tenant", "user", "invited_by"):
            if (
                invitation.status != Invitation.Status.PENDING
                or invitation.expires_at <= timezone.now()
            ):
                skipped += 1
                continue
            try:
                sent += send_invitation(request, invitation)
            except Exception as exc:  # pragma: no cover - email backend dependent
                self.message_user(
                    request,
                    f"Could not send {invitation}: {exc}",
                    level=messages.ERROR,
                )
        if sent:
            self.message_user(
                request,
                _(f"Sent {sent} invitation notification(s)."),
                level=messages.SUCCESS,
            )
        if skipped:
            self.message_user(
                request,
                _(f"Skipped {skipped} non-pending or expired invitation(s)."),
                level=messages.WARNING,
            )

    def save_model(self, request, obj, form, change):
        if not change:
            obj.invited_by = request.user
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        return request.user.is_superuser and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser and super().has_delete_permission(request, obj)
