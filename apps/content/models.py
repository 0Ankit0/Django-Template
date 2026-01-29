import hashid_field
from django.conf import settings
from django.db import models
from django.utils.text import slugify


class ContentfulAbstractModel(models.Model):
    id = models.CharField(max_length=64, primary_key=True)
    fields = models.JSONField(default=dict)

    # is_published is set to False both for unpublished and deleted items
    # to avoid unwanted cascade deletion
    is_published = models.BooleanField(default=False)

    class Meta:
        abstract = True


class DemoItem(ContentfulAbstractModel):
    def __str__(self):
        return self.fields["title"]


class ContentItem(models.Model):
    """Generic content item synced from external CMS."""

    id = hashid_field.HashidAutoField(primary_key=True)
    external_id = models.CharField(max_length=64, unique=True)
    content_type = models.CharField(max_length=64, db_index=True)
    slug = models.SlugField(max_length=255, blank=True)

    fields = models.JSONField(default=dict)
    is_published = models.BooleanField(default=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["content_type", "is_published"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug and "title" in self.fields:
            self.slug = slugify(self.fields["title"])[:255]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.fields.get("title", str(self.id))


class Document(models.Model):
    """User-uploaded document."""

    id = hashid_field.HashidAutoField(primary_key=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to="documents/%Y/%m/")
    file_type = models.CharField(max_length=50, blank=True)
    file_size = models.PositiveIntegerField(default=0)

    is_processed = models.BooleanField(default=False)
    extracted_text = models.TextField(blank=True)
    thumbnail = models.ImageField(upload_to="documents/thumbnails/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.file:
            self.file_size = self.file.size
            if not self.file_type:
                self.file_type = self.file.name.split(".")[-1].lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class Page(models.Model):
    """Static page content."""

    id = hashid_field.HashidAutoField(primary_key=True)
    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    content = models.TextField()
    meta_description = models.CharField(max_length=255, blank=True)

    is_published = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title
