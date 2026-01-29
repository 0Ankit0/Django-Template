from core.emails import Email

class AccountActivationEmail(Email):
    name = "account_activation"

class PasswordResetEmail(Email):
    name = "password_reset"
