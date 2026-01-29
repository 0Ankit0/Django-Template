from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"", views.NotificationViewSet, basename="app")

urlpatterns = router.urls

urlpatterns += [
    path('notifications/', views.NotificationListView.as_view(), name='list'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='read_all'),
]
