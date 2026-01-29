import factory

from .. import models


class NotificationFactory(factory.django.DjangoModelFactory):
    user = factory.SubFactory("iam.tests.factories.UserFactory")
    type = factory.Faker("pystr")
    issuer = factory.SubFactory("iam.tests.factories.UserFactory")

    class Meta:
        model = models.Notification
