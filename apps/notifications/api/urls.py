from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'notifications_api'

router = DefaultRouter()
router.register(r"", views.NotificationViewSet, basename="app")

urlpatterns = router.urls
