from django.urls import path

from .views import ActiveCountryListView, CountryDetailView, CountryListView

app_name = "countries"

urlpatterns = [
    path("", CountryListView.as_view(), name="list"),
    path("active/", ActiveCountryListView.as_view(), name="active"),
    path("<int:pk>/", CountryDetailView.as_view(), name="detail"),
]
