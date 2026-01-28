import uuid
import hashid_field
from django.db import models
from django.conf import settings
from django.utils import timezone

class DeleteQuerySet(models.QuerySet):
    """QuerySet for delete"""
    def delete(self, user=None):
        return self.update(is_active=False, deleted_at=timezone.now(), deleted_by=user)

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

class PublishedQuerySet(models.QuerySet):
    """QuerySet for publish"""
    def published(self):
        return self.filter(is_published=True)

    def publish(self, user=None):
        return self.update(is_published=True, published_at=timezone.now(), published_by=user)

    def unpublish(self, user=None):
        return self.update(is_published=False, published_at=None, published_by=user)

class BaseQuerySet(DeleteQuerySet, PublishedQuerySet):
    """Combines all custom QuerySets"""
    pass

class BaseManager(models.Manager.from_queryset(BaseQuerySet)):
    """Base Manager for all models"""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)

class BaseModel(models.Model):
    id = hashid_field.HashidAutoField(primary_key=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_%(class)s_set', null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='updated_%(class)s_set', null=True, blank=True)

    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='deleted_%(class)s_set')

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True, related_name='published_%(class)s_set')

    objects = BaseManager()

    def delete(self, user=None):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save()

    def hard_delete(self, using=None, keep_parents=False):
        return super().delete(using=using, keep_parents=keep_parents)

    def publish(self, user=None):
        self.is_published = True
        self.published_at = timezone.now()
        self.published_by = user
        self.save()

    def unpublish(self, user=None):
        self.is_published = False
        self.published_at = None
        self.published_by = user
        self.save()

    class Meta:
        abstract = True



        
