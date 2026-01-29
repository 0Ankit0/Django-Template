from django.urls import path
from . import views

app_name = 'integrations_api'

urlpatterns = [
    path("openai/ideas/", views.OpenAIIdeaGeneratorView.as_view(), name="openai_ideas"),
]
