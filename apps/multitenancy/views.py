from rest_framework import status, viewsets
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from django.urls import reverse, reverse_lazy
from django.views.generic import FormView, ListView, TemplateView
from . import forms

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import models, serializers
from .services import membership as membership_service


class TenantViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.TenantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return models.Tenant.objects.filter(membership__user=self.request.user).distinct()

    def perform_create(self, serializer):
        tenant = serializer.save(created_by=self.request.user)
        models.TenantMembership.objects.create(
            tenant=tenant, user=self.request.user, role=models.TenantUserRole.OWNER, invitee=self.request.user
        )


class TenantMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.TenantMembershipSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant_id = self.request.query_params.get("tenant_id")
        if tenant_id:
            return models.TenantMembership.objects.filter(
                tenant_id=tenant_id, tenant__membership__user=self.request.user
            )
        return models.TenantMembership.objects.filter(tenant__membership__user=self.request.user)

    @action(detail=True, methods=["delete"])
    def remove(self, request, pk=None):
        membership = self.get_object()
        membership_service.delete_tenant_membership(membership, self.request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class TenantInvitationViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.TenantInvitationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return models.TenantInvitation.objects.filter(
            invitee=self.request.user
        ) | models.TenantInvitation.objects.filter(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def accept(self, request, pk=None):
        invitation = self.get_object()
        result = membership_service.accept_invitation(invitation, request.user)
        return Response(result, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def decline(self, request, pk=None):
        invitation = self.get_object()
        result = membership_service.decline_invitation(invitation, request.user)
        return Response(result, status=status.HTTP_200_OK)


class TenantListView(LoginRequiredMixin, ListView):
    """List user's tenants."""
    template_name = 'tenants/list.html'
    context_object_name = 'memberships'
    login_url = reverse_lazy('iam:login')
    
    def get_queryset(self):
        return models.TenantMembership.objects.filter(
            user=self.request.user
        ).select_related('tenant')


class TenantCreateView(LoginRequiredMixin, FormView):
    """Create a new tenant."""
    template_name = 'tenants/create.html'
    form_class = forms.TenantForm
    success_url = reverse_lazy('multitenancy:list')
    login_url = reverse_lazy('iam:login')
    
    def form_valid(self, form):
        tenant = models.Tenant.objects.create(
            name=form.cleaned_data['name'],
            created_by=self.request.user
        )
        models.TenantMembership.objects.create(
            user=self.request.user,
            tenant=tenant,
            role=models.TenantUserRole.OWNER # Using enum from model if available, else string
        )
        messages.success(self.request, f'Organization "{tenant.name}" created successfully!')
        return super().form_valid(form)


class TenantDetailView(LoginRequiredMixin, TemplateView):
    """Tenant detail view."""
    template_name = 'tenants/detail.html'
    login_url = reverse_lazy('iam:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        tenant_id = self.kwargs.get('pk')
        
        membership = get_object_or_404(
            models.TenantMembership,
            tenant_id=tenant_id,
            user=self.request.user
        )
        
        context['tenant'] = membership.tenant
        context['membership'] = membership
        context['members'] = models.TenantMembership.objects.filter(
            tenant=membership.tenant
        ).select_related('user')
        context['invitation_form'] = forms.TenantInvitationForm()
        
        return context


class TenantInviteView(LoginRequiredMixin, FormView):
    """Invite a member to a tenant."""
    template_name = 'tenants/invite.html'
    form_class = forms.TenantInvitationForm
    login_url = reverse_lazy('iam:login')
    
    def get_success_url(self):
        return reverse('multitenancy:detail', kwargs={'pk': self.kwargs.get('pk')})
    
    def form_valid(self, form):
        tenant_id = self.kwargs.get('pk')
        membership = get_object_or_404(
            models.TenantMembership,
            tenant_id=tenant_id,
            user=self.request.user
        )
        
        email = form.cleaned_data['email']
        role = form.cleaned_data['role']
        
        models.TenantInvitation.objects.create(
            tenant=membership.tenant,
            email=email,
            role=role,
            created_by=self.request.user
        )
        
        messages.success(self.request, f'Invitation sent to {email}!')
        return super().form_valid(form)


@login_required
def switch_tenant(request, tenant_id):
    tenant = get_object_or_404(models.Tenant, id=tenant_id)
    if not tenant.members.filter(user=request.user).exists():
        messages.error(request, 'You are not a member of this tenant.')
        return redirect('core:dashboard')
    
    request.session['tenant_id'] = str(tenant.id)
    messages.success(request, f'Switched to {tenant.name}')
    return redirect('core:dashboard')
