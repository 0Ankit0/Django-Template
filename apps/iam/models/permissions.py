from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from core.models import BaseModel

class Permission(BaseModel):
    name = models.CharField(_('name'), max_length=255)
    content_type = models.ForeignKey(
        ContentType,
        models.CASCADE,
        verbose_name=_('content type'),
        related_name='iam_permissions',
    )
    codename = models.CharField(_('codename'), max_length=100)

    class Meta:
        app_label = 'iam'
        verbose_name = _('permission')
        verbose_name_plural = _('permissions')
        unique_together = [['content_type', 'codename']]
        ordering = ['content_type__app_label', 'content_type__model', 'codename']

    def __str__(self):
        return '%s | %s' % (self.content_type, self.name)

    def natural_key(self):
        return (self.codename,) + self.content_type.natural_key()
    natural_key.dependencies = ['contenttypes.contenttype']