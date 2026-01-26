from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.utils.translation import gettext_lazy as _
from core.models import BaseModel
from django.contrib.auth.models import Permission as BasePermissionModel

class Permission(BasePermissionModel):
    pass

    class Meta:
        app_label = 'iam'
        verbose_name = _('permission')
        verbose_name_plural = _('permissions')

    def __str__(self):
        return '%s | %s' % (self.content_type, self.name)
