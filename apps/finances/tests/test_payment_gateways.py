"""Unit tests for payment gateway adapters"""

import hmac
import hashlib
import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.test import TestCase
from django.conf import settings

from ..gateways.khalti_gateway import KhaltiGateway
from ..gateways.factory import PaymentGatewayFactory


class TestKhaltiGateway(TestCase):
    """Test Khalti payment gateway adapter"""

    def test_npr_to_paisa_conversion(self):
        """Test NPR to paisa conversion (1 NPR = 100 paisa)"""
        gateway = KhaltiGateway()
        
        self.assertEqual(gateway._npr_to_paisa(100.00), 10000)
        self.assertEqual(gateway._npr_to_paisa(1.50), 150)
        self.assertEqual(gateway._npr_to_paisa(0.01), 1)
        self.assertEqual(gateway._npr_to_paisa(1000), 100000)

    def test_paisa_to_npr_conversion(self):
        """Test paisa to NPR conversion"""
        gateway = KhaltiGateway()
        
        self.assertEqual(gateway._paisa_to_npr(10000), 100.00)
        self.assertEqual(gateway._paisa_to_npr(150), 1.50)
        self.assertEqual(gateway._paisa_to_npr(1), 0.01)
        self.assertEqual(gateway._paisa_to_npr(100000), 1000.00)

    def test_status_mapping(self):
        """Test Khalti status to generic status mapping"""
        gateway = KhaltiGateway()
        
        self.assertEqual(gateway._map_status("Completed"), "completed")
        self.assertEqual(gateway._map_status("Pending"), "pending")
        self.assertEqual(gateway._map_status("Refunded"), "refunded")
        self.assertEqual(gateway._map_status("User canceled"), "cancelled")
        self.assertEqual(gateway._map_status("Partially refunded"), "refunded")
        self.assertEqual(gateway._map_status("Unknown"), "failed")

    @patch('requests.post')
    def test_initiate_payment_success(self, mock_post):
        """Test successful payment initiation"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'payment_url': 'https://khalti.com/payment/abc123',
            'pidx': 'test_pidx_123',
            'expires_at': '2026-02-11T12:00:00Z',
            'expires_in': 3600,
        }
        mock_post.return_value = mock_response
        
        gateway = KhaltiGateway()
        result = gateway.initiate_payment(
            amount=1000.00,
            currency='NPR',
            customer_info={
                'customer_name': 'Test User',
                'customer_email': 'test@example.com',
                'customer_phone': '9800000000',
            },
            metadata={
                'purchase_order_id': 'order_123',
                'purchase_order_name': 'Test Order',
                'return_url': 'https://example.com/return',
            }
        )
        
        self.assertEqual(result['payment_url'], 'https://khalti.com/payment/abc123')
        self.assertEqual(result['transaction_id'], 'test_pidx_123')
        self.assertIn('expires_at', result)
        
        # Verify API was called with correct amount (converted to paisa)
        call_args = mock_post.call_args
        self.assertEqual(call_args[1]['json']['amount'], 100000)  # 1000 NPR = 100000 paisa

    @patch('requests.post')
    def test_initiate_payment_api_error(self, mock_post):
        """Test payment initiation with API error"""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = 'Invalid request'
        mock_post.return_value = mock_response
        
        gateway = KhaltiGateway()
        
        with self.assertRaisesRegex(Exception, "Khalti API error"):
            gateway.initiate_payment(
                amount=1000.00,
                currency='NPR',
                customer_info={
                    'customer_name': 'Test User',
                    'customer_email': 'test@example.com',
                    'customer_phone': '9800000000',
                },
                metadata={
                    'purchase_order_id': 'order_123',
                    'purchase_order_name': 'Test Order',
                    'return_url': 'https://example.com/return',
                }
            )

    def test_initiate_payment_invalid_currency(self):
        """Test payment initiation with non-NPR currency"""
        gateway = KhaltiGateway()
        
        with self.assertRaisesRegex(ValueError, "Khalti only supports NPR currency"):
            gateway.initiate_payment(
                amount=100.00,
                currency='USD',
                customer_info={},
                metadata={}
            )

    @patch('requests.post')
    def test_verify_payment_completed(self, mock_post):
        """Test verifying a completed payment"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'pidx': 'test_pidx_123',
            'status': 'Completed',
            'total_amount': 100000,  # 1000 NPR in paisa
            'fee': 1000,  # 10 NPR in paisa
            'refunded': False,
            'payment_method': 'khalti',
        }
        mock_post.return_value = mock_response
        
        gateway = KhaltiGateway()
        result = gateway.verify_payment('test_pidx_123')
        
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['amount'], 1000.00)  # Converted back to NPR
        self.assertEqual(result['currency'], 'NPR')
        self.assertEqual(result['fee'], 10.00)
        self.assertFalse(result['refunded'])

    @patch('requests.post')
    def test_verify_payment_pending(self, mock_post):
        """Test verifying a pending payment"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'pidx': 'test_pidx_123',
            'status': 'Pending',
            'total_amount': 100000,
            'fee': 0,
            'refunded': False,
        }
        mock_post.return_value = mock_response
        
        gateway = KhaltiGateway()
        result = gateway.verify_payment('test_pidx_123')
        
        self.assertEqual(result['status'], 'pending')

    @patch('requests.post')
    def test_verify_payment_failed(self, mock_post):
        """Test verifying a failed payment"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'pidx': 'test_pidx_123',
            'status': 'Failed',
            'total_amount': 100000,
            'fee': 0,
            'refunded': False,
        }
        mock_post.return_value = mock_response
        
        gateway = KhaltiGateway()
        result = gateway.verify_payment('test_pidx_123')
        
        self.assertEqual(result['status'], 'failed')

    @patch('requests.post')
    def test_verify_payment_api_error(self, mock_post):
        """Test payment verification with API error"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = 'Transaction not found'
        mock_post.return_value = mock_response
        
        gateway = KhaltiGateway()
        
        with self.assertRaisesRegex(Exception, "Khalti verification error"):
            gateway.verify_payment('invalid_pidx')

    def test_verify_signature_valid(self):
        """Test webhook signature verification with valid signature"""
        gateway = KhaltiGateway()
        
        payload = {
            'event_type': 'payment.success',
            'data': {'pidx': 'test_123'}
        }
        
        # Create valid signature
        message = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        signature = hmac.new(
            gateway.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        self.assertTrue(gateway._verify_signature(payload, signature))

    def test_verify_signature_invalid(self):
        """Test webhook signature verification with invalid signature"""
        gateway = KhaltiGateway()
        
        payload = {
            'event_type': 'payment.success',
            'data': {'pidx': 'test_123'}
        }
        
        invalid_signature = 'invalid_signature_12345'
        
        self.assertFalse(gateway._verify_signature(payload, invalid_signature))

    @patch.object(KhaltiGateway, 'verify_payment')
    def test_process_webhook_success(self, mock_verify):
        """Test processing a webhook event"""
        mock_verify.return_value = {
            'status': 'completed',
            'amount': 1000.00,
            'currency': 'NPR',
        }
        
        gateway = KhaltiGateway()
        
        payload = {
            'event_type': 'payment.success',
            'data': {'pidx': 'test_pidx_123'}
        }
        
        # Create valid signature
        message = json.dumps(payload, separators=(',', ':'), sort_keys=True)
        signature = hmac.new(
            gateway.secret_key.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        headers = {'X-Khalti-Signature': signature}
        
        result = gateway.process_webhook(payload, headers)
        
        self.assertEqual(result['event_type'], 'payment.success')
        self.assertEqual(result['transaction_id'], 'test_pidx_123')
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['amount'], 1000.00)

    def test_process_webhook_invalid_signature(self):
        """Test webhook processing with invalid signature"""
        gateway = KhaltiGateway()
        
        payload = {
            'event_type': 'payment.success',
            'data': {'pidx': 'test_pidx_123'}
        }
        
        headers = {'X-Khalti-Signature': 'invalid_signature'}
        
        with self.assertRaisesRegex(Exception, "Invalid webhook signature"):
            gateway.process_webhook(payload, headers)

    def test_create_refund_not_implemented(self):
        """Test that refund creation raises NotImplementedError"""
        gateway = KhaltiGateway()
        
        with self.assertRaisesRegex(NotImplementedError, "Khalti refunds must be processed"):
            gateway.create_refund('test_pidx_123')


class TestPaymentGatewayFactory(TestCase):
    """Test payment gateway factory"""

    def test_get_khalti_gateway(self):
        """Test getting Khalti gateway instance"""
        gateway = PaymentGatewayFactory.get_gateway('khalti')
        
        self.assertIsInstance(gateway, KhaltiGateway)

    def test_get_unknown_gateway(self):
        """Test getting unknown gateway raises error"""
        with self.assertRaisesRegex(ValueError, "Unknown payment gateway: paypal"):
            PaymentGatewayFactory.get_gateway('paypal')

    def test_get_available_gateways(self):
        """Test getting list of available gateways"""
        gateways = PaymentGatewayFactory.get_available_gateways()
        
        self.assertIn('khalti', gateways)
        self.assertIsInstance(gateways, list)
