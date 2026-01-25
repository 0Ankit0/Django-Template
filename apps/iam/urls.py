from rest_framework.routers import DefaultRouter
from .views import UserViewSet

router = DefaultRouter()

app_name = 'users'

# Api Views
router.register(r'users', UserViewSet, basename='user')
urlpatterns = router.urls


# Web Views
from django.urls import path, include
from .views import get_test_view

urlpatterns += [
    path('test/', get_test_view, name='test_view'),
]
