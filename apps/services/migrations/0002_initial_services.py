"""SERV-001: the six services Shipora starts with. The Admin can change them later."""

from decimal import Decimal

from django.db import migrations

INITIAL_SERVICES = [
    (
        "Standard Delivery",
        "Reliable, low-cost delivery for everyday parcels within the country.",
        "3-5 business days",
        Decimal("30"),
        False,
    ),
    (
        "Express Delivery",
        "Faster delivery for parcels that need to arrive sooner.",
        "1-2 business days",
        Decimal("20"),
        False,
    ),
    (
        "International Shipping",
        "Delivery of parcels and documents to other countries.",
        "7-14 business days",
        Decimal("30"),
        True,
    ),
    (
        "Same Day Delivery",
        "Collected and delivered on the same day within the city.",
        "Same day",
        Decimal("10"),
        False,
    ),
    (
        "Document Delivery",
        "Safe delivery of letters and important documents.",
        "1-3 business days",
        Decimal("2"),
        False,
    ),
    (
        "Package Delivery",
        "Delivery of larger boxes and packages.",
        "2-5 business days",
        Decimal("50"),
        False,
    ),
]


def add_services(apps, schema_editor):
    Service = apps.get_model("services", "Service")
    for name, description, delivery, weight, international in INITIAL_SERVICES:
        Service.objects.get_or_create(
            name=name,
            defaults={
                "description": description,
                "estimated_delivery": delivery,
                "weight_limit_kg": weight,
                "is_international": international,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("services", "0001_initial")]

    operations = [migrations.RunPython(add_services, migrations.RunPython.noop)]
