from django.urls import path

from . import views

urlpatterns = [
    path("openai/ideas/", views.OpenAIIdeaGeneratorView.as_view(), name="openai-ideas"),
    path('ai-ideas/', views.SaaSIdeasView.as_view(), name='ai_ideas'),
]
