"""AUTH-003: verification confirmation, already-verified links and new links."""

import re
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core import signing
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.verification import SALT, make_token
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


# ---- Registration and verification fix: no account stays stuck unverified ----

REGISTER = "/api/auth/register/"
USERS = "/api/users/"
NEW_PASSWORD = "Qu1et-Lantern-87"
DUPLICATE = ["An account with this email address already exists."]


def registration(**overrides):
    data = {
        "first_name": "Cass",
        "last_name": "Client",
        "email": "Customer@Example.com",
        "phone": "+44 113 496 0002",
        "password": NEW_PASSWORD,
        "password_confirm": NEW_PASSWORD,
    }
    data.update(overrides)
    return data


@pytest.fixture
def mail_server_down(monkeypatch):
    def refuse(*args, **kwargs):
        raise OSError("mail server not reachable")

    monkeypatch.setattr("apps.accounts.verification.send_mail", refuse)


@pytest.mark.django_db
class TestRegisterAgain:
    def test_unverified_email_starts_registration_again(self, api_client, customer, mailoutbox):
        old_token = make_token(customer)

        response = api_client.post(REGISTER, registration(), format="json")

        assert response.status_code == 200
        assert response.data["restarted"] is True
        assert response.data["verification_email_sent"] is True
        assert "never verified" in response.data["detail"]
        assert User.objects.count() == 1  # the same account, no duplicate
        customer.refresh_from_db()
        assert (customer.first_name, customer.last_name) == ("Cass", "Client")
        assert customer.phone == "+44 113 496 0002"
        assert customer.check_password(NEW_PASSWORD)
        assert customer.email_verified is False
        assert [message.to for message in mailoutbox] == [[customer.email]]

        # The link sent before no longer works; the new one does.
        assert api_client.post(VERIFY, {"token": old_token}, format="json").status_code == 400
        verify = api_client.post(VERIFY, {"token": token_from(mailoutbox[0])}, format="json")
        assert verify.status_code == 200
        login = api_client.post(
            LOGIN, {"email": customer.email, "password": NEW_PASSWORD}, format="json"
        )
        assert login.status_code == 200

    def test_verified_email_cannot_be_registered_again(self, api_client, customer, mailoutbox):
        User.objects.filter(pk=customer.pk).update(email_verified=True)

        response = api_client.post(REGISTER, registration(), format="json")

        assert response.status_code == 400
        assert response.data["email"] == DUPLICATE
        customer.refresh_from_db()
        assert customer.check_password(TEST_PASSWORD)  # untouched
        assert customer.first_name == "Casey"
        assert mailoutbox == []

    @pytest.mark.parametrize(
        "changes", [{"is_active": False}, {"role": User.Role.STAFF}], ids=["deactivated", "staff"]
    )
    def test_other_unverified_accounts_are_not_restarted(
        self, api_client, customer, mailoutbox, changes
    ):
        User.objects.filter(pk=customer.pk).update(**changes)

        response = api_client.post(REGISTER, registration(), format="json")

        assert response.status_code == 400
        assert response.data["email"] == DUPLICATE
        customer.refresh_from_db()
        assert customer.check_password(TEST_PASSWORD)
        assert mailoutbox == []

    def test_admin_cannot_take_over_an_unverified_account(self, api_client, customer):
        admin = User.objects.create_user(
            "admin@example.com", TEST_PASSWORD, role=User.Role.ADMIN, email_verified=True
        )
        api_client.force_authenticate(admin)

        response = api_client.post(USERS, registration(role="STAFF"), format="json")

        assert response.status_code == 400
        assert response.data["email"] == DUPLICATE
        customer.refresh_from_db()
        assert customer.role == User.Role.CUSTOMER
        assert customer.check_password(TEST_PASSWORD)


@pytest.mark.django_db
class TestEmailNotSent:
    def test_registration_says_the_email_was_not_sent(self, api_client, mail_server_down):
        response = api_client.post(REGISTER, registration(), format="json")

        assert response.status_code == 201
        assert response.data["verification_email_sent"] is False
        assert "could not send the verification email" in response.data["detail"]
        # The account is kept: the user can ask for a new link or register again.
        assert User.objects.filter(email="customer@example.com", email_verified=False).exists()

    def test_registering_again_works_once_email_is_back(self, api_client, monkeypatch, mailoutbox):
        with monkeypatch.context() as broken:
            broken.setattr(
                "apps.accounts.verification.send_mail",
                lambda *args, **kwargs: (_ for _ in ()).throw(OSError("down")),
            )
            first = api_client.post(REGISTER, registration(), format="json")
        assert first.data["verification_email_sent"] is False

        second = api_client.post(REGISTER, registration(), format="json")

        assert second.status_code == 200
        assert second.data["verification_email_sent"] is True
        assert User.objects.count() == 1
        verify = api_client.post(VERIFY, {"token": token_from(mailoutbox[0])}, format="json")
        assert verify.status_code == 200

    def test_resend_says_the_email_was_not_sent(self, api_client, customer, mail_server_down):
        response = api_client.post(RESEND, {"email": customer.email}, format="json")

        assert response.status_code == 503
        assert response.data["code"] == "email_not_sent"
        assert "could not send the verification email" in response.data["detail"]

    def test_resend_stays_generic_for_other_emails(self, api_client, mail_server_down):
        response = api_client.post(RESEND, {"email": "nobody@example.com"}, format="json")

        assert response.status_code == 200
        assert response.data == {"detail": RESENT}

    def test_email_that_is_only_logged_counts_as_not_sent(self, api_client, settings, caplog):
        settings.DEBUG = False
        settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

        response = api_client.post(REGISTER, registration(), format="json")

        assert response.status_code == 201
        assert response.data["verification_email_sent"] is False
        assert "Email delivery is not configured" in caplog.text


