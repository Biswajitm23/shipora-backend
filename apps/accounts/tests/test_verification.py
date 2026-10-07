"""AUTH-003: verification confirmation, already-verified links and new links."""

import re
from urllib.parse import parse_qs, urlsplit

import pytest

from apps.accounts.models import User
from apps.accounts.verification import make_token
from conftest import TEST_PASSWORD

VERIFY = "/api/auth/verify-email/"
RESEND = "/api/auth/resend-verification/"
LOGIN = "/api/auth/login/"
RESENT = (
    "If an account with this email address still needs verification, "
    "we have sent it a new verification link."
)


def token_from(message):
    link = re.search(r"\S+/verify-email\?\S+", message.body).group(0)
    return parse_qs(urlsplit(link).query)["token"][0]


@pytest.mark.django_db
class TestVerify:
    def test_first_use_verifies_and_sends_a_confirmation(self, api_client, customer, mailoutbox):
        response = api_client.post(VERIFY, {"token": make_token(customer)}, format="json")

        assert response.status_code == 200
        assert response.data == {
            "detail": "Your email address has been verified.",
            "already_verified": False,
        }
        customer.refresh_from_db()
        assert customer.email_verified is True
        assert len(mailoutbox) == 1
        assert mailoutbox[0].to == [customer.email]
        assert mailoutbox[0].subject == "Your Shipora account is verified"

    def test_already_verified_account_does_not_verify_again(self, api_client, customer, mailoutbox):
        token = make_token(customer)
        api_client.post(VERIFY, {"token": token}, format="json")

        response = api_client.post(VERIFY, {"token": token}, format="json")

        assert response.status_code == 200
        assert response.data["already_verified"] is True
        assert "already verified" in response.data["detail"]
        assert len(mailoutbox) == 1  # only the first confirmation

    def test_link_for_another_account_does_not_verify_this_one(self, api_client, customer):
        other = User.objects.create_user("other@example.com", TEST_PASSWORD)
        token = make_token(other)

        api_client.post(VERIFY, {"token": token}, format="json")

        customer.refresh_from_db()
        other.refresh_from_db()
        assert (customer.email_verified, other.email_verified) == (False, True)


@pytest.mark.django_db
class TestResend:
    def test_unverified_account_gets_a_new_working_link(self, api_client, customer, mailoutbox):
        response = api_client.post(RESEND, {"email": "Customer@Example.com"}, format="json")

        assert response.status_code == 200
        assert response.data == {"detail": RESENT}
        assert len(mailoutbox) == 1
        verify = api_client.post(VERIFY, {"token": token_from(mailoutbox[0])}, format="json")
        assert verify.status_code == 200
        customer.refresh_from_db()
        assert customer.email_verified is True

    @pytest.mark.parametrize("email", ["nobody@example.com", "verified@example.com"])
    def test_same_answer_and_no_email_otherwise(self, api_client, mailoutbox, email):
        User.objects.create_user("verified@example.com", TEST_PASSWORD, email_verified=True)

        response = api_client.post(RESEND, {"email": email}, format="json")

        assert response.status_code == 200
        assert response.data == {"detail": RESENT}
        assert mailoutbox == []

    def test_email_is_required(self, api_client):
        response = api_client.post(RESEND, {}, format="json")

        assert response.status_code == 400
        assert response.data["email"] == ["Please enter your email address."]


@pytest.mark.django_db
def test_login_tells_the_website_the_account_is_not_verified(api_client, customer):
    response = api_client.post(
        LOGIN, {"email": customer.email, "password": TEST_PASSWORD}, format="json"
    )

    assert response.status_code == 403
    assert response.data["code"] == "email_not_verified"
