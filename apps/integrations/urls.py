from django.urls import path

from . import views

app_name = 'integrations'

urlpatterns = [
    path('ai-ideas/', views.SaaSIdeasView.as_view(), name='ai_ideas'),
]
