import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class ContentfulService:
    """Service for interacting with Contentful CMS."""

    def __init__(self):
        try:
            import contentful

            self.space_id = getattr(settings, "CONTENTFUL_SPACE_ID", None)
            self.access_token = getattr(settings, "CONTENTFUL_ACCESS_TOKEN", None)
            self.environment = getattr(settings, "CONTENTFUL_ENVIRONMENT", "master")

            if self.space_id and self.access_token:
                self.client = contentful.Client(self.space_id, self.access_token, environment=self.environment)
            else:
                self.client = None
                logger.warning("Contentful credentials not configured")
        except ImportError:
            self.client = None
            logger.warning("contentful package not installed")

    def is_configured(self) -> bool:
        """Check if Contentful is properly configured."""
        return self.client is not None

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        """Get a single entry by ID."""
        if not self.is_configured():
            return None

        try:
            entry = self.client.entry(entry_id)
            return self._serialize_entry(entry)
        except Exception as e:
            logger.error(f"Error fetching entry {entry_id}: {e}")
            return None

    def get_entries(self, content_type: str, limit: int = 100, skip: int = 0) -> list[dict[str, Any]]:
        """Get entries by content type."""
        if not self.is_configured():
            return []

        try:
            entries = self.client.entries(
                {
                    "content_type": content_type,
                    "limit": limit,
                    "skip": skip,
                }
            )
            return [self._serialize_entry(entry) for entry in entries]
        except Exception as e:
            logger.error(f"Error fetching entries: {e}")
            return []

    def get_all_entries(self) -> list[dict[str, Any]]:
        """Get all entries from Contentful."""
        if not self.is_configured():
            return []

        try:
            all_entries = []
            skip = 0
            limit = 1000

            while True:
                entries = self.client.entries({"skip": skip, "limit": limit, "include": 0})
                if not entries:
                    break
                all_entries.extend([self._serialize_entry(entry) for entry in entries])
                skip += limit

                if len(entries) < limit:
                    break

            return all_entries
        except Exception as e:
            logger.error(f"Error fetching all entries: {e}")
            return []

    def get_content_types(self) -> list[dict[str, Any]]:
        """Get all content types."""
        if not self.is_configured():
            return []

        try:
            content_types = self.client.content_types()
            return [
                {
                    "id": ct.id,
                    "name": ct.name,
                    "description": getattr(ct, "description", ""),
                    "fields": [
                        {
                            "id": f.id,
                            "name": f.name,
                            "type": f.type,
                            "required": getattr(f, "required", False),
                        }
                        for f in ct.fields
                    ],
                }
                for ct in content_types
            ]
        except Exception as e:
            logger.error(f"Error fetching content types: {e}")
            return []

    def _serialize_entry(self, entry) -> dict[str, Any]:
        """Serialize a Contentful entry to a dictionary."""
        import contentful

        fields = {}
        for field_name, field_value in entry.fields().items():
            if isinstance(field_value, contentful.Link):
                fields[field_name] = {"id": field_value.id, "type": "Link"}
            elif isinstance(field_value, contentful.Asset):
                fields[field_name] = {
                    "id": field_value.id,
                    "url": f"https:{field_value.url()}" if hasattr(field_value, "url") else None,
                    "type": "Asset",
                }
            elif isinstance(field_value, list):
                fields[field_name] = [self._serialize_value(v) for v in field_value]
            else:
                fields[field_name] = field_value

        return {
            "id": entry.id,
            "content_type": entry.content_type.id,
            "fields": fields,
            "created_at": entry.sys.get("created_at"),
            "updated_at": entry.sys.get("updated_at"),
        }

    def _serialize_value(self, value) -> Any:
        """Serialize a single value."""
        import contentful

        if isinstance(value, contentful.Link):
            return {"id": value.id, "type": "Link"}
        elif isinstance(value, contentful.Asset):
            return {
                "id": value.id,
                "url": f"https:{value.url()}" if hasattr(value, "url") else None,
                "type": "Asset",
            }
        return value
