# BPMN / Swimlane Diagram

## Subscription Upgrade Process

```mermaid
sequenceDiagram
    participant U as User (Tenant Owner)
    participant F as Frontend
    participant B as Backend (Django)
    participant S as Stripe

    rect rgb(240, 248, 255)
    note right of U: User Action
    U->>F: Clicks "Upgrade Subscription"
    end

    F->>B: POST /api/subscriptions/create-checkout

    rect rgb(255, 250, 240)
    note right of B: System Processing
    B->>S: Create Checkout Session (Customer, Price)
    S-->>B: Return Session URL
    B-->>F: Return Redirect URL
    end

    F->>U: Redirects to Stripe Checkout (Hosted Page)

    rect rgb(240, 255, 240)
    note right of S: Payment Processing
    U->>S: Enters Payment Details & Confirms
    S->>S: Process Payment
    S-->>U: Success! Redirect back to App

    par Async Webhook
        S->>B: Webhook: checkout.session.completed
        B->>B: Update Tenant Subscription Status
        B->>B: Send Invoice Email
    and User Redirect
        U->>F: Returns to Platform
        F->>B: Poll for Status Verify
        B-->>F: Return "Active"
        F->>U: Show Success Message
    end
    end
```
*Note: Mermaid does not strictly support BPMN notation, so a Swimlane-style Sequence Diagram is used to depict the cross-system workflow.*
