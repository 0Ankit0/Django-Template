from django.db import models
from django.utils.translation import gettext_lazy as _
from .permissions import Permission
from core.models import BaseModel

class Group(BaseModel):
    name = models.CharField(_('name'), max_length=150, unique=True)
    permissions = models.ManyToManyField(
        Permission,
        verbose_name=_('permissions'),
        blank=True,
    )

    class Meta:
        app_label = 'iam'
        verbose_name = _('group')
        verbose_name_plural = _('groups')

    def __str__(self):
        return self.name

    def natural_key(self):
        return (self.name,)