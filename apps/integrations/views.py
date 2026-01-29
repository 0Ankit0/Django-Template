from rest_framework import serializers, status, views
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
