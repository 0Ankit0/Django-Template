from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

from .models import Invitation
from .models import Tenant


User = get_user_model()


class OrganizationCreateForm(forms.ModelForm):
    class Meta:
        model = Tenant
        fields = ["name", "slug"]
        labels = {"slug": _("Subdomain")}
        help_texts = {"slug": _("Used as <subdomain>.<tenant domain>.")}

    def __init__(self, *args, owner=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner
        self.fields["slug"].required = False

    def clean_slug(self):
        value = self.cleaned_data.get("slug") or self.cleaned_data.get("name")
        value = slugify(value)
        if not value:
            raise forms.ValidationError(_("Enter a valid organization name or subdomain."))
        schema_name = value.replace("-", "_")[:63]
        if (
            Tenant.objects.filter(slug=value).exists()
            or Tenant.objects.filter(schema_name=schema_name).exists()
        ):
            raise forms.ValidationError(_("That subdomain is already in use."))
        return value

    @transaction.atomic
    def save(self, commit=True):
        tenant = super().save(commit=False)
        tenant.owner = self.owner
        tenant.schema_name = self.cleaned_data["slug"].replace("-", "_")[:63]
        if commit:
            tenant.save()
            tenant.add_user(self.owner, is_superuser=True)
        return tenant


class InvitationForm(forms.ModelForm):
    class Meta:
        model = Invitation
        fields = ["user", "message", "expires_at"]
        widgets = {
            "expires_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, tenant=None, invited_by=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.invited_by = invited_by
        self.fields["user"].queryset = User.objects.filter(is_active=True).exclude(tenants=tenant)

    def clean_user(self):
        user = self.cleaned_data["user"]
        if self.tenant.user_set.filter(pk=user.pk).exists():
            raise forms.ValidationError(_("This user is already a member of the organization."))
        if Invitation.objects.filter(
            tenant=self.tenant,
            user=user,
            status=Invitation.Status.PENDING,
        ).exists():
            raise forms.ValidationError(_("There is already a pending invitation for this user."))
        return user

    def save(self, commit=True):
        invitation = super().save(commit=False)
        invitation.tenant = self.tenant
        invitation.invited_by = self.invited_by
        if commit:
            invitation.save()
        return invitation
