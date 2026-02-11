"""API tests for payment gateway endpoints"""

import json
from decimal import Decimal
from unittest.mock import Mock, patch
from uuid import uuid4

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

from multitenancy.models import Tenant
from ..models import PaymentTransaction, WebhookEvent

User = get_user_model()


class TestInitiatePaymentView(TestCase):
    """Test payment initiation endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            email='test@tenant.com',
            subdomain='test'
        )
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            tenant=self.tenant
        )
        self.url = reverse('payment-initiate', host='api')

    @patch('finances.gateways.khalti_gateway.KhaltiGateway.initiate_payment')
    def test_initiate_payment_success(self, mock_initiate):
        """Test successful payment initiation"""
        mock_initiate.return_value = {
            'payment_url': 'https://khalti.com/payment/abc123',
            'transaction_id': 'test_pidx_123',
            'expires_at': '2026-02-11T12:00:00Z',
            'expires_in': 3600,
        }
        
        self.client.force_authenticate(self.user)
        
        data = {
            'gateway': 'khalti',
            'amount': '1000.00',
            'currency': 'NPR',
            'purchase_order_id': 'order_123',
            'purchase_order_name': 'Test Order',
            'customer_name': 'Test User',
            'customer_email': 'test@example.com',
            'customer_phone': '9800000000',
            'return_url': 'https://example.com/return',
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['payment_url'], 'https://khalti.com/payment/abc123')
        self.assertIn('transaction_id', response.data)
        self.assertEqual(response.data['gateway'], 'khalti')
        self.assertEqual(response.data['status'], 'pending')
        
        # Verify transaction was created
        self.assertTrue(PaymentTransaction.objects.filter(
            gateway='khalti',
            gateway_transaction_id='test_pidx_123',
            tenant=self.tenant
        ).exists())

    def test_initiate_payment_unauthenticated(self):
        """Test payment initiation without authentication"""
        data = {
            'gateway': 'khalti',
            'amount': '1000.00',
            'currency': 'NPR',
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_initiate_payment_missing_fields(self):
        """Test payment initiation with missing required fields"""
        self.client.force_authenticate(self.user)
        
        data = {
            'gateway': 'khalti',
            'amount': '1000.00',
            # Missing required fields
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('finances.gateways.khalti_gateway.KhaltiGateway.initiate_payment')
    def test_initiate_payment_gateway_error(self, mock_initiate):
        """Test payment initiation when gateway returns error"""
        mock_initiate.side_effect = Exception("Gateway error")
        
        self.client.force_authenticate(self.user)
        
        data = {
            'gateway': 'khalti',
            'amount': '1000.00',
            'currency': 'NPR',
            'purchase_order_id': 'order_123',
            'purchase_order_name': 'Test Order',
            'customer_name': 'Test User',
            'customer_email': 'test@example.com',
            'customer_phone': '9800000000',
            'return_url': 'https://example.com/return',
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)


class TestVerifyPaymentView(TestCase):
    """Test payment verification endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            email='test@tenant.com',
            subdomain='test'
        )
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            tenant=self.tenant
        )
        self.url = reverse('payment-verify', host='api')

    @patch('finances.gateways.khalti_gateway.KhaltiGateway.verify_payment')
    def test_verify_payment_success(self, mock_verify):
        """Test successful payment verification"""
        transaction = PaymentTransaction.objects.create(
            gateway='khalti',
            gateway_transaction_id='test_pidx_123',
            amount=Decimal('1000.00'),
            currency='NPR',
            status='pending',
            tenant=self.tenant
        )
        
        mock_verify.return_value = {
            'status': 'completed',
            'amount': 1000.00,
            'currency': 'NPR',
            'payment_method': 'khalti',
        }
        
        self.client.force_authenticate(self.user)
        
        data = {
            'transaction_id': str(transaction.id),
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        
        # Verify transaction was updated
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, 'completed')

    def test_verify_payment_not_found(self):
        """Test verifying non-existent transaction"""
        self.client.force_authenticate(self.user)
        
        data = {
            'transaction_id': str(uuid4()),
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_verify_payment_unauthenticated(self):
        """Test payment verification without authentication"""
        data = {
            'transaction_id': str(uuid4()),
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch('finances.gateways.khalti_gateway.KhaltiGateway.verify_payment')
    def test_verify_payment_tenant_isolation(self, mock_verify):
        """Test that users can only verify their own tenant's transactions"""
        tenant2 = Tenant.objects.create(
            name='Other Tenant',
            email='other@tenant.com',
            subdomain='other'
        )
        
        transaction = PaymentTransaction.objects.create(
            gateway='khalti',
            gateway_transaction_id='test_pidx_123',
            amount=Decimal('1000.00'),
            currency='NPR',
            status='pending',
            tenant=tenant2  # Different tenant
        )
        
        self.client.force_authenticate(self.user)
        
        data = {
            'transaction_id': str(transaction.id),
        }
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TestPaymentTransactionViewSet(TestCase):
    """Test payment transaction list endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            email='test@tenant.com',
            subdomain='test'
        )
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            tenant=self.tenant
        )
        self.url = reverse('payment-transaction-list', host='api')

    def test_list_transactions_authenticated(self):
        """Test listing payment transactions"""
        for i in range(3):
            PaymentTransaction.objects.create(
                gateway='khalti',
                gateway_transaction_id=f'test_{i}',
                amount=Decimal('1000.00'),
                currency='NPR',
                status='pending',
                tenant=self.tenant
            )
        
        self.client.force_authenticate(self.user)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)

    def test_list_transactions_filter_by_gateway(self):
        """Test filtering transactions by gateway"""
        PaymentTransaction.objects.create(
            gateway='khalti',
            gateway_transaction_id='test_1',
            amount=Decimal('1000.00'),
            currency='NPR',
            status='pending',
            tenant=self.tenant
        )
        PaymentTransaction.objects.create(
            gateway='stripe',
            gateway_transaction_id='test_2',
            amount=Decimal('1000.00'),
            currency='USD',
            status='pending',
            tenant=self.tenant
        )
        
        self.client.force_authenticate(self.user)
        
        response = self.client.get(self.url, {'gateway': 'khalti'})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)

    def test_list_transactions_tenant_isolation(self):
        """Test that users only see their tenant's transactions"""
        tenant2 = Tenant.objects.create(
            name='Other Tenant',
            email='other@tenant.com',
            subdomain='other'
        )
        
        for i in range(2):
            PaymentTransaction.objects.create(
                gateway='khalti',
                gateway_transaction_id=f'test_tenant1_{i}',
                amount=Decimal('1000.00'),
                currency='NPR',
                status='pending',
                tenant=self.tenant
            )
        
        for i in range(3):
            PaymentTransaction.objects.create(
                gateway='khalti',
                gateway_transaction_id=f'test_tenant2_{i}',
                amount=Decimal('1000.00'),
                currency='NPR',
                status='pending',
                tenant=tenant2
            )
        
        self.client.force_authenticate(self.user)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_list_transactions_unauthenticated(self):
        """Test listing transactions without authentication"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestPaymentConfigView(TestCase):
    """Test payment configuration endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            email='test@tenant.com',
            subdomain='test'
        )
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            tenant=self.tenant
        )
        self.url = reverse('payment-config', host='api')

    def test_get_config_authenticated(self):
        """Test getting payment gateway configuration"""
        self.client.force_authenticate(self.user)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('gateways', response.data)
        self.assertIn('enabled_gateways', response.data)

    def test_get_config_no_secrets_exposed(self):
        """Test that secret keys are not exposed in config"""
        self.client.force_authenticate(self.user)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify no secret keys in response
        response_str = json.dumps(response.data)
        self.assertNotIn('secret_key', response_str.lower())

    def test_get_config_unauthenticated(self):
        """Test getting config without authentication"""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TestPaymentWebhookView(TestCase):
    """Test payment webhook endpoint"""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name='Test Tenant',
            email='test@tenant.com',
            subdomain='test'
        )

    @patch('finances.gateways.khalti_gateway.KhaltiGateway.process_webhook')
    def test_webhook_khalti_valid_signature(self, mock_process):
        """Test processing Khalti webhook with valid signature"""
        transaction = PaymentTransaction.objects.create(
            gateway='khalti',
            gateway_transaction_id='test_pidx_123',
            amount=Decimal('1000.00'),
            currency='NPR',
            status='pending',
            tenant=self.tenant
        )
        
        mock_process.return_value = {
            'event_type': 'payment.success',
            'transaction_id': 'test_pidx_123',
            'status': 'completed',
            'amount': 1000.00,
            'currency': 'NPR',
        }
        
        url = reverse('payment-webhook', host='api', kwargs={'gateway': 'khalti'})
        
        payload = {
            'event_type': 'payment.success',
            'data': {'pidx': 'test_pidx_123'}
        }
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify webhook event was created
        self.assertTrue(WebhookEvent.objects.filter(
            gateway='khalti',
            event_type='payment.success',
            processed=True
        ).exists())
        
        # Verify transaction was updated
        transaction.refresh_from_db()
        self.assertEqual(transaction.status, 'completed')

    @patch('finances.gateways.khalti_gateway.KhaltiGateway.process_webhook')
    def test_webhook_invalid_signature(self, mock_process):
        """Test webhook with invalid signature"""
        mock_process.side_effect = Exception("Invalid webhook signature")
        
        url = reverse('payment-webhook', host='api', kwargs={'gateway': 'khalti'})
        
        payload = {
            'event_type': 'payment.success',
            'data': {'pidx': 'test_pidx_123'}
        }
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Verify webhook event was created with error
        webhook = WebhookEvent.objects.filter(gateway='khalti').first()
        self.assertIsNotNone(webhook)
        self.assertFalse(webhook.processed)
        self.assertIn('Invalid webhook signature', webhook.error_message)

    @patch('finances.gateways.khalti_gateway.KhaltiGateway.process_webhook')
    def test_webhook_creates_event_record(self, mock_process):
        """Test that webhook creates event record"""
        mock_process.return_value = {
            'event_type': 'payment.success',
            'transaction_id': 'test_pidx_123',
            'status': 'completed',
            'amount': 1000.00,
            'currency': 'NPR',
        }
        
        url = reverse('payment-webhook', host='api', kwargs={'gateway': 'khalti'})
        
        payload = {
            'event_type': 'payment.success',
            'data': {'pidx': 'test_pidx_123'}
        }
        
        initial_count = WebhookEvent.objects.count()
        
        response = self.client.post(url, payload, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(WebhookEvent.objects.count(), initial_count + 1)

    def test_webhook_no_authentication_required(self):
        """Test that webhooks don't require authentication"""
        url = reverse('payment-webhook', host='api', kwargs={'gateway': 'khalti'})
        
        payload = {
            'event_type': 'payment.success',
            'data': {'pidx': 'test_pidx_123'}
        }
        
        # Should not return 401 (will return 500 due to invalid signature, but that's expected)
        response = self.client.post(url, payload, format='json')
        
        self.assertNotEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
