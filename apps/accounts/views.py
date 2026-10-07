from django.contrib.auth.models import update_last_login
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .models import User
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from .verification import send_verification_email, user_for_token

INVALID_LINK = "This verification link is invalid or has expired."
INVALID_LOGIN = "Incorrect email or password."
INACTIVE = "This account has been deactivated. Please contact Shipora support."
UNVERIFIED = (
    "Please verify your email address before logging in. "
    "Open the link in the verification email we sent you."
)


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register/ — anonymous sign-up; emails a verification link."""

    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []

    def perform_create(self, serializer):
        send_verification_email(serializer.save())


class VerifyEmailView(APIView):
    """POST /api/auth/verify-email/ — {"token"} from the emailed link."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        user = user_for_token(str(request.data.get("token", "")))
        if user is None:
            return Response({"detail": INVALID_LINK}, status=status.HTTP_400_BAD_REQUEST)
        if not user.email_verified:
            user.email_verified = True
            user.save(update_fields=["email_verified"])
        return Response({"detail": "Your email address has been verified."})


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
            return Response({"detail": UNVERIFIED}, status=status.HTTP_403_FORBIDDEN)

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
