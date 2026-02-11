"""Payment API views"""

from rest_framework import viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from django.shortcuts import get_object_or_404
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

from .models import PaymentTransaction, WebhookEvent
from .serializers_payments import (
    PaymentTransactionSerializer,
    InitiatePaymentSerializer,
    VerifyPaymentSerializer,
    PaymentConfigSerializer,
    WebhookEventSerializer,
)
from .gateways.factory import PaymentGatewayFactory


class PaymentTransactionViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for listing and retrieving payment transactions"""
    
    serializer_class = PaymentTransactionSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['gateway', 'status', 'currency']
    search_fields = ['gateway_transaction_id', 'customer_info']
    ordering_fields = ['created_at', 'amount']
    ordering = ['-created_at']
    
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
                        'transaction_id': openapi.Schema(type=openapi.TYPE_STRING, format='uuid'),
                        'payment_url': openapi.Schema(type=openapi.TYPE_STRING, format='uri'),
                        'gateway': openapi.Schema(type=openapi.TYPE_STRING),
                        'amount': openapi.Schema(type=openapi.TYPE_NUMBER),
                        'status': openapi.Schema(type=openapi.TYPE_STRING),
                    }
                )
            ),
            400: "Bad request - validation error",
            500: "Internal server error - gateway error"
        }
    )
    def post(self, request):
        """Initiate a payment with the specified gateway"""
        serializer = InitiatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        data = serializer.validated_data
        gateway_name = data['gateway']
        
        try:
            # Get gateway adapter
            gateway = PaymentGatewayFactory.get_gateway(gateway_name)
            
            # Prepare customer info and metadata
            customer_info = {
                'customer_name': data['customer_name'],
                'customer_email': data['customer_email'],
                'customer_phone': data['customer_phone'],
            }
            
            metadata = {
                'purchase_order_id': data['purchase_order_id'],
                'purchase_order_name': data['purchase_order_name'],
                'return_url': data['return_url'],
                'website_url': data.get('website_url'),
            }
            
            # Initiate payment with gateway
            result = gateway.initiate_payment(
                amount=float(data['amount']),
                currency=data['currency'],
                customer_info=customer_info,
                metadata=metadata
            )
            
            # Create payment transaction record
            transaction = PaymentTransaction.objects.create(
                gateway=gateway_name,
                gateway_transaction_id=result['transaction_id'],
                amount=data['amount'],
                currency=data['currency'],
                status='pending',
                customer_info=customer_info,
                gateway_response=result,
                tenant=request.tenant
            )
            
            return Response({
                'transaction_id': str(transaction.id),
                'payment_url': result['payment_url'],
                'gateway': gateway_name,
                'amount': float(data['amount']),
                'currency': data['currency'],
                'status': 'pending',
            }, status=status.HTTP_201_CREATED)
            
        except ValueError as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({
                'error': f"Payment initiation failed: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class VerifyPaymentView(APIView):
    """API view to verify a payment"""
    
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        request_body=VerifyPaymentSerializer,
        responses={
            200: PaymentTransactionSerializer,
            404: "Transaction not found",
            500: "Verification failed"
        }
    )
    def post(self, request):
        """Verify payment status with the gateway"""
        serializer = VerifyPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        transaction_id = serializer.validated_data['transaction_id']
        
        # Get transaction
        transaction = get_object_or_404(
            PaymentTransaction,
            id=transaction_id,
            tenant=request.tenant
        )
        
        try:
            # Get gateway adapter
            gateway = PaymentGatewayFactory.get_gateway(transaction.gateway)
            
            # Verify payment
            result = gateway.verify_payment(transaction.gateway_transaction_id)
            
            # Update transaction
            transaction.status = result['status']
            transaction.payment_method = result.get('payment_method', '')
            transaction.gateway_response = result
            transaction.save()
            
            return Response(
                PaymentTransactionSerializer(transaction).data,
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response({
                'error': f"Payment verification failed: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PaymentConfigView(APIView):
    """API view to get payment gateway configuration"""
    
    permission_classes = [IsAuthenticated]
    
    @swagger_auto_schema(
        responses={
            200: PaymentConfigSerializer
        }
    )
    def get(self, request):
        """Get enabled payment gateways and their public configuration"""
        gateways_config = {}
        
        for gateway_name, config in settings.PAYMENT_GATEWAYS.items():
            if config.get('enabled', False):
                # Only expose public information
                gateways_config[gateway_name] = {
                    'name': gateway_name.title(),
                    'enabled': True,
                    'live_mode': config.get('live_mode', False),
                    # Don't expose secret keys
                }
                
                # Add public key for Khalti
                if gateway_name == 'khalti' and 'public_key' in config:
                    gateways_config[gateway_name]['public_key'] = config['public_key']
        
        return Response({
            'gateways': gateways_config,
            'enabled_gateways': settings.ENABLED_PAYMENT_GATEWAYS,
        }, status=status.HTTP_200_OK)


class PaymentWebhookView(APIView):
    """API view to handle payment gateway webhooks"""
    
    permission_classes = []  # Webhooks don't require authentication
    
    @swagger_auto_schema(
        manual_parameters=[
            openapi.Parameter(
                'gateway',
                openapi.IN_PATH,
                description="Gateway name (e.g., khalti)",
                type=openapi.TYPE_STRING,
                required=True
            )
        ],
        responses={
            200: "Webhook processed successfully",
            400: "Invalid signature or payload",
            500: "Webhook processing failed"
        }
    )
    def post(self, request, gateway):
        """Process webhook from payment gateway"""
        
        # Create webhook event record
        webhook_event = WebhookEvent.objects.create(
            gateway=gateway,
            event_type='unknown',
            payload=request.data,
            processed=False
        )
        
        try:
            # Get gateway adapter
            gateway_adapter = PaymentGatewayFactory.get_gateway(gateway)
            
            # Process webhook
            result = gateway_adapter.process_webhook(
                payload=request.data,
                headers=request.headers
            )
            
            # Update webhook event
            webhook_event.event_type = result['event_type']
            webhook_event.processed = True
            webhook_event.save()
            
            # Find and update transaction
            transaction = PaymentTransaction.objects.filter(
                gateway=gateway,
                gateway_transaction_id=result['transaction_id']
            ).first()
            
            if transaction:
                transaction.status = result['status']
                transaction.gateway_response = result
                transaction.save()
            
            return Response({
                'status': 'success',
                'message': 'Webhook processed successfully'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            # Log error in webhook event
            webhook_event.error_message = str(e)
            webhook_event.save()
            
            return Response({
                'error': f"Webhook processing failed: {str(e)}"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
