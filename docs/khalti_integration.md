# Khalti Payment Gateway Integration Guide

## Overview

Khalti is Nepal's leading digital wallet and payment gateway. This guide covers the complete integration of Khalti into the Django Template system using a generic payment gateway architecture.

## Khalti API Basics

### Authentication
- **Public Key**: Used in frontend for payment initiation
- **Secret Key**: Used in backend for API calls and webhook verification
- **Modes**: Sandbox (testing) and Live (production)

### API Endpoints
- **Sandbox**: `https://a.khalti.com/api/v2/`
- **Live**: `https://khalti.com/api/v2/`

### Key Concepts
- **Amount Format**: All amounts in paisa (1 NPR = 100 paisa)
- **Payment Index (pidx)**: Unique identifier for each payment
- **Webhook Signature**: HMAC-SHA256 signature for webhook verification

## Payment Flow

```
1. User initiates checkout
   ↓
2. Backend: POST /api/payments/initiate/
   - Creates PaymentTransaction (status=pending)
   - Calls Khalti API to create payment
   - Returns payment_url
   ↓
3. Frontend: Redirect user to payment_url
   ↓
4. User completes payment on Khalti
   ↓
5. Khalti redirects to return_url with pidx
   ↓
6. Frontend: POST /api/payments/verify/
   - Backend verifies payment with Khalti
   - Updates PaymentTransaction (status=completed)
   ↓
7. Khalti sends webhook (async)
   - POST /api/payments/webhook/khalti/
   - Verifies signature
   - Updates transaction if needed
```

## Backend Implementation

### Environment Variables

Add to `.env`:
```bash
KHALTI_ENABLED=True
KHALTI_PUBLIC_KEY=your_public_key_here
KHALTI_SECRET_KEY=your_secret_key_here
KHALTI_LIVE_MODE=False  # Set to True for production
```

### Models

**PaymentTransaction**: Universal model for all gateways
- `gateway`: 'khalti'
- `gateway_transaction_id`: Khalti's pidx
- `amount`: In NPR (e.g., 1000.00)
- `currency`: 'NPR'
- `status`: pending → completed/failed
- `customer_info`: JSON with customer details
- `gateway_response`: Full Khalti API response

**WebhookEvent**: Logs all webhook events
- `gateway`: 'khalti'
- `event_type`: Event type from webhook
- `payload`: Full webhook payload
- `processed`: True after successful processing

### API Endpoints

#### 1. Initiate Payment
```http
POST /api/payments/initiate/
Content-Type: application/json
Authorization: Bearer <token>

{
  "gateway": "khalti",
  "amount": 1000.00,
  "currency": "NPR",
  "purchase_order_id": "ORDER-123",
  "purchase_order_name": "Premium Subscription",
  "customer_name": "John Doe",
  "customer_email": "john@example.com",
  "customer_phone": "9841234567",
  "return_url": "https://yoursite.com/payment/success"
}
```

**Response**:
```json
{
  "transaction_id": "uuid-here",
  "payment_url": "https://test-pay.khalti.com/#/...",
  "gateway": "khalti",
  "amount": 1000.00,
  "status": "pending"
}
```

#### 2. Verify Payment
```http
POST /api/payments/verify/
Content-Type: application/json
Authorization: Bearer <token>

{
  "transaction_id": "uuid-from-initiate"
}
```

**Response**:
```json
{
  "transaction_id": "uuid-here",
  "status": "completed",
  "amount": 1000.00,
  "gateway_response": {
    "pidx": "khalti-pidx",
    "total_amount": 100000,
    "status": "Completed",
    ...
  }
}
```

#### 3. Webhook Handler
```http
POST /api/payments/webhook/khalti/
Content-Type: application/json
X-Khalti-Signature: <hmac-signature>

{
  "event_type": "payment.success",
  "data": {
    "pidx": "khalti-pidx",
    "total_amount": 100000,
    "status": "Completed",
    ...
  }
}
```

## Khalti Gateway Adapter

### Key Methods

**initiate_payment()**
- Converts NPR to paisa (multiply by 100)
- Calls Khalti `/epayment/initiate/`
- Returns payment URL

**verify_payment()**
- Calls Khalti `/epayment/lookup/`
- Maps Khalti status to generic status
- Returns payment details

**process_webhook()**
- Validates HMAC signature
- Extracts pidx from payload
- Verifies payment
- Updates transaction

### NPR ↔ Paisa Conversion

```python
# NPR to paisa
amount_npr = 1000.00
amount_paisa = int(amount_npr * 100)  # 100000

# Paisa to NPR
amount_paisa = 100000
amount_npr = amount_paisa / 100  # 1000.00
```

