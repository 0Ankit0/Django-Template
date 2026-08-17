from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_tenants.models import DomainMixin
from tenant_users.tenants.models import ExistsError
from tenant_users.tenants.models import TenantBase


def default_invitation_expiry():
    return timezone.now() + timedelta(days=7)
