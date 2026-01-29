from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken

def blacklist_user_tokens(user):
    """
    Blacklist all outstanding tokens for a user.
    """
    outstanding_tokens = OutstandingToken.objects.filter(user=user)
    for token in outstanding_tokens:
        BlacklistedToken.objects.get_or_create(token=token)
