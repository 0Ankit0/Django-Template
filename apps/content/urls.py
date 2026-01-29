from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"items", views.ContentItemViewSet, basename="content-items")
router.register(r"documents", views.DocumentViewSet, basename="documents")
router.register(r"pages", views.PageViewSet, basename="page")

urlpatterns = [
    path("webhooks/contentful/", views.ContentfulWebhook.as_view(), name="contentful-webhook"),
]
urlpatterns += router.urls

urlpatterns += [
    path('documents/', views.DocumentListView.as_view(), name='document_list'),
    path('documents/upload/', views.DocumentUploadView.as_view(), name='document_upload'),
    path('documents/<int:pk>/delete/', views.document_delete, name='document_delete'),
    path('products/', views.ProductListView.as_view(), name='product_list'),
]
