"""Email verification links.

A link carries a signed, timestamped token naming the user and the email address
it was sent to, so it only works for that account and that address, and only for
EMAIL_VERIFICATION_MAX_AGE seconds. It also carries a fingerprint of the account's
password, so the links sent before a registration was started again stop working.

Sending reports what really happened to the email: SENT (handed to a mail
server), CAPTURED (local development only: kept on this machine, in the local test
mailbox or the server log, never delivered) or FAILED.
"""

import logging
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import User

logger = logging.getLogger(__name__)

SALT = "accounts.verify-email"

SENT, CAPTURED, FAILED = "sent", "captured", "failed"

# Backends that keep a message on this machine instead of delivering it.
LOCAL_BACKENDS = (
    "django.core.mail.backends.filebased.EmailBackend",
    "django.core.mail.backends.console.EmailBackend",
)
# Throws every message away.
DUMMY_BACKEND = "django.core.mail.backends.dummy.EmailBackend"


def capturing_locally():
    """True in local development when emails are only kept on this machine."""
    return settings.DEBUG and settings.EMAIL_BACKEND in LOCAL_BACKENDS


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
    """Send one email and say what happened to it: SENT, CAPTURED or FAILED. A
    failure is logged, not raised: the action it reports has happened either way."""
    backend = settings.EMAIL_BACKEND
    if backend == DUMMY_BACKEND or (backend in LOCAL_BACKENDS and not settings.DEBUG):
        logger.error(
            "Email delivery is not configured (EMAIL_URL): the %s email to user %s was not sent",
            what,
            user.pk,
        )
        return FAILED
    try:
        accepted = send_mail(subject, message, None, [user.email])
    except Exception:
        logger.exception("Could not send the %s email to user %s", what, user.pk)
        return FAILED
    if not accepted:
        logger.error("The %s email to user %s was not accepted for sending", what, user.pk)
        return FAILED
    if backend in LOCAL_BACKENDS:
        logger.info("The %s email to user %s was kept locally, not delivered", what, user.pk)
        return CAPTURED
    return SENT


def seconds_until_resend(user):
    """How long this account still has to wait for another verification email."""
    sent_at = user.verification_email_sent_at
    if sent_at is None:
        return 0
    waited = (timezone.now() - sent_at).total_seconds()
    return max(0, int(settings.EMAIL_VERIFICATION_RESEND_COOLDOWN - waited + 0.999))


def send_verification_email(user):
    message = (
        f"Hello {user.first_name},\n\n"
        "Thank you for creating a Shipora account. Please verify your email address "
        "by opening the link below:\n\n"
        f"{verification_link(user)}\n\n"
        "If you did not create this account, you can ignore this email.\n\n"
        "The Shipora team"
    )
    outcome = _send(user, "Verify your Shipora account", message, "verification")
    if outcome != FAILED:
        user.verification_email_sent_at = timezone.now()
        user.save(update_fields=["verification_email_sent_at"])
    return outcome


def send_verified_confirmation(user):
    message = (
        f"Hello {user.first_name},\n\n"
        "Your email address has been verified and your Shipora account is ready. "
        f"You can now log in at {settings.FRONTEND_URL.rstrip('/')}/login\n\n"
        "The Shipora team"
    )
    return _send(user, "Your Shipora account is verified", message, "verification confirmation")
