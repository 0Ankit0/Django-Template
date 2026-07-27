from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from django_tenants.utils import get_public_schema_name

from django_template.tenants.models import Domain
from django_template.tenants.models import Tenant
from django_template.users.models import User
from django_template.users.tests.factories import UserFactory

if TYPE_CHECKING:
    from django_template.users.models import User


@pytest.fixture(autouse=True)
def _media_storage(settings, tmpdir) -> None:
    settings.MEDIA_ROOT = tmpdir.strpath


@pytest.fixture
def user(db) -> User:
    return UserFactory.create()


@pytest.fixture(autouse=True)
def _public_tenant(db) -> None:
    public_schema = get_public_schema_name()
    if Tenant.objects.filter(schema_name=public_schema).exists():
        return

    owner = User(email="public-owner@example.com", is_active=True, is_verified=True)
    owner.set_password("password")
    owner.save()

    tenant = Tenant(schema_name=public_schema, name="Public", owner=owner)
    tenant.save()
    Domain.objects.get_or_create(
        tenant=tenant,
        domain="testserver",
        defaults={"is_primary": True},
    )
