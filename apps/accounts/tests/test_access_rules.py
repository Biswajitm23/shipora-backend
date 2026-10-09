"""ROLE-002: what each account type may see and do."""

from types import SimpleNamespace

import pytest

from apps.accounts import permissions as access
from apps.accounts.models import User
from conftest import TEST_PASSWORD

ME = "/api/auth/me/"
LOGIN = "/api/auth/login/"
USERS = "/api/users/"


def make_user(role, email=None, **extra):
    return User.objects.create_user(
        email or f"{role.lower()}@example.com",
        TEST_PASSWORD,
        role=role,
        email_verified=True,
        **extra,
    )


class TestRulesPerAccountType:
    def test_every_account_type_has_rules(self):
        assert set(access.ACCESS_RULES) == set(User.Role)

    def test_no_rule_is_shared_between_account_types(self):
        rules = [rule for role_rules in access.ACCESS_RULES.values() for rule in role_rules]
        assert len(rules) == len(set(rules))

    def test_admin_rules(self):
        assert access.ACCESS_RULES[User.Role.ADMIN] == {
            "manage_users",
            "manage_countries",
            "manage_services",
            "manage_pricing",
            "view_all_shipments",
            "view_invoices",
            "view_reports",
            "manage_system",
        }

    def test_customer_rules(self):
        assert access.ACCESS_RULES[User.Role.CUSTOMER] == {
            "manage_own_profile",
            "create_shipments",
            "view_own_shipments",
            "track_own_shipments",
            "view_own_invoices",
            "view_permitted_documents",
        }

    def test_staff_rules(self):
        assert access.ACCESS_RULES[User.Role.STAFF] == {
            "view_operational_shipments",
            "confirm_shipments",
            "assign_delivery_agents",
            "manage_shipment_operations",
            "view_operational_info",
        }

    def test_agent_rules(self):
        assert access.ACCESS_RULES[User.Role.AGENT] == {
            "view_assigned_shipments",
            "manage_assigned_pickups",
            "manage_assigned_deliveries",
            "upload_proof_of_delivery",
        }


@pytest.mark.django_db
class TestRulesReachTheWebsite:
    @pytest.mark.parametrize("role", list(User.Role))
    def test_me_and_login_return_the_account_types_rules(self, api_client, role):
        user = make_user(role)
        expected = sorted(access.ACCESS_RULES[role])

        login = api_client.post(LOGIN, {"email": user.email, "password": TEST_PASSWORD})
        api_client.force_authenticate(user)
        me = api_client.get(ME)

        assert login.data["user"]["permissions"] == expected
        assert me.data["permissions"] == expected

    def test_deactivated_or_anonymous_users_have_no_rules(self, db):
        user = make_user(User.Role.ADMIN, is_active=False)
        assert access.permissions_for(user) == frozenset()
        assert access.permissions_for(None) == frozenset()


@pytest.mark.django_db
class TestActionsCheckTheRules:
    @pytest.mark.parametrize("role", [User.Role.CUSTOMER, User.Role.STAFF, User.Role.AGENT])
    def test_only_admin_manages_users(self, api_client, role):
        api_client.force_authenticate(make_user(role))

        assert api_client.get(USERS).status_code == 403
        assert api_client.post(USERS, {}, format="json").status_code == 403

    def test_admin_manages_users(self, api_client):
        api_client.force_authenticate(make_user(User.Role.ADMIN))
        assert api_client.get(USERS).status_code == 200

    def test_customers_cannot_see_other_customers(self, api_client):
        make_user(User.Role.CUSTOMER, "other@example.com")
        me = make_user(User.Role.CUSTOMER)
        api_client.force_authenticate(me)

        assert api_client.get(USERS).status_code == 403
        assert api_client.get(ME).data["email"] == me.email

    def test_has_access_requires_every_rule(self, db):
        perm = access.HasAccess(access.MANAGE_USERS, access.VIEW_REPORTS)()
        admin = SimpleNamespace(user=make_user(User.Role.ADMIN))
        staff = SimpleNamespace(user=make_user(User.Role.STAFF))

        assert perm.has_permission(admin, None)
        assert not perm.has_permission(staff, None)


@pytest.mark.django_db
class TestOwnRecordsOnly:
    """Customers only reach their own records; agents only the ones assigned to them."""

    view = SimpleNamespace(owner_field="customer", assigned_field="delivery_agent")

    @pytest.fixture
    def people(self):
        return {
            "admin": make_user(User.Role.ADMIN),
            "staff": make_user(User.Role.STAFF),
            "owner": make_user(User.Role.CUSTOMER, "owner@example.com"),
            "other": make_user(User.Role.CUSTOMER, "other@example.com"),
            "agent": make_user(User.Role.AGENT, "agent@example.com"),
            "other_agent": make_user(User.Role.AGENT, "agent2@example.com"),
        }

    def allowed(self, user, record):
        request = SimpleNamespace(user=user)
        return access.OwnRecordsOnly().has_object_permission(request, self.view, record)

    def test_object_access(self, people):
        record = SimpleNamespace(customer=people["owner"], delivery_agent=people["agent"])

        assert self.allowed(people["admin"], record)
        assert self.allowed(people["staff"], record)
        assert self.allowed(people["owner"], record)
        assert self.allowed(people["agent"], record)
        assert not self.allowed(people["other"], record)
        assert not self.allowed(people["other_agent"], record)

    def test_unassigned_record_is_not_open_to_agents(self, people):
        record = SimpleNamespace(customer=people["owner"], delivery_agent=None)
        assert not self.allowed(people["agent"], record)

    def test_nested_owner_field(self, people):
        view = SimpleNamespace(owner_field="shipment__customer")
        record = SimpleNamespace(shipment=SimpleNamespace(customer=people["owner"]))
        perm = access.OwnRecordsOnly()

        assert perm.has_object_permission(SimpleNamespace(user=people["owner"]), view, record)
        assert not perm.has_object_permission(SimpleNamespace(user=people["other"]), view, record)
        # No assigned_field on this view: agents get nothing.
        assert not perm.has_object_permission(SimpleNamespace(user=people["agent"]), view, record)

    def test_visible_to_limits_lists(self, people):
        # Users stand in for records here: a "record" belongs to the user it is.
        users = User.objects.all()

        def visible(user):
            return set(access.visible_to(user, users, owner_field="pk", assigned_field="pk"))

        assert visible(people["admin"]) == set(users)
        assert visible(people["staff"]) == set(users)
        assert visible(people["owner"]) == {people["owner"]}
        assert visible(people["agent"]) == {people["agent"]}
        assert set(access.visible_to(people["owner"], users)) == set()
