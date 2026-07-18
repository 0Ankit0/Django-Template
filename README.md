# Migrating to All the schemas in the database
Use the migrate_schemas command to migrate all the schemas in the database. This command will apply all the migrations for each tenant schema.
```shell
python manage.py migrate_schemas 
```

# Get current tenant in views
You can retrieve the current tenant in your views using the request.tenant which is inserted by the middleware. For example:
```python
from django.http import HttpResponse

def my_view(request):
    current_tenant = request.tenant
    return HttpResponse(f"Current tenant: {current_tenant}")
```

# Create public tenant
To create a public tenant, you can use the `create_public_tenant` management command.
```bash
python manage.py create_public_tenant --domain-url <domain_url> --owner-email
```