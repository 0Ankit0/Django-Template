from rest_framework import serializers, status, views
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .openai.client import OpenAIClient
from .openai.exceptions import OpenAIClientException


class OpenAIIdeaGeneratorSerializer(serializers.Serializer):
    keywords = serializers.ListField(child=serializers.CharField(max_length=100), min_length=1, max_length=10)


class OpenAIIdeaGeneratorView(views.APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = OpenAIIdeaGeneratorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = OpenAIClient.get_saas_ideas(serializer.validated_data["keywords"])
            return Response({"ideas": result.dict()}, status=status.HTTP_200_OK)
        except OpenAIClientException as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class SaaSIdeasView(LoginRequiredMixin, TemplateView):
    """AI SaaS Ideas Generator."""
    template_name = 'integrations/ai_ideas.html'
    login_url = reverse_lazy('iam:login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pass empty form or previous data
        return context
    
    def post(self, request, *args, **kwargs):
        prompt = request.POST.get('keywords', '')
        context = self.get_context_data(**kwargs)
        context['keywords'] = prompt
        
        if not prompt:
            messages.error(request, "Please enter some keywords.")
            return self.render_to_response(context)
            
        try:
            # from apps.integrations.openai.client import OpenAIClient # Already imported at top
            
            # Split keywords
            keywords_list = [k.strip() for k in prompt.split(',') if k.strip()]
            
            # Call OpenAI service
            result = OpenAIClient.get_saas_ideas(keywords_list)
            
            # Pydantic model to dict
            context['ideas'] = result.ideas if hasattr(result, 'ideas') else []
            
        except Exception as e:
            messages.error(request, f"Error generating ideas: {str(e)}")
            
        return self.render_to_response(context)

