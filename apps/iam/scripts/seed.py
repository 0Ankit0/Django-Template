import os
import sys
import django

# Add the project root to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Setup Django
django.setup()

from iam.models import Group, User

def seed_groups():
    """Seed default groups."""
    Group.objects.get_or_create(name='User')
    Group.objects.get_or_create(name='Admin')
    print("Default groups seeded successfully.")

def seed_users():
    """Seed default users with roles."""
    # Ensure groups exist
    seed_groups()
    
    admin_group = Group.objects.get(name='Admin')
    user_group = Group.objects.get(name='User')
    
    # Seed admin user
    admin_user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@gmail.com',
            'is_superuser': True,
            'is_active': True,
        }
    )
    if created:
        admin_user.set_password('admin123')  # Default password - change in production!
        admin_user.save()
        admin_user.groups.add(admin_group)
        print("Admin user 'admin' created.")
    else:
        print("Admin user 'admin' already exists.")
    
    # Seed regular user
    regular_user, created = User.objects.get_or_create(
        username='user',
        defaults={
            'email': 'user@gmail.com',
            'is_active': True,
        }
    )
    if created:
        regular_user.set_password('user123')  # Default password - change in production!
        regular_user.save()
        regular_user.groups.add(user_group)
        print("Regular user 'user' created.")
    else:
        print("Regular user 'user' already exists.")

if __name__ == '__main__':
    seed_users()