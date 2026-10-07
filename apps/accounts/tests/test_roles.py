"""ROLE-001: the four account types, created with the right type and never changed by
their owner."""

import pytest

from apps.accounts.models import User
from conftest import TEST_PASSWORD

USERS = "/api/users/"
LOGIN = "/api/auth/login/"
ME = "/api/auth/me/"
REGISTER = "/api/auth/register/"


def new_account(**overrides):
    data = {
        "first_name": "Sam",
        "last_name": "Staff",
        "email": "Sam.Staff@Example.com",
        "phone": "+44 113 496 0001",
        "role": "STAFF",
        "password": TEST_PASSWORD,
        "password_confirm": TEST_PASSWORD,
    }
    data.update(overrides)
    return data


@pytest.fixture
def admin_client(api_client, db):
    admin = User.objects.create_user(
        "admin@example.com", TEST_PASSWORD, role=User.Role.ADMIN, email_verified=True
    )
    api_client.force_authenticate(admin)
    return api_client


@pytest.mark.django_db
class TestAccountTypes:
    def test_all_four_types_exist(self):
        assert dict(User.Role.choices) == {
            "CUSTOMER": "Customer",
            "STAFF": "Logistics Staff",
            "AGENT": "Delivery Agent",
            "ADMIN": "Admin",
        }

    @pytest.mark.parametrize("role", list(User.Role))
    def test_admin_adds_an_account_of_each_type_that_can_log_in(
        self, admin_client, api_client, role
    ):
        response = admin_client.post(
            USERS, new_account(role=role, email=f"new.{role.lower()}@example.com"), format="json"
        )

        assert response.status_code == 201
        assert response.data["role"] == role
        assert response.data["is_active"] is True
        assert response.data["email_verified"] is True
        api_client.force_authenticate(None)
        login = api_client.post(
            LOGIN, {"email": f"new.{role.lower()}@example.com", "password": TEST_PASSWORD}
        )
        assert login.status_code == 200
        assert login.data["user"]["role"] == role

    def test_new_account_is_checked_like_a_registration(self, admin_client):
        User.objects.create_user("taken@example.com", TEST_PASSWORD)

        response = admin_client.post(
            USERS,
            new_account(email="TAKEN@example.com", role="BOSS", password_confirm="Other-Pass-99"),
            format="json",
        )

        assert response.status_code == 400
        assert set(response.data) >= {"email", "role"}

    @pytest.mark.parametrize("role", [User.Role.CUSTOMER, User.Role.STAFF, User.Role.AGENT])
    def test_only_an_admin_can_add_accounts(self, api_client, role):
        user = User.objects.create_user(f"{role.lower()}@x.com", TEST_PASSWORD, role=role)
        api_client.force_authenticate(user)

        response = api_client.post(USERS, new_account(role="ADMIN"), format="json")

        assert response.status_code == 403
        assert not User.objects.filter(email="sam.staff@example.com").exists()


@pytest.mark.django_db
class TestOwnTypeCannotChange:
    def test_registration_ignores_a_requested_type(self, api_client):
        data = new_account(role="ADMIN")
        api_client.post(REGISTER, data, format="json")

        assert User.objects.get(email="sam.staff@example.com").role == User.Role.CUSTOMER

    def test_own_account_details_are_read_only(self, api_client):
        user = User.objects.create_user("riya@example.com", TEST_PASSWORD, email_verified=True)
        api_client.force_authenticate(user)

        response = api_client.patch(ME, {"role": "ADMIN"}, format="json")

        assert response.status_code == 405
        user.refresh_from_db()
        assert user.role == User.Role.CUSTOMER

    def test_admin_cannot_change_their_own_type(self, admin_client):
        admin = User.objects.get(email="admin@example.com")

        admin_client.patch(f"{USERS}{admin.pk}/", {"role": "CUSTOMER"}, format="json")

        admin.refresh_from_db()
        assert admin.role == User.Role.ADMIN
