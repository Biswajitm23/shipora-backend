"""Root URL configuration.

Only `/api/` is mounted. There is no `/admin/` route by design.
"""

from django.http import JsonResponse
from django.urls import include, path


def api_root(_request):
    """Liveness/smoke endpoint for the API."""
    return JsonResponse({"service": "shipora", "status": "ok"})


urlpatterns = [
    path("api/", api_root, name="api-root"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/users/", include("apps.accounts.user_urls")),
    path("api/countries/", include("apps.countries.urls")),
]
