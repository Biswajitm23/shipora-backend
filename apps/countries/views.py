"""CNTRY-001: country management (Admin) and the active countries for shipments."""

from django.db.models import Q
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.accounts.permissions import MANAGE_COUNTRIES, HasAccess

from .models import Country
from .serializers import CountryOptionSerializer, CountrySerializer


class CountryListView(generics.ListCreateAPIView):
    """GET /api/countries/?search=&status=active|inactive, POST: add a country."""

    serializer_class = CountrySerializer
    permission_classes = [HasAccess(MANAGE_COUNTRIES)]

    def get_queryset(self):
        countries = Country.objects.all()
        params = self.request.query_params
        search = params.get("search", "").strip()
        if search:
            countries = countries.filter(
                Q(name__icontains=search)
                | Q(code__iexact=search)
                | Q(currency__iexact=search)
                | Q(shipping_zone__icontains=search)
            )
        status = params.get("status")
        if status in ("active", "inactive"):
            countries = countries.filter(is_active=status == "active")
        return countries


class CountryDetailView(generics.RetrieveUpdateAPIView):
    """GET / PATCH /api/countries/<id>/: view or edit a country (incl. is_active)."""

    serializer_class = CountrySerializer
    permission_classes = [HasAccess(MANAGE_COUNTRIES)]
    queryset = Country.objects.all()
    http_method_names = ["get", "patch", "options"]


class ActiveCountryListView(generics.ListAPIView):
    """GET /api/countries/active/: the countries a new shipment can use (any logged-in user)."""

    serializer_class = CountryOptionSerializer
    permission_classes = [IsAuthenticated]
    queryset = Country.objects.active()
