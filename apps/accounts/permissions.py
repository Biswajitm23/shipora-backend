from rest_framework.permissions import BasePermission

from .models import User


class IsAdmin(BasePermission):
    """Logged-in Admin accounts only. (ROLE-002 builds the full access rules.)"""

    message = "Only an Admin can do this."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == User.Role.ADMIN)
