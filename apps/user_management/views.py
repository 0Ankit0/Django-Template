from rest_framework import viewsets, permissions
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from .serializers import UserSerializer, GroupSerializer

User = get_user_model()

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all().order_by('name')
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


def get_test_view(request):
    from django.http import JsonResponse
    return JsonResponse({'message': 'This is a test view'})
