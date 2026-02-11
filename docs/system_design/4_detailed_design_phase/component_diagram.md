# Component Diagram

```mermaid
C4Component
    title Component Diagram for Application Logic

    Container_Boundary(api, "API Layer") {
        Component(views, "ViewSets", "DRF", "Handles HTTP Requests (Auth, Tenant, Finance)")
        Component(serializers, "Serializers", "DRF", "Data Validation & Transformation")
        Component(permissions, "Permissions", "DRF", "Access Control Logic (IsTenantOwner, etc.)")
    }

    Container_Boundary(core, "Core Features") {
        Component(iam, "IAM App", "Django App", "User Mgmt, Auth, OTP")
        Component(multi, "Multitenancy App", "Django App", "Tenant logic, Middleware")
        Component(fin, "Finances App", "Django App", "Subscription wrappers, Webhooks")
        Component(notif, "Notifications App", "Django App", "Email sending logic")
    }

    Container_Boundary(infra, "Infrastructure Adapters") {
        Component(celery, "Tasks Module", "Celery", "Async Job Definitions")
        Component(storage, "Storage Backend", "S3Boto3", "File Upload Handling")
    }

    Rel(views, serializers, "Uses")
    Rel(views, permissions, "Checks")
    Rel(views, core, "Calls Business Logic")
    Rel(core, infra, "Dispatches Tasks")
```
