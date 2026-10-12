"""Email verification links.

A link carries a signed, timestamped token naming the user and the email address
it was sent to, so it only works for that account and that address, and only for
EMAIL_VERIFICATION_MAX_AGE seconds. It also carries a fingerprint of the account's
password, so the links sent before a registration was started again stop working.
"""

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import User

logger = logging.getLogger(__name__)

SALT = "accounts.verify-email"

# Backends that accept a message without delivering it to anyone.
UNDELIVERED_BACKENDS = (
    "django.core.mail.backends.console.EmailBackend",
    "django.core.mail.backends.dummy.EmailBackend",
)


def _fingerprint(user):
    return salted_hmac(SALT, user.password).hexdigest()[:16]


def make_token(user):
    return signing.dumps({"uid": user.pk, "email": user.email, "v": _fingerprint(user)}, salt=SALT)


def user_for_token(token):
    """The user a valid, unexpired token belongs to, or None."""
    try:
        data = signing.loads(token, salt=SALT, max_age=settings.EMAIL_VERIFICATION_MAX_AGE)
    except signing.BadSignature:  # includes SignatureExpired
        return None
    if not isinstance(data, dict):
        return None
    user = User.objects.filter(pk=data.get("uid"), email=data.get("email")).first()
    # Links sent before the fingerprint existed have no "v" and stay valid.
    if user is not None and "v" in data:
        if not constant_time_compare(str(data["v"]), _fingerprint(user)):
            return None
    return user


def verification_link(user):
    query = urlencode({"token": make_token(user)})
    return f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?{query}"


def _send(user, subject, message, what):
    """Send one email and say whether it went out. A delivery failure is logged,
    not raised: the action it reports has happened either way."""
    if not settings.DEBUG and settings.EMAIL_BACKEND in UNDELIVERED_BACKENDS:
        logger.error(
            "Email delivery is not configured (EMAIL_URL): the %s email to user %s was not sent",
            what,
            user.pk,
        )
        return False
    try:
        return send_mail(subject, message, None, [user.email]) > 0
    except Exception:
        logger.exception("Could not send the %s email to user %s", what, user.pk)
        return False


def send_verification_email(user):
    message = (
        f"Hello {user.first_name},\n\n"
        "Thank you for creating a Shipora account. Please verify your email address "
        "by opening the link below:\n\n"
        f"{verification_link(user)}\n\n"
        "If you did not create this account, you can ignore this email.\n\n"
        "The Shipora team"
    )
    return _send(user, "Verify your Shipora account", message, "verification")


def send_verified_confirmation(user):
    message = (
        f"Hello {user.first_name},\n\n"
        "Your email address has been verified and your Shipora account is ready. "
        f"You can now log in at {settings.FRONTEND_URL.rstrip('/')}/login\n\n"
        "The Shipora team"
    )
    return _send(user, "Your Shipora account is verified", message, "verification confirmation")
