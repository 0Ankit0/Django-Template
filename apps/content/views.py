from django.conf import settings
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.acl import policies

from . import models, serializers


class ContentfulWebhook(generics.CreateAPIView):
    permission_classes = (policies.AnyoneFullAccess,)
    serializer_class = serializers.ContentfulWebhookSerializer


class ContentItemViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for reading content items (synced from CMS)."""

    queryset = models.ContentItem.objects.filter(is_published=True)
    serializer_class = serializers.ContentItemSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        queryset = super().get_queryset()
        content_type = self.request.query_params.get("content_type")
        if content_type:
            queryset = queryset.filter(content_type=content_type)
        return queryset

    @action(detail=False, methods=["get"])
    def by_type(self, request):
        """Get content items grouped by content type."""
        content_type = request.query_params.get("type")
        if not content_type:
            return Response({"error": "content_type query parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        items = self.get_queryset().filter(content_type=content_type)
        serializer = self.get_serializer(items, many=True)
        return Response(serializer.data)


class DocumentViewSet(viewsets.ModelViewSet):
    """ViewSet for user documents."""

    serializer_class = serializers.DocumentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return models.Document.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return serializers.DocumentUploadSerializer
        return serializers.DocumentSerializer

    def create(self, request, *args, **kwargs):
        # Check document limit
        current_count = models.Document.objects.filter(user=request.user).count()
        if current_count >= settings.USER_DOCUMENTS_NUMBER_LIMIT:
            return Response(
                {"error": f"Maximum number of documents ({settings.USER_DOCUMENTS_NUMBER_LIMIT}) reached"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().create(request, *args, **kwargs)

    @action(detail=True, methods=["get"])
    def download(self, request, pk=None):
        """Get download URL for document."""
        document = self.get_object()
        return Response(
            {
                "url": request.build_absolute_uri(document.file.url),
                "filename": document.file.name.split("/")[-1],
            }
        )


class PageViewSet(viewsets.ModelViewSet):
    """ViewSet for static pages."""

    serializer_class = serializers.PageSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "slug"

    def get_queryset(self):
        if self.action in ["list", "retrieve"]:
            # Allow public access to published pages
            if not self.request.user.is_authenticated:
                return models.Page.objects.filter(is_published=True)
        return models.Page.objects.all()

    def get_permissions(self):
        if self.action in ["list", "retrieve"]:
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "list":
            return serializers.PageListSerializer
        return serializers.PageSerializer

    @action(detail=False, methods=["get"], url_path="by-slug/(?P<page_slug>[^/.]+)")
    def by_slug(self, request, page_slug=None):
        """Get page by slug."""
        try:
            page = models.Page.objects.get(slug=page_slug, is_published=True)
            serializer = self.get_serializer(page)
            return Response(serializer.data)
        except models.Page.DoesNotExist:
            return Response({"error": "Page not found"}, status=status.HTTP_404_NOT_FOUND)
