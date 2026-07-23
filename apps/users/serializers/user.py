from rest_framework import serializers
from apps.users.models import TenantUser

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantUser
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'date_joined')

