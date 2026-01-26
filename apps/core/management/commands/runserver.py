import os
from django.core.management.commands.runserver import Command as RunserverCommand
from django.core.management import call_command

class Command(RunserverCommand):
    def handle(self, *args, **options):
        # Build Tailwind CSS before starting the server
        if not os.environ.get('RUN_MAIN') or options.get('use_reloader') is False:
             self.stdout.write(self.style.SUCCESS('Building Tailwind CSS...'))
             try:
                 call_command('tailwind', 'build')
             except Exception as e:
                 self.stdout.write(self.style.WARNING(f'Failed to build Tailwind CSS: {e}'))
        super().handle(*args, **options)