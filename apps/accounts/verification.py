"""Email verification links.

A link carries a signed, timestamped token naming the user and the email address
it was sent to, so it only works for that account and that address, and only for
EMAIL_VERIFICATION_MAX_AGE seconds.
"""

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail

from .models import User

logger = logging.getLogger(__name__)

SALT = "accounts.verify-email"


def make_token(user):
    return signing.dumps({"uid": user.pk, "email": user.email}, salt=SALT)


def user_for_token(token):
    """The user a valid, unexpired token belongs to, or None."""
    try:
        data = signing.loads(token, salt=SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)
    except signing.BadSignature:  # includes SignatureExpired
        return None
    return User.objects.filter(pk=data.get("uid"), email=data.get("email")).first()


def verification_link(user):
    query = urlencode({"token": make_token(user)})
    return f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?{query}"


def _send(user, subject, message, what):
    """Send one email. A delivery failure is logged, not raised: the action it
    reports has happened either way."""
    try:
        send_mail(subject, message, None, [user.email])
    except Exception:
        logger.exception("Could not send the %s email to user %s", what, user.pk)


def send_verification_email(user):
    message = (
        f"Hello {user.first_name},\n\n"
        "Thank you for creating a Shipora account. Please verify your email address "
        "by opening the link below:\n\n"
        f"{verification_link(user)}\n\n"
        "If you did not create this account, you can ignore this email.\n\n"
        "The Shipora team"
    )
    _send(user, "Verify your Shipora account", message, "verification")


def send_verified_confirmation(user):
    message = (
        f"Hello {user.first_name},\n\n"
        "Your email address has been verified and your Shipora account is ready. "
        f"You can now log in at {settings.FRONTEND_URL.rstrip('/')}/login\n\n"
        "The Shipora team"
    )
    _send(user, "Your Shipora account is verified", message, "verification confirmation")
