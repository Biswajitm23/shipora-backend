from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegisterSerializer
from .verification import send_verification_email, user_for_token

INVALID_LINK = "This verification link is invalid or has expired."


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
