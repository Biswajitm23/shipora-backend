from django.urls import path

from .views import AvailableServiceListView, ServiceDetailView, ServiceListView

app_name = "services"

urlpatterns = [
    path("", ServiceListView.as_view(), name="list"),
    path("available/", AvailableServiceListView.as_view(), name="available"),
    path("<int:pk>/", ServiceDetailView.as_view(), name="detail"),
]
