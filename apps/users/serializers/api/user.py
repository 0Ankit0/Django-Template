from rest_framework import viewsets
from apps.users.models import TenantUser
from apps.users.serializers.user import UserSerializer

class UserViewSet(viewsets.ModelViewSet):
    queryset = TenantUser.objects.all()
    serializer_class = UserSerializer
