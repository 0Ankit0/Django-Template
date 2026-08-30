"""Backward-compatible checkout imports.

Stripe checkout implementation lives in ``billing.services.stripe``.
"""

from .services import create_checkout_session, create_or_get_customer

__all__ = ["create_checkout_session", "create_or_get_customer"]
