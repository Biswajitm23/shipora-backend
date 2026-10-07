"""USER-002: the Admin views, searches, activates and deactivates accounts."""

import pytest

from apps.accounts.models import User
from conftest import TEST_PASSWORD

USERS = "/api/users/"
LOGIN = "/api/auth/login/"


def make(email, role=User.Role.CUSTOMER, **extra):
    extra.setdefault("email_verified", True)
    return User.objects.create_user(email, TEST_PASSWORD, role=role, **extra)


@pytest.fixture
def admin(db):
    return make("admin@example.com", User.Role.ADMIN, first_name="Ada", last_name="Admin")


@pytest.fixture
def admin_client(api_client, admin):
    api_client.force_authenticate(admin)
    return api_client


@pytest.fixture
def people(db):
    return {
        "riya": make("riya@example.com", first_name="Riya", last_name="Sen", phone="+91 98765"),
        "sam": make("sam@example.com", User.Role.STAFF, first_name="Sam", last_name="Staff"),
        "ali": make("ali@example.com", User.Role.AGENT, first_name="Ali", is_active=False),
    }


def emails(response):
    return {row["email"] for row in response.data}


@pytest.mark.django_db
class TestList:
    def test_admin_sees_every_account_with_type_and_status(self, admin_client, people):
        response = admin_client.get(USERS)

        assert response.status_code == 200
        assert emails(response) == {
            "admin@example.com",
            "riya@example.com",
            "sam@example.com",
            "ali@example.com",
        }
        ali = next(row for row in response.data if row["email"] == "ali@example.com")
        assert (ali["role"], ali["is_active"]) == ("AGENT", False)

    @pytest.mark.parametrize(
        ("search", "expected"),
        [
            ("riya sen", {"riya@example.com"}),
            ("SEN", {"riya@example.com"}),
            ("sam@", {"sam@example.com"}),
            ("98765", {"riya@example.com"}),
            ("nobody", set()),
        ],
    )
    def test_search_by_name_email_or_phone(self, admin_client, people, search, expected):
        assert emails(admin_client.get(USERS, {"search": search})) == expected

    def test_filter_by_account_type_and_status(self, admin_client, people):
        assert emails(admin_client.get(USERS, {"role": "STAFF"})) == {"sam@example.com"}
        assert emails(admin_client.get(USERS, {"status": "inactive"})) == {"ali@example.com"}

    @pytest.mark.parametrize("role", [User.Role.CUSTOMER, User.Role.STAFF, User.Role.AGENT])
    def test_other_account_types_cannot_manage_users(self, api_client, role):
        api_client.force_authenticate(make(f"{role.lower()}@x.com", role))

        assert api_client.get(USERS).status_code == 403

    def test_login_required(self, api_client):
        assert api_client.get(USERS).status_code == 401


@pytest.mark.django_db
class TestStatus:
    def test_deactivated_account_cannot_log_in_and_can_be_activated_again(
        self, admin_client, api_client, people
    ):
        riya = people["riya"]

        response = admin_client.patch(f"{USERS}{riya.pk}/", {"is_active": False}, format="json")

        assert response.status_code == 200
        assert response.data["is_active"] is False
        api_client.force_authenticate(None)
        login = {"email": riya.email, "password": TEST_PASSWORD}
        assert api_client.post(LOGIN, login, format="json").status_code == 403

        api_client.force_authenticate(User.objects.get(email="admin@example.com"))
        admin_client.patch(f"{USERS}{riya.pk}/", {"is_active": True}, format="json")
        api_client.force_authenticate(None)
        assert api_client.post(LOGIN, login, format="json").status_code == 200

    def test_only_the_status_can_change(self, admin_client, people):
        sam = people["sam"]

        admin_client.patch(
            f"{USERS}{sam.pk}/", {"role": "ADMIN", "email": "x@x.com"}, format="json"
        )

        sam.refresh_from_db()
        assert (sam.role, sam.email) == ("STAFF", "sam@example.com")

    def test_admin_cannot_deactivate_themselves(self, admin_client, admin):
        response = admin_client.patch(f"{USERS}{admin.pk}/", {"is_active": False}, format="json")

        assert response.status_code == 400
        assert response.data["is_active"] == ["You cannot deactivate your own account."]
        admin.refresh_from_db()
        assert admin.is_active is True

    def test_customer_cannot_change_another_account(self, api_client, people):
        api_client.force_authenticate(people["riya"])

        response = api_client.patch(
            f"{USERS}{people['sam'].pk}/", {"is_active": False}, format="json"
        )

        assert response.status_code == 403
        people["sam"].refresh_from_db()
        assert people["sam"].is_active is True
