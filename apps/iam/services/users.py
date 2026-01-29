def get_role_names(user):
    """
    Get list of role names for a user.
    """
    roles = []
    if user.is_superuser:
        roles.append("Superuser")
    if user.is_staff:
        roles.append("Staff")
    # Add logic for other roles/groups if needed
    return roles
