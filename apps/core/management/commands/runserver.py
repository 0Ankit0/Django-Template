import subprocess
import sys
from django.core.management.commands.runserver import Command as RunserverCommand

class Command(RunserverCommand):
    def handle(self, *args, **options):
        # Build Tailwind CSS before starting the server
        try:
            print("Building Tailwind CSS...")
            subprocess.run(
                ["bun", "run", "build-css-prod"],  # Use prod build for speed; change to build-css for watch
                check=True,
                cwd=self.get_project_root()  # Assumes project root; adjust if needed
            )
            print("Tailwind CSS built successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Error building Tailwind CSS: {e}")
            sys.exit(1)
        
        # Call the original runserver command
        super().handle(*args, **options)
    
    def get_project_root(self):
        # Get the project root (where manage.py is)
        import os
        from pathlib import Path
        return Path(__file__).resolve().parent.parent.parent.parent.parent  # Adjust based on your structure