"""CNTRY-001: the Admin manages the countries Shipora ships to."""

from decimal import Decimal

import pytest

from apps.accounts.models import User
from apps.countries.models import Country
from conftest import TEST_PASSWORD

COUNTRIES = "/api/countries/"
ACTIVE = "/api/countries/active/"


def detail(country):
    return f"{COUNTRIES}{country.pk}/"


def payload(**overrides):
    data = {
        "name": "India",
        "code": "in",
        "currency": "inr",
        "currency_symbol": "₹",
        "shipping_zone": "Asia",
        "tax_percentage": "18.00",
    }
    data.update(overrides)
    return data


def make_country(**overrides):
    data = {
        "name": "United Kingdom",
        "code": "GB",
        "currency": "GBP",
        "currency_symbol": "£",
        "shipping_zone": "Europe",
        "tax_percentage": Decimal("20"),
    }
    data.update(overrides)
    return Country.objects.create(**data)


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
class TestAddCountry:
    def test_admin_adds_a_country(self, admin_client):
        response = admin_client.post(COUNTRIES, payload(), format="json")

        assert response.status_code == 201
        assert response.data["code"] == "IN"
        assert response.data["currency"] == "INR"
        assert response.data["tax_percentage"] == "18.00"
        assert response.data["is_active"] is True
        assert Country.objects.get().name == "India"

    def test_every_field_is_required(self, admin_client):
        response = admin_client.post(COUNTRIES, {}, format="json")

        assert response.status_code == 400
        assert set(response.data) == {
            "name",
            "code",
            "currency",
            "currency_symbol",
            "shipping_zone",
            "tax_percentage",
        }

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("code", "I"),
            ("code", "IN1"),
            ("currency", "RUPEE"),
            ("tax_percentage", "-1"),
            ("tax_percentage", "100.01"),
            ("tax_percentage", "abc"),
        ],
    )
    def test_invalid_values(self, admin_client, field, value):
        response = admin_client.post(COUNTRIES, payload(**{field: value}), format="json")

        assert response.status_code == 400
        assert field in response.data

    @pytest.mark.parametrize(
        ("field", "value"),
        [("name", "  united   KINGDOM "), ("code", "gb")],
    )
    def test_duplicates_are_prevented(self, admin_client, field, value):
        make_country()

        response = admin_client.post(COUNTRIES, payload(**{field: value}), format="json")

        assert response.status_code == 400
        assert "already exists" in response.data[field][0]
        assert Country.objects.count() == 1


@pytest.mark.django_db
class TestEditCountry:
    def test_admin_edits_a_country(self, admin_client):
        country = make_country()

        response = admin_client.patch(
            detail(country), {"tax_percentage": "17.5", "shipping_zone": "Europe West"}
        )

        assert response.status_code == 200
        country.refresh_from_db()
        assert country.tax_percentage == Decimal("17.50")
        assert country.shipping_zone == "Europe West"

    def test_keeping_its_own_name_and_code_is_not_a_duplicate(self, admin_client):
        country = make_country()

        response = admin_client.patch(detail(country), {"name": "United Kingdom", "code": "gb"})

        assert response.status_code == 200

    def test_cannot_take_another_countrys_code(self, admin_client):
        make_country()
        india = make_country(name="India", code="IN")

        response = admin_client.patch(detail(india), {"code": "GB"})

        assert response.status_code == 400
        assert "code" in response.data

    def test_activate_and_deactivate(self, admin_client):
        country = make_country()

        assert admin_client.patch(detail(country), {"is_active": False}).data["is_active"] is False
        assert admin_client.patch(detail(country), {"is_active": True}).data["is_active"] is True


@pytest.mark.django_db
class TestListCountries:
    def test_search_and_status_filter(self, admin_client):
        make_country()
        make_country(name="India", code="IN", shipping_zone="Asia", is_active=False)

        def names(query):
            return [c["name"] for c in admin_client.get(f"{COUNTRIES}?{query}").data]

        assert names("") == ["India", "United Kingdom"]
        assert names("search=king") == ["United Kingdom"]
        assert names("search=asia") == ["India"]
        assert names("status=inactive") == ["India"]
        assert names("status=active") == ["United Kingdom"]


@pytest.mark.django_db
class TestAccess:
    @pytest.mark.parametrize("role", [User.Role.CUSTOMER, User.Role.STAFF, User.Role.AGENT])
    def test_only_admin_manages_countries(self, api_client, role):
        country = make_country()
        login_as(api_client, role)

        assert api_client.get(COUNTRIES).status_code == 403
        assert api_client.post(COUNTRIES, payload(), format="json").status_code == 403
        assert api_client.patch(detail(country), {"is_active": False}).status_code == 403

    def test_anonymous_is_refused(self, api_client, db):
        assert api_client.get(COUNTRIES).status_code == 401
        assert api_client.get(ACTIVE).status_code == 401


@pytest.mark.django_db
class TestInactiveCountriesCannotBeChosen:
    def test_only_active_countries_are_offered(self, api_client):
        make_country()
        make_country(name="India", code="IN", is_active=False)
        login_as(api_client, User.Role.CUSTOMER)

        response = api_client.get(ACTIVE)

        assert response.status_code == 200
        assert [c["code"] for c in response.data] == ["GB"]
        assert set(response.data[0]) == {"id", "name", "code", "currency", "currency_symbol"}
        assert list(Country.objects.active().values_list("code", flat=True)) == ["GB"]
