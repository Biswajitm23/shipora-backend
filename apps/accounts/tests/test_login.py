"""AUTH-002: one login for every account type, refresh and the current user."""

import pytest

from apps.accounts.models import User
from conftest import TEST_PASSWORD

LOGIN = "/api/auth/login/"
REFRESH = "/api/auth/refresh/"
ME = "/api/auth/me/"


def make_user(role=User.Role.CUSTOMER, **extra):
    extra.setdefault("email_verified", True)
    return User.objects.create_user(
        f"{role.lower()}@example.com", TEST_PASSWORD, first_name="Sam", role=role, **extra
    )


def login(client, email, password=TEST_PASSWORD):
    return client.post(LOGIN, {"email": email, "password": password}, format="json")


@pytest.mark.django_db
class TestLogin:
    @pytest.mark.parametrize("role", list(User.Role))
    def test_every_account_type_logs_in_on_the_same_page(self, api_client, role):
        user = make_user(role)

        response = login(api_client, user.email)

        assert response.status_code == 200
        assert response.data["access"] and response.data["refresh"]
        assert response.data["user"]["role"] == role
        user.refresh_from_db()
        assert user.last_login is not None

    def test_email_is_matched_ignoring_case(self, api_client):
        make_user()

        assert login(api_client, "Customer@Example.COM").status_code == 200

    @pytest.mark.parametrize("email", ["customer@example.com", "nobody@example.com"])
    def test_wrong_details_get_one_clear_message(self, api_client, email):
        make_user()

        response = login(api_client, email, "Wrong-Password-1")

        assert response.status_code == 400
        assert response.data == {"detail": "Incorrect email or password."}

    def test_missing_details_are_reported_per_field(self, api_client):
        response = api_client.post(LOGIN, {}, format="json")

        assert response.status_code == 400
        assert set(response.data) == {"email", "password"}

    def test_deactivated_account_cannot_log_in(self, api_client):
        user = make_user(is_active=False)

        response = login(api_client, user.email)

        assert response.status_code == 403
        assert "deactivated" in response.data["detail"]

    def test_unverified_account_cannot_log_in(self, api_client, customer):
        response = login(api_client, customer.email)

        assert response.status_code == 403
        assert "verify your email" in response.data["detail"]

    def test_deactivated_account_is_refused_with_wrong_password_message(self, api_client):
        user = make_user(is_active=False)

        response = login(api_client, user.email, "Wrong-Password-1")

        assert response.status_code == 400
        assert response.data == {"detail": "Incorrect email or password."}


@pytest.mark.django_db
class TestSession:
    def test_me_returns_the_logged_in_user(self, api_client):
        user = make_user(User.Role.STAFF)
        access = login(api_client, user.email).data["access"]

        response = api_client.get(ME, HTTP_AUTHORIZATION=f"Bearer {access}")

        assert response.status_code == 200
        assert response.data["email"] == user.email
        assert response.data["role"] == "STAFF"

    def test_me_requires_login(self, api_client):
        assert api_client.get(ME).status_code == 401

    def test_refresh_gives_a_new_access_token(self, api_client):
        user = make_user()
        refresh = login(api_client, user.email).data["refresh"]

        response = api_client.post(REFRESH, {"refresh": refresh}, format="json")

        assert response.status_code == 200
        assert response.data["access"]

    def test_deactivating_an_account_ends_its_session(self, api_client):
        user = make_user()
        tokens = login(api_client, user.email).data
        user.is_active = False
        user.save()

        me = api_client.get(ME, HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        refreshed = api_client.post(REFRESH, {"refresh": tokens["refresh"]}, format="json")

        assert me.status_code == 401
        assert refreshed.status_code == 401
