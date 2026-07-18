
from django.core.management.base import BaseCommand
from apps.tenancy.models import Client, Domain


class Command(BaseCommand):
    help = "Create the public tenant"

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True)
        parser.add_argument("--domain", required=True) # localhost for local

    def handle(self, *args, **options):
        if Client.objects.filter(schema_name="public").exists():
            self.stdout.write(
                self.style.WARNING("Public tenant already exists.")
            )
            return

        client = Client.objects.create(
            schema_name="public",
            name=options["name"],
        )

        Domain.objects.create(
            tenant=client,
            domain=options["domain"],
            is_primary=True,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Created public tenant '{client.name}' ({options['domain']})"
            )
        )