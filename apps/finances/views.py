from djstripe import models as djstripe_models
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import serializers


class PaymentIntentViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.PaymentIntentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        customer, _ = djstripe_models.Customer.get_or_create(self.request.tenant)
        return djstripe_models.PaymentIntent.objects.filter(customer=customer)


class SetupIntentViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.SetupIntentSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post"]

    def get_queryset(self):
        customer, _ = djstripe_models.Customer.get_or_create(self.request.tenant)
        return djstripe_models.SetupIntent.objects.filter(customer=customer)


class PaymentMethodViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.PaymentMethodSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "delete"]

    def get_queryset(self):
        customer, _ = djstripe_models.Customer.get_or_create(self.request.tenant)
        return djstripe_models.PaymentMethod.objects.filter(customer=customer)

    @action(detail=True, methods=["post"])
    def set_default(self, request, pk=None):
        payment_method = self.get_object()
        serializer = serializers.UpdateDefaultPaymentMethodSerializer(
            payment_method, data={}, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Default payment method updated"}, status=status.HTTP_200_OK)


class SubscriptionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = serializers.SubscriptionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        customer, _ = djstripe_models.Customer.get_or_create(self.request.tenant)
        return djstripe_models.Subscription.objects.filter(customer=customer)


class SubscriptionScheduleViewSet(viewsets.ModelViewSet):
    serializer_class = serializers.TenantSubscriptionScheduleSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        customer, _ = djstripe_models.Customer.get_or_create(self.request.tenant)
        return djstripe_models.SubscriptionSchedule.objects.filter(customer=customer)

    @action(detail=True, methods=["post"], serializer_class=serializers.CancelTenantActiveSubscriptionSerializer)
    def cancel(self, request, pk=None):
        schedule = self.get_object()
        serializer = self.get_serializer(schedule, data={})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"message": "Subscription cancelled"}, status=status.HTTP_200_OK)
