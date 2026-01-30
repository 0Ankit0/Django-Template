from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .. import models, serializers
from ..services import membership as membership_service


class TenantViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.TenantSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return models.Tenant.objects.filter(user_memberships__user=self.request.user).distinct()

    def perform_create(self, serializer):
        tenant = serializer.save(created_by=self.request.user)
        models.TenantMembership.objects.create(
            tenant=tenant, user=self.request.user, role=models.TenantUserRole.OWNER, invitee=self.request.user
        )

    @action(detail=True, methods=["post"])
    def switch(self, request, pk=None):
        tenant = self.get_object()
        # Ensure user is a member (get_queryset handles this largely, but explicit check doesn't hurt)
        if not models.TenantMembership.objects.filter(tenant=tenant, user=request.user).exists():
            return Response({"detail": "You are not a member of this tenant."}, status=status.HTTP_403_FORBIDDEN)
        
        request.session['tenant_id'] = str(tenant.id)
        return Response({"detail": f"Switched to {tenant.name}", "tenant_id": str(tenant.id)})


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
