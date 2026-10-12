"""SERV-001: the Admin manages the delivery services; customers see the available ones."""

from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.services.models import Service
from conftest import TEST_PASSWORD

SERVICES = "/api/services/"
AVAILABLE = "/api/services/available/"

INITIAL = {
    "Standard Delivery",
    "Express Delivery",
    "International Shipping",
    "Same Day Delivery",
    "Document Delivery",
    "Package Delivery",
}


def detail(service):
    return f"{SERVICES}{service.pk}/"


def payload(**overrides):
    data = {
        "name": "Fragile Delivery",
        "description": "Extra care for fragile items.",
        "estimated_delivery": "2-4 business days",
        "weight_limit_kg": "15",
        "is_international": False,
    }
    data.update(overrides)
    return data


def login_as(api_client, role):
    user = User.objects.create_user(
        f"{role.lower()}@example.com", TEST_PASSWORD, role=role, email_verified=True
    )
    api_client.force_authenticate(user)
    return api_client


@pytest.fixture
def admin_client(api_client, db):
    return login_as(api_client, User.Role.ADMIN)


@pytest.mark.django_db
class TestInitialServices:
    def test_the_six_initial_services_exist_and_are_available(self):
        services = Service.objects.all()

        assert set(services.values_list("name", flat=True)) == INITIAL
        assert all(s.is_active for s in services)
        assert Service.objects.get(name="International Shipping").is_international


@pytest.mark.django_db
class TestCreateAndUpdate:
    def test_admin_creates_a_service(self, admin_client):
        response = admin_client.post(SERVICES, payload(), format="json")

        assert response.status_code == 201
        assert response.data["weight_limit_kg"] == "15.00"
        assert response.data["is_active"] is True

    def test_every_field_is_required(self, admin_client):
        response = admin_client.post(SERVICES, {}, format="json")

        assert response.status_code == 400
        assert set(response.data) == {
            "name",
            "description",
            "estimated_delivery",
            "weight_limit_kg",
        }

    @pytest.mark.parametrize("weight", ["0", "-2", "heavy"])
    def test_weight_limit_must_be_positive(self, admin_client, weight):
        response = admin_client.post(SERVICES, payload(weight_limit_kg=weight), format="json")

        assert response.status_code == 400
        assert "weight_limit_kg" in response.data

    def test_duplicate_name_is_prevented(self, admin_client):
        response = admin_client.post(SERVICES, payload(name="express  delivery"), format="json")

        assert response.status_code == 400
        assert "already exists" in response.data["name"][0]

    def test_admin_updates_a_service(self, admin_client):
        service = Service.objects.get(name="Express Delivery")

        response = admin_client.patch(
            detail(service), {"estimated_delivery": "Next day", "weight_limit_kg": "25"}
        )

        assert response.status_code == 200
        service.refresh_from_db()
        assert service.estimated_delivery == "Next day"
        assert service.weight_limit_kg == Decimal("25")

    def test_admin_activates_and_deactivates(self, admin_client):
        service = Service.objects.get(name="Same Day Delivery")

        assert admin_client.patch(detail(service), {"is_active": False}).data["is_active"] is False
        assert admin_client.patch(detail(service), {"is_active": True}).data["is_active"] is True

    def test_search_and_status_filter(self, admin_client):
        Service.objects.filter(name="Document Delivery").update(is_active=False)

        def names(query):
            return [s["name"] for s in admin_client.get(f"{SERVICES}?{query}").data]

        assert names("search=express") == ["Express Delivery"]
        assert names("status=inactive") == ["Document Delivery"]
        assert "Document Delivery" not in names("status=active")


@pytest.mark.django_db
class TestCustomersSeeAvailableServices:
    def test_only_available_services_with_their_limits(self, api_client):
        Service.objects.filter(name="Same Day Delivery").update(is_active=False)
        login_as(api_client, User.Role.CUSTOMER)

        response = api_client.get(AVAILABLE)

        assert response.status_code == 200
        names = [s["name"] for s in response.data]
        assert set(names) == INITIAL - {"Same Day Delivery"}
        assert set(response.data[0]) == {
            "id",
            "name",
            "description",
            "estimated_delivery",
            "weight_limit_kg",
            "is_international",
        }


@pytest.mark.django_db
class TestAccess:
    @pytest.mark.parametrize("role", [User.Role.CUSTOMER, User.Role.STAFF, User.Role.AGENT])
    def test_only_admin_manages_services(self, api_client, role):
        service = Service.objects.first()
        login_as(api_client, role)

        assert api_client.get(SERVICES).status_code == 403
        assert api_client.post(SERVICES, payload(), format="json").status_code == 403
        assert api_client.patch(detail(service), {"is_active": False}).status_code == 403

    def test_anonymous_is_refused(self, api_client, db):
        assert api_client.get(SERVICES).status_code == 401
        assert api_client.get(AVAILABLE).status_code == 401
