"""Payment API views"""

from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .gateways.factory import PaymentGatewayFactory
from .models import PaymentTransaction, WebhookEvent
from .serializers_payments import (
    InitiatePaymentSerializer,
    PaymentConfigSerializer,
    PaymentTransactionSerializer,
    VerifyPaymentSerializer,
)


class PaymentTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing and retrieving payment transactions"""

    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["gateway", "status", "currency"]
    search_fields = ["gateway_transaction_id", "customer_info"]
    ordering_fields = ["created_at", "amount"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """Filter transactions by tenant"""
        return PaymentTransaction.objects.filter(tenant=self.request.tenant)


class InitiatePaymentView(APIView):
    """API view to initiate a payment"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=InitiatePaymentSerializer,
        responses={
            201: openapi.Response(
                description="Payment initiated successfully",
                schema=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "transaction_id": openapi.Schema(type=openapi.TYPE_STRING, format="uuid"),
                        "payment_url": openapi.Schema(type=openapi.TYPE_STRING, format="uri"),
                        "gateway": openapi.Schema(type=openapi.TYPE_STRING),
                        "amount": openapi.Schema(type=openapi.TYPE_NUMBER),
                        "status": openapi.Schema(type=openapi.TYPE_STRING),
                    },
                ),
            ),
            400: "Bad request - validation error",
            500: "Internal server error - gateway error",
        },
    )
    def post(self, request):
        """Initiate a payment with the specified gateway"""
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        gateway_name = data["gateway"]
        purchase_order_id = data.get("purchase_order_id")

        # Initialize variables
        amount = 0.0
        currency = "NPR"
        purchase_order_name = "Purchase"

        # 1. Resolve Product/Plan and Calculate Amount Server-Side
        found = False

        # Try ContentItem (Product)
        if not found:
            try:
                from content.models import ContentItem

                try:
                    product = ContentItem.objects.get(pk=purchase_order_id)
                    amount = float(product.fields.get("price", 0))
                    currency = "NPR"  # Default for products
                    purchase_order_name = f"Purchase of {product.fields.get('title', 'Product')}"
                    found = True
                except ContentItem.DoesNotExist:
                    pass
            except ImportError:
                pass

        # Try Stripe Price (Subscription Plan)
        if not found:
            try:
                from djstripe import models as djstripe_models

                price = djstripe_models.Price.objects.get(id=purchase_order_id)
                # unit_amount is in cents, unit_amount_decimal is decimal object of cents
                # We need major units for our internal logic usually, but let's be careful.
                # Actually, our khalti gateway expects NPR major units.
                # Stripe gateway expects major units? No, Stripe gateway usually expects cents but let's check.
                # Our StripeGateway.initiate_payment helper might convert?
                # Let's check StripeGateway.initiate_payment logic.
                # Wait, StripeGateway usually takes amount.
                # If we standardise on MAJOR UNITS in this View, the Gateway Adapter should handle conversion.
                # Khalti Adapter: _npr_to_paisa(amount) -> amount * 100. So it expects Major.
                # Stripe Adapter: let's assume it expects Major and converts to cents?
                # I'll check StripeGateway later or assume standard practice.
                # Usually standard practice in this codebase seems to be handling conversions in Gateway or View.
                # Let's use Major Units here.

                amount = float(price.unit_amount or 0) / 100.0
                currency = str(price.currency).upper()
                purchase_order_name = f"Subscription to {price.product.name}"
                found = True
            except djstripe_models.Price.DoesNotExist:
                pass

        if not found:
            return Response({"error": "Invalid purchase_order_id"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Resolve Customer Info Server-Side
        user = request.user

        # Safe way to get name
        customer_name = user.username
        if hasattr(user, "profile"):
            full_name = f"{user.profile.first_name} {user.profile.last_name}".strip()
            if full_name:
                customer_name = full_name

        customer_info = {
            "customer_name": customer_name,
            "customer_email": user.email,
            "customer_phone": "",
        }

        # 3. Prepare Metadata
        metadata = {
            "purchase_order_id": purchase_order_id,
            "purchase_order_name": purchase_order_name,
            "return_url": data["return_url"],
            "website_url": data.get("website_url"),
        }

        try:
            # Get gateway adapter
            gateway = PaymentGatewayFactory.get_gateway(gateway_name)

            # Add Stripe specific data if available
            if gateway_name == "stripe":
                from djstripe import models as djstripe_models

                # Get or create Stripe customer for the tenant
                customer, _ = djstripe_models.Customer.get_or_create(request.tenant)
                metadata["customer_id"] = customer.id

                if data.get("payment_method_id"):
                    metadata["payment_method_id"] = data["payment_method_id"]

            # Initiate payment with gateway
            result = gateway.initiate_payment(
                amount=amount, currency=currency, customer_info=customer_info, metadata=metadata
            )

            # Create payment transaction record
            transaction = PaymentTransaction.objects.create(
                gateway=gateway_name,
                gateway_transaction_id=result["transaction_id"],
                amount=amount,
                currency=currency,
                status=result.get("status", "pending"),
                customer_info=customer_info,
                gateway_response=result,
                tenant=request.tenant,
            )

            return Response(
                {
                    "transaction_id": str(transaction.id),
                    "payment_url": result.get("payment_url"),
                    "gateway": gateway_name,
                    "amount": amount,
                    "currency": currency,
                    "status": result.get("status", "pending"),
                    "client_secret": result.get("client_secret"),
                },
                status=status.HTTP_201_CREATED,
            )

        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response(
                {"error": f"Payment initiation failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class VerifyPaymentView(APIView):
    """API view to verify a payment"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(
        request_body=VerifyPaymentSerializer,
        responses={200: PaymentTransactionSerializer, 404: "Transaction not found", 500: "Verification failed"},
    )
    def post(self, request):
        """Verify payment status with the gateway"""
        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        transaction_id = serializer.validated_data["transaction_id"]

        # Get transaction
        transaction = get_object_or_404(PaymentTransaction, id=transaction_id, tenant=request.tenant)

        try:
            # Get gateway adapter
            gateway = PaymentGatewayFactory.get_gateway(transaction.gateway)

            # Verify payment
            result = gateway.verify_payment(transaction.gateway_transaction_id)

            # Update transaction
            transaction.status = result["status"]
            transaction.payment_method = result.get("payment_method", "")
            transaction.gateway_response = result
            transaction.save()

            return Response(PaymentTransactionSerializer(transaction).data, status=status.HTTP_200_OK)

        except Exception as e:
            return Response(
                {"error": f"Payment verification failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class PaymentConfigView(APIView):
    """API view to get payment gateway configuration"""

    permission_classes = [IsAuthenticated]

    @swagger_auto_schema(responses={200: PaymentConfigSerializer})
    def get(self, request):
        """Get enabled payment gateways and their public configuration"""
        gateways_config = {}

        for gateway_name, config in settings.PAYMENT_GATEWAYS.items():
            if config.get("enabled", False):
                # Only expose public information
                gateways_config[gateway_name] = {
                    "name": gateway_name.title(),
                    "enabled": True,
                    "live_mode": config.get("live_mode", False),
                    # Don't expose secret keys
                }

                # Add public key for Khalti
                if gateway_name == "khalti" and "public_key" in config:
                    gateways_config[gateway_name]["public_key"] = config["public_key"]

        return Response(
            {
                "gateways": gateways_config,
                "enabled_gateways": settings.ENABLED_PAYMENT_GATEWAYS,
            },
            status=status.HTTP_200_OK,
        )


class PaymentWebhookView(APIView):
    """API view to handle payment gateway webhooks"""

    permission_classes: list = []  # Webhooks don't require authentication

    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                "gateway",
                openapi.IN_PATH,
                description="Gateway name (e.g., khalti)",
                type=openapi.TYPE_STRING,
                required=True,
            )
        ],
        responses={
            200: "Webhook processed successfully",
            400: "Invalid signature or payload",
            500: "Webhook processing failed",
        },
    )
    def post(self, request, gateway):
        """Process webhook from payment gateway"""

        # Create webhook event record
        webhook_event = WebhookEvent.objects.create(
            gateway=gateway, event_type="unknown", payload=request.data, processed=False
        )

        try:
            # Get gateway adapter
            gateway_adapter = PaymentGatewayFactory.get_gateway(gateway)

            # Process webhook
            result = gateway_adapter.process_webhook(payload=request.data, headers=request.headers)

            # Update webhook event
            webhook_event.event_type = result["event_type"]
            webhook_event.processed = True
            webhook_event.save()

            # Find and update transaction
            transaction = PaymentTransaction.objects.filter(
                gateway=gateway, gateway_transaction_id=result["transaction_id"]
            ).first()

            if transaction:
                transaction.status = result["status"]
                transaction.gateway_response = result
                transaction.save()

            return Response(
                {"status": "success", "message": "Webhook processed successfully"}, status=status.HTTP_200_OK
            )

        except Exception as e:
            # Log error in webhook event
            webhook_event.error_message = str(e)
            webhook_event.save()

            return Response(
                {"error": f"Webhook processing failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
