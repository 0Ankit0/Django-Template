from io import BytesIO

from django.core.files.base import ContentFile
from django.db import models
from django.utils.translation import gettext as _
from PIL import Image
from rest_framework.exceptions import ValidationError


class ImageWithThumbnailMixin:
    FILE_FORMATS = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "gif": "GIF", "webp": "WEBP"}

    def make_thumbnail(self):
        image = Image.open(self.original)
        image.thumbnail(self.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

        file_name = self.original.name.split("/")[-1]
        extension = self.original.name.split(".")[-1]
        file_format = self.FILE_FORMATS.get(extension.lower())
        if not file_format:
            raise ValidationError({self.ERROR_FIELD_NAME: [_("Unsupported image file format.")]})

        temp_thumbnail = BytesIO()
        image.save(temp_thumbnail, file_format)
        temp_thumbnail.seek(0)

        self.thumbnail.save(file_name, ContentFile(temp_thumbnail.read()), save=False)
        temp_thumbnail.close()

    def save(self, *args, **kwargs):
        if self.original:
            self.make_thumbnail()
        super().save(*args, **kwargs)