"""USER-002: the Admin's user account management."""

from django.db.models import Q, Value
from django.db.models.functions import Concat
from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .models import User
from .permissions import IsAdmin
from .serializers import AdminUserSerializer

SELF_DEACTIVATE = "You cannot deactivate your own account."


class UserListView(generics.ListAPIView):
    """GET /api/users/?search=&role=&status=active|inactive — every account, newest first."""

    serializer_class = AdminUserSerializer
    permission_classes = [IsAdmin]

    def get_queryset(self):
        users = User.objects.order_by("-date_joined", "-id")
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            users = users.annotate(full_name=Concat("first_name", Value(" "), "last_name")).filter(
                Q(full_name__icontains=search)
                | Q(email__icontains=search)
                | Q(phone__icontains=search)
            )
        if params.get("role") in User.Role.values:
            users = users.filter(role=params["role"])
        status = params.get("status")
        if status in ("active", "inactive"):
            users = users.filter(is_active=status == "active")
        return users


class UserStatusView(generics.UpdateAPIView):
    """PATCH /api/users/<id>/ {is_active} — activate or deactivate an account."""

    serializer_class = AdminUserSerializer
    permission_classes = [IsAdmin]
    queryset = User.objects.all()
    http_method_names = ["patch", "options"]

    def perform_update(self, serializer):
        deactivating = serializer.validated_data.get("is_active") is False
        if deactivating and serializer.instance == self.request.user:
            raise ValidationError({"is_active": [SELF_DEACTIVATE]})
        serializer.save()
