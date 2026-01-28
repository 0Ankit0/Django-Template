from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework import status
from config import settings

class HealthCheckMiddleware(MiddlewareMixin):
    """Middleware for health checking the application."""
    def process_request(self, request):
        if request.META["PATH_INFO"] == "/lbcheck":
            response = HttpResponse()

            executor = MigrationExecutor(connections[DEFAULT_DB_ALIAS])
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

            return response
