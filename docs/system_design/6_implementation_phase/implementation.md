# Implementation Details

## C4 Code Diagram (Class Level)

Focusing on the **Subscription Checkout Flow**.

```mermaid
classDiagram
    direction TB

    class SubscriptionViewSet {
        +create_checkout_session(request)
    }

    class StripeService {
        +create_checkout_session(tenant_id, price_id)
        +handle_webhook(event)
    }

    class TenantRepository {
        +get_tenant_by_id(id)
        +update_subscription_status(tenant, status)
    }

    SubscriptionViewSet --> StripeService : delegates to
    StripeService --> TenantRepository : uses
```

## Implementation Strategy

The implementation follows the **adapters structure**:
- **Core Domain Logic** stays in `apps/<name>/services/`.
- **Framework Glue** (Views/Serializers) stays in `apps/<name>/api/`.
- **External Integrations** (Stripe/AWS) use the Adapter pattern to keep the core logic testable.
