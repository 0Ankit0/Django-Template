from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"items", views.ContentItemViewSet, basename="content-items")
router.register(r"documents", views.DocumentViewSet, basename="documents")
router.register(r"pages", views.PageViewSet, basename="pages")

urlpatterns = [
    path("contentful-hook/", views.ContentfulWebhook.as_view(), name="contentful-webhook"),
    path("", include(router.urls)),
]
