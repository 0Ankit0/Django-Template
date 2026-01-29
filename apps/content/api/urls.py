from django.urls import include, path
from rest_framework.routers import DefaultRouter
from . import views

app_name = 'content_api'

router = DefaultRouter()
router.register(r"items", views.ContentItemViewSet, basename="content_items")
router.register(r"documents", views.DocumentViewSet, basename="documents")
router.register(r"pages", views.PageViewSet, basename="page")

urlpatterns = [
    path("webhooks/contentful/", views.ContentfulWebhook.as_view(), name="contentful_webhook"),
]
urlpatterns += router.urls
