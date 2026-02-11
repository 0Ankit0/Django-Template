# Use Case Analysis

## Use Case Diagram

```mermaid
usecaseDiagram
    actor "User" as U
    actor "Tenant Owner" as TO
    actor "System Admin" as A
    actor "Stripe" as S
    actor "Email Service" as ES

    package "Template Platform" {
        usecase "Register Account" as UC1
        usecase "Login / logout" as UC2
        usecase "Manage Profile" as UC3
        usecase "Create Tenant" as UC4
        usecase "Invite Member" as UC5
        usecase "Accept Invitation" as UC6
        usecase "Subscribe to Plan" as UC7
        usecase "Pay Invoice" as UC8
        usecase "Manage Users" as UC9
    }

    U -- UC1
    U -- UC2
    U -- UC3
    U -- UC6

    TO --|> U
    TO -- UC4
    TO -- UC5
    TO -- UC7
    TO -- UC8

    A -- UC9

    UC1 ..> ES : "Send Confirmation"
    UC5 ..> ES : "Send Invite"
    UC7 ..> S : "Process Payment"
    UC8 ..> S : "Process Payment"
```

## Use Case Descriptions

### UC1: Register Account
*   **Actor**: User
*   **Description**: User creates a new account using email or social login.
*   **Preconditions**: None
*   **Postconditions**: Account created, email confirmation sent.

### UC4: Create Tenant
*   **Actor**: Tenant Owner
*   **Description**: User creates a new organization workspace.
*   **Preconditions**: User is logged in.
*   **Postconditions**: Tenant created, User assigned as Owner.

### UC7: Subscribe to Plan
*   **Actor**: Tenant Owner
*   **Description**: Owner selects a subscription plan and pays via Stripe.
*   **Preconditions**: Tenant exists, Owner has permissions.
*   **Postconditions**: Subscription active, premium features unlocked.
