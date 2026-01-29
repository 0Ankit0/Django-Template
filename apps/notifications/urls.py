from django.urls import path

from . import views

app_name = 'notifications'

urlpatterns = [
    path('notifications/', views.NotificationListView.as_view(), name='list'),
    path('notifications/<int:pk>/read/', views.mark_notification_read, name='mark_read'),
    path('notifications/read-all/', views.mark_all_notifications_read, name='mark_all_read'),
]
