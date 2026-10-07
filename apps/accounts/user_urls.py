from django.urls import path

from .user_views import UserListView, UserStatusView

app_name = "users"

urlpatterns = [
    path("", UserListView.as_view(), name="list"),
    path("<int:pk>/", UserStatusView.as_view(), name="status"),
]
