from django.conf import settings
from rest_framework import serializers

from . import models, tasks


class ContentfulWebhookSerializer(serializers.Serializer):
    def create(self, obj):
        sync_task = tasks.ContentfulSync("complete")
        sync_task.apply()
        return {}


class ContentItemSerializer(serializers.ModelSerializer):
    """Serializer for ContentItem model."""

    class Meta:
        model = models.ContentItem
        fields = ["id", "external_id", "content_type", "slug", "fields", "is_published", "created_at", "updated_at"]
        read_only_fields = ["id", "external_id", "created_at", "updated_at"]


class DocumentSerializer(serializers.ModelSerializer):
    """Serializer for Document model."""

    file_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()

    class Meta:
        model = models.Document
        fields = [
            "id",
            "title",
            "file",
            "file_url",
            "file_type",
            "file_size",
            "is_processed",
            "thumbnail_url",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "file_type", "file_size", "is_processed", "thumbnail_url", "created_at", "updated_at"]

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None

    def get_thumbnail_url(self, obj):
        if obj.thumbnail:
            request = self.context.get("request")
            if request:
                return request.build_absolute_uri(obj.thumbnail.url)
            return obj.thumbnail.url
        return None

    def validate_file(self, value):
        if value.size > settings.UPLOADED_DOCUMENT_SIZE_LIMIT:
            raise serializers.ValidationError(
                f"File size exceeds the limit of {settings.UPLOADED_DOCUMENT_SIZE_LIMIT / (1024*1024):.0f}MB"
            )
        return value


class DocumentUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploading documents."""

    class Meta:
        model = models.Document
        fields = ["title", "file"]

    def validate_file(self, value):
        if value.size > settings.UPLOADED_DOCUMENT_SIZE_LIMIT:
            raise serializers.ValidationError(
                f"File size exceeds the limit of {settings.UPLOADED_DOCUMENT_SIZE_LIMIT / (1024*1024):.0f}MB"
            )
        return value

    def create(self, validated_data):
        validated_data["user"] = self.context["request"].user
        document = super().create(validated_data)
        # Trigger async processing
        from tasks.content_tasks import process_uploaded_document

        process_uploaded_document.delay(document.id)
        return document


class PageSerializer(serializers.ModelSerializer):
    """Serializer for Page model."""

    class Meta:
        model = models.Page
        fields = [
            "id",
            "slug",
            "title",
            "content",
            "meta_description",
            "is_published",
            "created_at",
            "updated_at",
            "published_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class PageListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for page listings."""

    class Meta:
        model = models.Page
        fields = ["id", "slug", "title", "is_published", "updated_at"]
