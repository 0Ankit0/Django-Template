# Entity Relationship Diagram (ERD)

```mermaid
erDiagram
    iam_user {
        hashid id PK
        varchar username
        varchar email
        varchar password
        bool is_active
        bool is_superuser
    }

    multitenancy_tenant {
        hashid id PK
        varchar name
        varchar slug
        varchar billing_email
        varchar type
    }

    multitenancy_tenantmembership {
        hashid id PK
        fk user_id
        fk tenant_id
        varchar role
        bool is_accepted
    }

    djstripe_customer {
        varchar id PK "stripe_id"
        fk subscriber_id "Tenant"
        decimal balance
    }

    djstripe_subscription {
        varchar id PK
        fk customer_id
        varchar status
        timestamp current_period_end
    }

    djstripe_product {
        varchar id PK
        varchar name
    }

    djstripe_price {
        varchar id PK
        fk product_id
        decimal unit_amount
        varchar currency
    }

    iam_user ||--o{ multitenancy_tenantmembership : has
    multitenancy_tenant ||--o{ multitenancy_tenantmembership : has
    multitenancy_tenant ||--o| djstripe_customer : "is subscriber"
    djstripe_customer ||--o{ djstripe_subscription : has
    djstripe_subscription }|--|| djstripe_price : "based on"
    djstripe_price }|--|| djstripe_product : "variant of"

    finances_paymenttransaction {
        uuid id PK
        varchar gateway "stripe|khalti"
        varchar gateway_transaction_id UK
        decimal amount
        varchar currency
        varchar status "pending|completed|failed|refunded|cancelled"
        varchar payment_method
        json customer_info
        json gateway_response
        fk tenant_id
        timestamp created_at
        timestamp updated_at
    }

    finances_webhookevent {
        uuid id PK
        varchar gateway
        varchar event_type
        json payload
        bool processed
        text error_message
        timestamp created_at
    }

    multitenancy_tenant ||--o{ finances_paymenttransaction : "has payments"
```