## Testing

### Sandbox Credentials

1. Sign up at https://khalti.com/
2. Go to Settings → Developer
3. Get test public and secret keys

### Test Payment Numbers

Khalti provides test phone numbers:
- `9800000000` - Success
- `9800000001` - Insufficient balance
- `9800000002` - Invalid PIN
- `9800000003` - Invalid OTP
- `9800000004` - User canceled
- `9800000005` - Transaction limit exceeded

### Test Flow

1. Initiate payment via API
2. Open payment_url in browser
3. Use test phone number (e.g., 9800000000)
4. Enter OTP: `987654`
5. Enter PIN: `1111`
6. Payment completes
7. Verify payment via API

### Webhook Testing (Local)

Use ngrok to expose local server:
```bash
ngrok http 8000
```

Configure webhook URL in Khalti dashboard:
```
https://your-ngrok-url.ngrok.io/api/payments/webhook/khalti/
```

## Production Deployment

### Checklist

- [ ] Get production Khalti credentials
- [ ] Set `KHALTI_LIVE_MODE=True`
- [ ] Update `KHALTI_PUBLIC_KEY` and `KHALTI_SECRET_KEY`
- [ ] Configure production webhook URL (must be HTTPS)
- [ ] Test with real payment (small amount)
- [ ] Monitor webhook events in admin
- [ ] Set up error alerting for failed webhooks

### Security Best Practices

1. **Never expose secret key**: Only use in backend
2. **Validate webhook signatures**: Always verify HMAC
3. **Use HTTPS**: Required for production webhooks
4. **Idempotency**: Handle duplicate webhooks gracefully
5. **Logging**: Log all payment attempts and webhooks

## Troubleshooting

### Payment Initiation Fails

**Error**: "Invalid credentials"
- Check `KHALTI_SECRET_KEY` is correct
- Verify `KHALTI_LIVE_MODE` matches your keys

**Error**: "Invalid amount"
- Ensure amount is in paisa (multiply NPR by 100)
- Amount must be positive integer

### Payment Verification Fails

**Error**: "Payment not found"
- Check `pidx` is correct
- Verify payment was actually completed

### Webhook Not Received

- Check webhook URL is publicly accessible (use ngrok for local)
- Verify webhook URL configured in Khalti dashboard
- Check webhook signature validation isn't failing

### Webhook Signature Invalid

- Ensure `KHALTI_SECRET_KEY` matches dashboard
- Check payload is not modified before verification
- Verify HMAC calculation matches Khalti's format

## API Reference

### Khalti API Documentation
- Official Docs: https://docs.khalti.com/
- Checkout API: https://docs.khalti.com/checkout/web/
- Payment Gateway: https://docs.khalti.com/khalti-epayment/

### Support
- Khalti Support: support@khalti.com
- Developer Forum: https://community.khalti.com/

## Example Code

### Frontend Integration (Optional)

If using Khalti's checkout SDK:
```javascript
import KhaltiCheckout from "khalti-checkout-web";

const config = {
  publicKey: "your_public_key",
  productIdentity: "ORDER-123",
  productName: "Premium Subscription",
  productUrl: "https://yoursite.com/product",
  eventHandler: {
    onSuccess(payload) {
      // Call verify API
      fetch('/api/payments/verify/', {
        method: 'POST',
        body: JSON.stringify({ transaction_id: payload.pidx })
      });
    },
    onError(error) {
      console.error(error);
    }
  }
};

const checkout = new KhaltiCheckout(config);
checkout.show({ amount: 100000 }); // Amount in paisa
```

### Backend Verification

```python
from finances.gateways.factory import PaymentGatewayFactory

# Get Khalti gateway
gateway = PaymentGatewayFactory.get_gateway('khalti')

# Verify payment
result = gateway.verify_payment(pidx='khalti-pidx-here')
print(result['status'])  # 'Completed', 'Pending', 'Failed'
```

## Monitoring

### Admin Interface

Access Django admin to monitor:
- **PaymentTransaction**: All payment attempts
- **WebhookEvent**: All webhook deliveries

Filter by:
- Gateway: khalti
- Status: pending, completed, failed
- Date range

### Metrics to Track

- Payment success rate
- Average payment time
- Webhook delivery success rate
- Failed payment reasons

## Next Steps

After Khalti integration:
1. Add more payment gateways (PayPal, Razorpay, etc.)
2. Implement refund functionality
3. Add payment analytics dashboard
4. Support recurring payments
5. Add payment method management
