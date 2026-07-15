# API Design Integration

## Key API Endpoints & Contracts

```mermaid
classDiagram
    direction LR
    class Auth_API {
        POST /auth/login/
        POST /auth/register/
        POST /auth/refresh/
        POST /auth/logout/
    }

    class Tenant_API {
        GET /tenants/
        POST /tenants/
        GET /tenants/{id}/
        POST /tenants/{id}/invite/
    }

    class Finance_API {
        GET /subscriptions/
        POST /subscriptions/create-checkout/
        POST /subscriptions/portal/
        GET /invoices/
    }

    class User_API {
        GET /me/
        PATCH /me/
        POST /me/avatar/
    }

    Auth_API --> User_API : Returns User Details
    Tenant_API --> Auth_API : Requires Authentication
    Finance_API --> Tenant_API : Scoped to Tenant
```
