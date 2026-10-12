from django.contrib.auth.models import update_last_login
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import User
from .serializers import (
    LoginSerializer,
    RegisterSerializer,
    ResendVerificationSerializer,
    UserSerializer,
)
from .verification import (
    CAPTURED,
    FAILED,
    SENT,
    capturing_locally,
    seconds_until_resend,
    send_verification_email,
    send_verified_confirmation,
    user_for_token,
)

INVALID_LINK = "This verification link is invalid or has expired."
VERIFIED = "Your email address has been verified."
ALREADY_VERIFIED = "Your email address is already verified. You can log in."
RESENT = (
    "If an account with this email address still needs verification, "
    "we have sent it a new verification link."
)
CREATED = "Your account has been created."
RESTARTED = (
    "This email address was registered before but never verified. We have saved your new details."
)
LINK_SENT = "We have sent a verification link to your email address."
# Local development: the email never leaves this machine, and the page says so.
LINK_CAPTURED = (
    "This is a local test setup, so no email goes to a real inbox: "
    "the verification email was saved in the local test mailbox."
)
LINK_NOT_SENT = (
    "We could not send the verification email. "
    "Please ask for a new verification link in a few minutes."
)
RESENT_CAPTURED = (
    "This is a local test setup, so no email goes to a real inbox. If an account with "
    "this email address still needs verification, its new verification link was saved "
    "in the local test mailbox."
)
NOT_SENT = "We could not send the verification email right now. Please try again in a few minutes."
TOO_SOON = (
    "A verification email was sent to this address a moment ago. "
    "Please wait {seconds} seconds before asking for another one."
)
INVALID_LOGIN = "Incorrect email or password."
INACTIVE = "This account has been deactivated. Please contact Shipora support."
UNVERIFIED = (
    "Please verify your email address before logging in. "
    "Open the link in the verification email we sent you."
)


def too_soon(seconds):
    """429: this account was sent a verification email a moment ago."""
    return Response(
        {"detail": TOO_SOON.format(seconds=seconds), "code": "resend_too_soon"},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
        headers={"Retry-After": str(seconds)},
    )


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — anonymous sign-up; emails a verification link.

    The answer says what happened: `detail` (the message to show), `email_delivery`
    ("sent", "captured" in local development, or "failed"),
    `verification_email_sent` (true only for "sent"), and `restarted` when the
    email belonged to an account that was never verified (200 instead of 201).
    Starting again waits for the resend cooldown (429) like any new link.
    """

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if serializer.unverified_account is not None:
            wait = seconds_until_resend(serializer.unverified_account)
            if wait:
                return too_soon(wait)
        user = serializer.save()
        outcome = send_verification_email(user)
        link = {SENT: LINK_SENT, CAPTURED: LINK_CAPTURED, FAILED: LINK_NOT_SENT}[outcome]
        return Response(
            {
                **serializer.data,
                "detail": f"{RESTARTED if serializer.restarted else CREATED} {link}",
                "email_delivery": outcome,
                "verification_email_sent": outcome == SENT,
                "restarted": serializer.restarted,
            },
            status=status.HTTP_200_OK if serializer.restarted else status.HTTP_201_CREATED,
        )


class VerifyEmailView(APIView):
    """POST /api/auth/verify-email/ — {"token"} from the emailed link."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        user = user_for_token(str(request.data.get("token", "")))
        if user is None:
            return Response({"detail": INVALID_LINK}, status=status.HTTP_400_BAD_REQUEST)
        if user.email_verified:
            return Response({"detail": ALREADY_VERIFIED, "already_verified": True})
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        send_verified_confirmation(user)
        return Response({"detail": VERIFIED, "already_verified": False})


class ResendVerificationView(APIView):
    """POST /api/auth/resend-verification/ — {"email"}: a new link for an unverified
    account. The answer is the same whatever the email, so it reveals nothing; only
    an account that has to wait (429, `resend_too_soon`) or whose link could not be
    sent (503, `email_not_sent`) is told so."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = ResendVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(
            email__iexact=serializer.validated_data["email"], email_verified=False
        ).first()
        if user is not None:
            wait = seconds_until_resend(user)
            if wait:
                return too_soon(wait)
            if send_verification_email(user) == FAILED:
                return Response(
                    {"detail": NOT_SENT, "code": "email_not_sent"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        if capturing_locally():
            return Response({"detail": RESENT_CAPTURED, "email_delivery": CAPTURED})
        return Response({"detail": RESENT})


class LoginView(APIView):
    """POST /api/auth/login/ — {email, password} -> {access, refresh, user}.

    One login for every account type. Wrong details get one message whether or not
    the email exists; a deactivated or unverified account is only told so once the
    password is right.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            User().set_password(password)  # same hashing work: no hint the email is unknown
            return Response({"detail": INVALID_LOGIN}, status=status.HTTP_400_BAD_REQUEST)
        if not user.check_password(password):
            return Response({"detail": INVALID_LOGIN}, status=status.HTTP_400_BAD_REQUEST)
        if not user.is_active:
            return Response({"detail": INACTIVE}, status=status.HTTP_403_FORBIDDEN)
        if not user.email_verified:
            return Response(
                {"detail": UNVERIFIED, "code": "email_not_verified"},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(user)
        update_last_login(None, user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "user": UserSerializer(user).data,
            }
        )


class RefreshView(TokenRefreshView):
    """POST /api/auth/refresh/ — {"refresh"} -> {"access"}; refused for deactivated accounts."""


class MeView(generics.RetrieveAPIView):
    """GET /api/auth/me/ — the logged-in user."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user
