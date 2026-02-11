from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Custom authentication backend that allows users to log in using their email address.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        try:
            # Try to fetch the user by email
            user = User.objects.get(email=username)
        except User.DoesNotExist:
            # Try to fetch by username as fallback
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                return None

        # Check the password
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
