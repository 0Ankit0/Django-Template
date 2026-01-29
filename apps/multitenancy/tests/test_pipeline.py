import pytest

from ..constants import TenantType
from ..models import Tenant
from ..pipeline import create_default_tenant

pytestmark = pytest.mark.django_db


class TestCreateTenantPipeline:
    def test_create_default_tenant_user_and_is_new(self, user):
        create_default_tenant(user=user, is_new=True)
        tenant_exists = Tenant.objects.filter(created_by=user, type=TenantType.DEFAULT).exists()
        assert tenant_exists

    def test_create_default_tenant_user_not_new(self, user):
        count_before = Tenant.objects.filter(created_by=user, type=TenantType.DEFAULT).count()
        create_default_tenant(user=user, is_new=False)
        count_after = Tenant.objects.filter(created_by=user, type=TenantType.DEFAULT).count()
        assert count_before == count_after

    def test_create_default_tenant_no_user(self):
        create_default_tenant(user=None, is_new=True)
        tenant_exists = Tenant.objects.exists()
        assert not tenant_exists
