"""ROLE-002: what each account type is allowed to see and do.

`ACCESS_RULES` is the one place the rules live. Views check them with
`HasAccess(<rule>)`; records that belong to one customer or are assigned to one
delivery agent are limited with `OwnRecordsOnly` and `visible_to()`. The website
gets the logged-in user's rules from `/api/auth/me/` (`permissions`).
"""

from rest_framework.permissions import BasePermission

from .models import User

Role = User.Role

# Admin
MANAGE_USERS = "manage_users"
MANAGE_COUNTRIES = "manage_countries"
MANAGE_SERVICES = "manage_services"
MANAGE_PRICING = "manage_pricing"
VIEW_ALL_SHIPMENTS = "view_all_shipments"
VIEW_INVOICES = "view_invoices"
VIEW_REPORTS = "view_reports"
MANAGE_SYSTEM = "manage_system"
# Customer
MANAGE_OWN_PROFILE = "manage_own_profile"
CREATE_SHIPMENTS = "create_shipments"
VIEW_OWN_SHIPMENTS = "view_own_shipments"
TRACK_OWN_SHIPMENTS = "track_own_shipments"
VIEW_OWN_INVOICES = "view_own_invoices"
VIEW_PERMITTED_DOCUMENTS = "view_permitted_documents"
# Logistics Staff
VIEW_OPERATIONAL_SHIPMENTS = "view_operational_shipments"
CONFIRM_SHIPMENTS = "confirm_shipments"
ASSIGN_DELIVERY_AGENTS = "assign_delivery_agents"
MANAGE_SHIPMENT_OPERATIONS = "manage_shipment_operations"
VIEW_OPERATIONAL_INFO = "view_operational_info"
# Delivery Agent
VIEW_ASSIGNED_SHIPMENTS = "view_assigned_shipments"
MANAGE_ASSIGNED_PICKUPS = "manage_assigned_pickups"
MANAGE_ASSIGNED_DELIVERIES = "manage_assigned_deliveries"
UPLOAD_PROOF_OF_DELIVERY = "upload_proof_of_delivery"

ACCESS_RULES = {
    Role.ADMIN: frozenset(
        {
            MANAGE_USERS,
            MANAGE_COUNTRIES,
            MANAGE_SERVICES,
            MANAGE_PRICING,
            VIEW_ALL_SHIPMENTS,
            VIEW_INVOICES,
            VIEW_REPORTS,
            MANAGE_SYSTEM,
        }
    ),
    Role.CUSTOMER: frozenset(
        {
            MANAGE_OWN_PROFILE,
            CREATE_SHIPMENTS,
            VIEW_OWN_SHIPMENTS,
            TRACK_OWN_SHIPMENTS,
            VIEW_OWN_INVOICES,
            VIEW_PERMITTED_DOCUMENTS,
        }
    ),
    Role.STAFF: frozenset(
        {
            VIEW_OPERATIONAL_SHIPMENTS,
            CONFIRM_SHIPMENTS,
            ASSIGN_DELIVERY_AGENTS,
            MANAGE_SHIPMENT_OPERATIONS,
            VIEW_OPERATIONAL_INFO,
        }
    ),
    Role.AGENT: frozenset(
        {
            VIEW_ASSIGNED_SHIPMENTS,
            MANAGE_ASSIGNED_PICKUPS,
            MANAGE_ASSIGNED_DELIVERIES,
            UPLOAD_PROOF_OF_DELIVERY,
        }
    ),
}


def permissions_for(user):
    """The rules an active, logged-in user has; nothing for anyone else."""
    if not (user and user.is_authenticated and user.is_active):
        return frozenset()
    return ACCESS_RULES.get(user.role, frozenset())


def can(user, rule):
    return rule in permissions_for(user)


def HasAccess(*rules):
    """Permission class: the user must have every one of `rules`.

    Usage: `permission_classes = [HasAccess(MANAGE_COUNTRIES)]`.
    """

    class _HasAccess(BasePermission):
        message = "You do not have access to this."

        def has_permission(self, request, view):
            return all(can(request.user, rule) for rule in rules)

    _HasAccess.__name__ = f"HasAccess({', '.join(rules)})"
    return _HasAccess


def _owner_matches(obj, field, user):
    """Follow `field` ("customer" or "shipment__customer") from obj; True if it is user."""
    value = obj
    for part in field.split("__"):
        value = getattr(value, part, None)
        if value is None:
            return False
    return getattr(value, "pk", value) == user.pk


class OwnRecordsOnly(BasePermission):
    """Object rule for records that belong to a customer or are assigned to an agent.

    The view names the fields: `owner_field` (the customer the record belongs to) and
    `assigned_field` (the delivery agent it is assigned to). Admin and Logistics
    Staff may open any record; a customer only their own; an agent only the ones
    assigned to them. Use `visible_to()` for the matching list.
    """

    message = "You do not have access to this record."

    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.role in (Role.ADMIN, Role.STAFF):
            return True
        field = {
            Role.CUSTOMER: getattr(view, "owner_field", None),
            Role.AGENT: getattr(view, "assigned_field", None),
        }.get(user.role)
        return bool(field) and _owner_matches(obj, field, user)


def visible_to(user, queryset, *, owner_field=None, assigned_field=None):
    """Limit a list to the records `user` may see (same rules as `OwnRecordsOnly`)."""
    if not (user and user.is_authenticated and user.is_active):
        return queryset.none()
    if user.role in (Role.ADMIN, Role.STAFF):
        return queryset
    field = {Role.CUSTOMER: owner_field, Role.AGENT: assigned_field}.get(user.role)
    return queryset.filter(**{field: user.pk}) if field else queryset.none()
