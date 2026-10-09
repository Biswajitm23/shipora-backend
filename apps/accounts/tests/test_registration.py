"""AUTH-001: customer registration and the emailed verification link."""

import re
from urllib.parse import parse_qs, urlsplit

import pytest

from apps.accounts.models import User
from apps.accounts.permissions import ACCESS_RULES
from apps.accounts.verification import make_token

REGISTER = "/api/auth/register/"
VERIFY = "/api/auth/verify-email/"
PASSWORD = "Tr1cky-Harbour-42"


def payload(**overrides):
    data = {
        "first_name": "Riya",
        "last_name": "Sen",
        "email": "Riya.Sen@Example.com",
        "phone": "+91 98765 43210",
        "password": PASSWORD,
        "password_confirm": PASSWORD,
    }
    data.update(overrides)
    return data


def token_from(message):
    """The token as the verify page reads it: the emailed link's query, URL-decoded."""
    link = re.search(r"\S+/verify-email\?\S+", message.body).group(0)
    return parse_qs(urlsplit(link).query)["token"][0]


@pytest.mark.django_db
class TestRegister:
    def test_creates_unverified_customer_and_emails_link(self, api_client, mailoutbox):
        response = api_client.post(REGISTER, payload(), format="json")

        assert response.status_code == 201
        user = User.objects.get()
        assert user.email == "riya.sen@example.com"
        assert (user.first_name, user.last_name, user.phone) == ("Riya", "Sen", "+91 98765 43210")
        assert user.role == User.Role.CUSTOMER
        assert user.email_verified is False
        assert user.check_password(PASSWORD)
        assert response.data == {
            "id": user.pk,
            "email": "riya.sen@example.com",
            "first_name": "Riya",
            "last_name": "Sen",
            "phone": "+91 98765 43210",
            "role": "CUSTOMER",
            "email_verified": False,
            "permissions": sorted(ACCESS_RULES[User.Role.CUSTOMER]),
        }
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == ["riya.sen@example.com"]
        assert "http://localhost:3000/verify-email?token=" in mailoutbox[0].body

    def test_role_cannot_be_chosen(self, api_client, mailoutbox):
        response = api_client.post(REGISTER, payload(role="ADMIN"), format="json")

        assert response.status_code == 201
        assert User.objects.get().role == User.Role.CUSTOMER

    def test_email_must_be_unique_ignoring_case(self, api_client, mailoutbox):
        api_client.post(REGISTER, payload(), format="json")
        response = api_client.post(REGISTER, payload(email="RIYA.SEN@example.com"), format="json")

        assert response.status_code == 400
        assert response.data["email"] == ["An account with this email address already exists."]
        assert User.objects.count() == 1

    def test_passwords_must_match(self, api_client):
        response = api_client.post(
            REGISTER, payload(password_confirm="Other-Pass-99"), format="json"
        )

        assert response.status_code == 400
        assert response.data["password_confirm"] == ["Passwords do not match."]

    def test_every_field_is_required(self, api_client):
        response = api_client.post(REGISTER, {"first_name": "  "}, format="json")

        assert response.status_code == 400
        assert set(response.data) == {
            "first_name",
            "last_name",
            "email",
            "phone",
            "password",
            "password_confirm",
        }
        assert response.data["first_name"] == ["Please enter your first name."]

    @pytest.mark.parametrize(
        ("field", "value"),
        [("email", "not-an-email"), ("phone", "12345"), ("phone", "call me maybe")],
    )
    def test_invalid_details_are_rejected(self, api_client, field, value):
        response = api_client.post(REGISTER, payload(**{field: value}), format="json")

        assert response.status_code == 400
        assert field in response.data

    def test_weak_password_is_rejected(self, api_client):
        response = api_client.post(
            REGISTER, payload(password="12345678", password_confirm="12345678"), format="json"
        )

        assert response.status_code == 400
        assert "password" in response.data
        assert not User.objects.exists()


@pytest.mark.django_db
class TestVerifyEmail:
    def test_emailed_link_verifies_the_account(self, api_client, mailoutbox):
        api_client.post(REGISTER, payload(), format="json")

        response = api_client.post(VERIFY, {"token": token_from(mailoutbox[0])}, format="json")

        assert response.status_code == 200
        assert User.objects.get().email_verified is True

    @pytest.mark.parametrize("token", ["", "garbage", "eyJ1aWQiOjF9:bad:signature"])
    def test_invalid_token_is_rejected(self, api_client, customer, token):
        response = api_client.post(VERIFY, {"token": token}, format="json")

        assert response.status_code == 400
        assert response.data == {"detail": "This verification link is invalid or has expired."}
        customer.refresh_from_db()
        assert customer.email_verified is False

    def test_expired_token_is_rejected(self, api_client, customer, settings):
        token = make_token(customer)
        settings.EMAIL_VERIFICATION_MAX_AGE = -1

        response = api_client.post(VERIFY, {"token": token}, format="json")

        assert response.status_code == 400

    def test_token_only_works_for_the_address_it_was_sent_to(self, api_client, customer):
        token = make_token(customer)
        customer.email = "someone.else@example.com"
        customer.save()

        response = api_client.post(VERIFY, {"token": token}, format="json")

        assert response.status_code == 400
