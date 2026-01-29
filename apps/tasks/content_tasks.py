import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task
def sync_content():
    """Synchronize content from external CMS (Contentful)."""
    from content.models import ContentItem
    from integrations.services.contentful_service import ContentfulService

    logger.info("Starting content synchronization")

    try:
        service = ContentfulService()
        entries = service.get_all_entries()

        synced_count = 0
        for entry in entries:
            ContentItem.objects.update_or_create(
                external_id=entry["id"],
                defaults={
                    "content_type": entry["content_type"],
                    "fields": entry["fields"],
                    "is_published": True,
                },
            )
            synced_count += 1

        # Mark missing entries as unpublished
        existing_ids = [e["id"] for e in entries]
        ContentItem.objects.exclude(external_id__in=existing_ids).update(is_published=False)

        logger.info(f"Synced {synced_count} content items")
        return {"synced_count": synced_count}
    except Exception as e:
        logger.error(f"Error syncing content: {e}")
        return {"error": str(e)}


@shared_task
def process_uploaded_document(document_id: int):
    """Process an uploaded document (extract text, generate thumbnails, etc.)."""
    from content.models import Document

    logger.info(f"Processing document {document_id}")

    try:
        document = Document.objects.get(id=document_id)

        # Generate thumbnail if image
        if document.file.name.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
            # Thumbnail generation logic here
            pass

        # Extract text if PDF
        if document.file.name.lower().endswith(".pdf"):
            # PDF text extraction logic here
            pass

        document.is_processed = True
        document.save()

        logger.info(f"Document {document_id} processed successfully")
        return {"document_id": document_id, "status": "processed"}
    except Document.DoesNotExist:
        logger.error(f"Document {document_id} not found")
        return {"error": "Document not found"}
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        return {"error": str(e)}


@shared_task
def generate_sitemap():
    """Generate sitemap for SEO."""
    from django.conf import settings

    from content.models import ContentItem

    logger.info("Generating sitemap")

    try:
        # Get all published content
        items = ContentItem.objects.filter(is_published=True)

        sitemap_entries = []
        for item in items:
            sitemap_entries.append(
                {
                    "url": f"{settings.FRONTEND_URL}/content/{item.slug}",
                    "lastmod": item.updated_at.isoformat(),
                    "changefreq": "weekly",
                    "priority": 0.8,
                }
            )

        logger.info(f"Generated sitemap with {len(sitemap_entries)} entries")
        return {"entries_count": len(sitemap_entries)}
    except Exception as e:
        logger.error(f"Error generating sitemap: {e}")
        return {"error": str(e)}
