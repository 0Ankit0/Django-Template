from rest_framework import viewsets, permissions, serializers
from django.contrib.auth import get_user_model
from iam.models import Group
from ..serializers import (
    CreateUserSerializer, UpdateUserSerializer, ListUserSerializer,
    CreateGroupSerializer, UpdateGroupSerializer, ListGroupSerializer
)

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all().order_by('-created')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self) -> type[serializers.Serializer]: # type: ignore[return]
        if self.action == 'create':
            return CreateUserSerializer
        elif self.action in ['update', 'partial_update']:
            return UpdateUserSerializer
        return ListUserSerializer

class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all().order_by('name')
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self) -> type[serializers.Serializer]: # type: ignore[return]
        if self.action == 'create':
            return CreateGroupSerializer
        elif self.action in ['update', 'partial_update']:
            return UpdateGroupSerializer
        return ListGroupSerializer