"""Icon Model - FontAwesome Icons"""

import hashid_field

from django.db import models


class Icon(models.Model):
    """
    Icon model to store FontAwesome icons with metadata.
    Populated from fontawesome.min.css
    """

    id = hashid_field.HashidAutoField(primary_key=True)
    library = models.CharField(
        max_length=50,
        default="fontawesome",
        help_text="Icon library name (e.g., 'fontawesome')",
    )
    name = models.CharField(
        max_length=100, help_text="Icon class name (e.g., 'fa-users')"
    )
    display_name = models.CharField(
        max_length=150, help_text="Human-readable icon name (e.g., 'Users')"
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Icon category (e.g., 'people', 'business')",
    )
    unicode_char = models.CharField(
        max_length=10, blank=True, help_text="Unicode character for the icon"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "icons"
        ordering = ["display_name"]
        indexes = [
            models.Index(fields=["library"]),
            models.Index(fields=["name"]),
            models.Index(fields=["library", "name"]),
            models.Index(fields=["category"]),
        ]
        unique_together = ("library", "name")

    def __str__(self):
        return f"{self.display_name} ({self.library}:{self.name})"
