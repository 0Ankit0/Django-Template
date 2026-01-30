import os
import subprocess
import sys
import threading
from django.core.management.commands.runserver import Command as RunserverCommand

class Command(RunserverCommand):
    def run_tailwind(self):
        # Use sys.executable for cross-platform compatibility
        self.tailwind_process = subprocess.Popen([sys.executable, 'manage.py', 'tailwind', 'start'])

    def handle(self, *args, **options):
        # Start Tailwind in a background thread only if this is the main process
        # (not the auto-reloader child process)
        if os.environ.get('RUN_MAIN') != 'true':
            thread = threading.Thread(target=self.run_tailwind, daemon=True)
            thread.start()
        try:
            super().handle(*args, **options)
        finally:
            # Cleanup Tailwind process on server shutdown
            if hasattr(self, 'tailwind_process') and self.tailwind_process.poll() is None:
                self.tailwind_process.terminate()