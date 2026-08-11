from django.urls import path

from . import views

app_name = "controlroom_sentry"

urlpatterns = [
    path("", views.index, name="index"),
    path("integrations/", views.integrations, name="integrations"),
    path("issues/", views.issues, name="issues"),
    path("issues/<str:issue_id>/", views.issue_detail, name="issue_detail"),
    path("test-event/", views.test_event, name="test_event"),
]
