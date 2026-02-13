from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import TemplateView
from django.views.generic.edit import FormView
from djstripe import models as djstripe_models
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import serializers
from .forms import PlanCreationForm


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


class FinancesView(LoginRequiredMixin, TemplateView):
    """Finances overview."""

    template_name = "finances/index.html"
    login_url = reverse_lazy("iam:login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get available plans
        context["plans"] = djstripe_models.Product.objects.filter(active=True).prefetch_related("prices")

        return context


class PaymentMethodsView(LoginRequiredMixin, TemplateView):
    """Manage payment methods."""

    template_name = "finances/payment_methods.html"
    login_url = reverse_lazy("iam:login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get enabled gateways from settings
        context["payment_gateways"] = settings.PAYMENT_GATEWAYS

        # Check if this is a plan subscription
        plan_id = self.request.GET.get("plan")
        if plan_id:
            try:
                price = djstripe_models.Price.objects.get(id=plan_id)
                context["selected_plan"] = price
                context["selected_product"] = price.product
            except djstripe_models.Price.DoesNotExist:
                pass

        # Check if this is a product purchase
        product_id = self.request.GET.get("product_id")

        if product_id:
            try:
                from content.models import ContentItem

                try:
                    content_item = ContentItem.objects.get(pk=product_id)

                    context["is_product_purchase"] = True
                    context["product_purchase"] = {
                        "id": str(content_item.pk),  # HashID to string
                        "name": content_item.fields.get("title", "Product"),
                        "amount": content_item.fields.get("price", 0),
                        "currency": "NPR",  # Default currency for products
                    }
                except ContentItem.DoesNotExist:
                    pass
            except ImportError:
                pass

        # Get saved payment methods
        context["payment_methods"] = []
        if getattr(self.request, "tenant", None):
            customer, _ = djstripe_models.Customer.get_or_create(self.request.tenant)
            context["payment_methods"] = djstripe_models.PaymentMethod.objects.filter(
                customer=customer, type="card"
            ).order_by("-created")
        context["stripe_public_key"] = (
            settings.STRIPE_LIVE_PUBLIC_KEY if settings.STRIPE_LIVE_MODE else settings.STRIPE_TEST_PUBLIC_KEY
        )

        return context


class SubscriptionView(LoginRequiredMixin, TemplateView):
    """Subscription management."""

    template_name = "finances/subscription.html"
    login_url = reverse_lazy("iam:login")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Fetch active products with their prices
        context["plans"] = djstripe_models.Product.objects.filter(active=True).prefetch_related("prices")
        return context


class AddPlanView(LoginRequiredMixin, FormView):
    template_name = "finances/add_plan.html"
    form_class = PlanCreationForm
    success_url = reverse_lazy("finances:index")
    login_url = reverse_lazy("iam:login")

    def form_valid(self, form):
        try:
            form.save()
            return super().form_valid(form)
        except Exception as e:
            form.add_error(None, str(e))
            return self.form_invalid(form)