@pytest.mark.django_db
def test_link_sent_before_the_fix_still_verifies(api_client, customer):
    old_style = signing.dumps({"uid": customer.pk, "email": customer.email}, salt=SALT)

    response = api_client.post(VERIFY, {"token": old_style}, format="json")

    assert response.status_code == 200
    customer.refresh_from_db()
    assert customer.email_verified is True


@pytest.mark.django_db
class TestResendCooldown:
    def test_second_request_has_to_wait(self, api_client, customer, mailoutbox):
        first = api_client.post(RESEND, {"email": customer.email}, format="json")
        second = api_client.post(RESEND, {"email": customer.email}, format="json")

        assert first.status_code == 200
        assert second.status_code == 429
        assert second.data["code"] == "resend_too_soon"
        assert "Please wait" in second.data["detail"]
        assert 0 < int(second["Retry-After"]) <= 60
        assert len(mailoutbox) == 1

    def test_a_new_link_can_be_sent_after_the_wait(self, api_client, customer, mailoutbox):
        api_client.post(RESEND, {"email": customer.email}, format="json")
        User.objects.filter(pk=customer.pk).update(
            verification_email_sent_at=timezone.now() - timedelta(seconds=61)
        )

        response = api_client.post(RESEND, {"email": customer.email}, format="json")

        assert response.status_code == 200
        assert len(mailoutbox) == 2
        verify = api_client.post(VERIFY, {"token": token_from(mailoutbox[1])}, format="json")
        assert verify.status_code == 200

    def test_registering_again_has_to_wait_too(self, api_client, mailoutbox):
        first = api_client.post(REGISTER, registration(), format="json")
        again = api_client.post(
            REGISTER,
            registration(password="An0ther-Harbour-55", password_confirm="An0ther-Harbour-55"),
            format="json",
        )

        assert first.status_code == 201
        assert again.status_code == 429
        assert again.data["code"] == "resend_too_soon"
        user = User.objects.get()
        assert user.check_password(NEW_PASSWORD)  # nothing was changed
        assert len(mailoutbox) == 1
        # The link already sent still works.
        verify = api_client.post(VERIFY, {"token": token_from(mailoutbox[0])}, format="json")
        assert verify.status_code == 200

    def test_a_failed_send_does_not_start_the_wait(self, api_client, customer, mail_server_down):
        api_client.post(RESEND, {"email": customer.email}, format="json")

        customer.refresh_from_db()
        assert customer.verification_email_sent_at is None


@pytest.fixture
def local_mailbox(settings, tmp_path):
    """Local development: emails are kept as files, never delivered."""
    settings.DEBUG = True
    settings.EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    settings.EMAIL_FILE_PATH = tmp_path
    return tmp_path


def link_token(text):
    link = re.search(r"\S+/verify-email\?\S+", text).group(0)
    return parse_qs(urlsplit(link).query)["token"][0]


@pytest.mark.django_db
class TestLocalMailbox:
    def test_registration_says_the_email_was_only_saved_locally(self, api_client, local_mailbox):
        response = api_client.post(REGISTER, registration(), format="json")

        assert response.status_code == 201
        assert response.data["email_delivery"] == "captured"
        assert response.data["verification_email_sent"] is False
        assert "local test mailbox" in response.data["detail"]
        (saved,) = Path(local_mailbox).iterdir()
        text = saved.read_text()
        assert "To: customer@example.com" in text
        verify = api_client.post(VERIFY, {"token": link_token(text)}, format="json")
        assert verify.status_code == 200
        assert User.objects.get().email_verified is True

    @pytest.mark.parametrize("email", ["customer@example.com", "nobody@example.com"])
    def test_resend_says_so_whatever_the_email(self, api_client, customer, local_mailbox, email):
        response = api_client.post(RESEND, {"email": email}, format="json")

        assert response.status_code == 200
        assert response.data["email_delivery"] == "captured"
        assert "local test mailbox" in response.data["detail"]
        saved = list(Path(local_mailbox).iterdir())
        assert len(saved) == (1 if email == customer.email else 0)

    def test_a_local_mailbox_does_not_count_outside_development(
        self, api_client, local_mailbox, settings
    ):
        settings.DEBUG = False

        response = api_client.post(REGISTER, registration(), format="json")

        assert response.data["email_delivery"] == "failed"
        assert list(Path(local_mailbox).iterdir()) == []
