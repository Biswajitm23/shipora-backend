"""SERV-001: service management (Admin) and the available services (logged-in users)."""

from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import MANAGE_SERVICES, HasAccess

from .models import Service
from .serializers import AvailableServiceSerializer, ServiceSerializer


class ServiceListView(generics.ListCreateAPIView):
    """GET /api/services/?search=&status=active|inactive, POST: create a service."""

    serializer_class = ServiceSerializer
    permission_classes = [HasAccess(MANAGE_SERVICES)]

    def get_queryset(self):
        services = Service.objects.all()
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            services = services.filter(Q(name__icontains=search) | Q(description__icontains=search))
        status = params.get("status")
        if status in ("active", "inactive"):
            services = services.filter(is_active=status == "active")
        return services


class ServiceDetailView(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/services/<id>/: view or update a service (incl. is_active)."""

    serializer_class = ServiceSerializer
    permission_classes = [HasAccess(MANAGE_SERVICES)]
    queryset = Service.objects.all()
    http_method_names = ["get", "patch", "options"]


class AvailableServiceListView(generics.ListAPIView):
    """GET /api/services/available/: only the services currently available."""

    serializer_class = AvailableServiceSerializer
    permission_classes = [IsAuthenticated]
    queryset = Service.objects.available()
