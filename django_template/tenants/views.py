from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_tenants.utils import get_public_schema_name

from .forms import InvitationForm
from .forms import OrganizationCreateForm
from .models import Invitation
from .models import Tenant
from .services import send_invitation_notification


def _public_domain_redirect(request, tenant: Tenant):
    domain = tenant.domains.filter(is_primary=True).first()
    if not domain:
        return redirect("users:redirect")
    return redirect(f"{request.scheme}://{domain.domain}")


@login_required
def create_organization(request):
    if request.tenant.schema_name != get_public_schema_name():
        raise Http404
    if request.method == "POST":
        form = OrganizationCreateForm(request.POST, owner=request.user)
        if form.is_valid():
            with transaction.atomic():
                tenant = form.save()
                base_domain = str(getattr(request, "tenant", None) and request.tenant.domains.first().domain or "")
                host = request.get_host().split(":", 1)[0]
                root_domain = host if host in {"localhost", "127.0.0.1"} else request.get_host().split(":", 1)[0]
                if "." in root_domain and not root_domain.endswith(".localhost"):
                    root_domain = root_domain.split(".", 1)[-1]
                if not base_domain:
                    base_domain = root_domain
                domain_name = f"{tenant.slug}.{base_domain}"
                tenant.domains.create(domain=domain_name, is_primary=True)
            messages.success(request, _("Organization created successfully."))
            return _public_domain_redirect(request, tenant)
    else:
        form = OrganizationCreateForm(owner=request.user)
    return render(request, "tenants/organization_form.html", {"form": form})


@login_required
def invite_user(request):
    tenant = request.tenant
    if tenant.schema_name == get_public_schema_name() or tenant.owner_id != request.user.id:
        raise Http404
    if request.method == "POST":
        form = InvitationForm(request.POST, tenant=tenant, invited_by=request.user)
        if form.is_valid():
            invitation = form.save()
            try:
                send_invitation_notification(request, invitation)
            except Exception:
                invitation.delete()
                messages.error(request, _("The invitation could not be sent. Please try again."))
            else:
                messages.success(request, _("Invitation sent."))
                return redirect("tenants:invite-user")
    else:
        form = InvitationForm(tenant=tenant, invited_by=request.user)
    return render(
        request,
        "tenants/invite_user.html",
        {"form": form, "tenant": tenant},
    )


@login_required
def resend_invitation(request, token):
    invitation = get_object_or_404(Invitation, token=token)
    if invitation.tenant.owner_id != request.user.id and not request.user.is_superuser:
        raise Http404
    if invitation.status != Invitation.Status.PENDING:
        messages.error(request, _("Only pending invitations can be resent."))
        return redirect("users:redirect")
    if invitation.is_expired:
        invitation.status = Invitation.Status.EXPIRED
        invitation.save(update_fields=["status", "updated_at"])
        messages.error(request, _("This invitation has expired."))
        return redirect("users:redirect")
    send_invitation_notification(request, invitation)
    messages.success(request, _("Invitation notification sent again."))
    return redirect("users:redirect")


@login_required
def invitation_accept(request, token):
    invitation = get_object_or_404(Invitation.objects.select_related("tenant", "user"), token=token)
    if invitation.user_id != request.user.id:
        raise Http404
    if request.method == "POST":
        try:
            invitation.accept()
        except ValidationError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(request, _(f"You joined {invitation.tenant.name}."))
            return _public_domain_redirect(request, invitation.tenant)
    return render(request, "tenants/invitation_accept.html", {"invitation": invitation})


@login_required
def invitation_decline(request, token):
    if request.method != "POST":
        raise Http404
    invitation = get_object_or_404(Invitation, token=token)
    if invitation.user_id != request.user.id:
        raise Http404
    try:
        invitation.decline()
    except ValidationError as exc:
        messages.error(request, exc.message)
    else:
        messages.info(request, _("Invitation declined."))
    return redirect("users:redirect")
