from django.urls import path

from . import views

app_name = 'content'

urlpatterns = [
    path('documents/', views.DocumentListView.as_view(), name='documents_list'),
    path('documents/upload/', views.DocumentUploadView.as_view(), name='documents_upload'),
    path('documents/<int:pk>/delete/', views.document_delete, name='document_delete'),
    path('products/create/', views.ProductCreateView.as_view(), name='products_create'),
    path('products/', views.ProductListView.as_view(), name='products_list'),
]
