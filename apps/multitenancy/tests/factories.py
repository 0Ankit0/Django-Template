import factory

from .. import constants, models


class TenantFactory(factory.django.DjangoModelFactory):
    created_by = factory.SubFactory("iam.tests.factories.UserFactory")
    type = factory.Iterator(constants.TenantType.values)
    name = factory.Faker("pystr")
    slug = factory.Faker("pystr")
    billing_email = factory.Faker("email")
    created_at = factory.Faker("date_time")
    updated_at = factory.Faker("date_time")

    class Meta:
        model = models.Tenant


class TenantMembershipFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory("iam.tests.factories.UserFactory")
    created_by = factory.SubFactory("iam.tests.factories.UserFactory")
    tenant = factory.SubFactory(TenantFactory)
    role = factory.Iterator(constants.TenantUserRole.values)
    created_at = factory.Faker("date_time")
    updated_at = factory.Faker("date_time")
    is_accepted = True

    class Meta:
        model = models.TenantMembership
