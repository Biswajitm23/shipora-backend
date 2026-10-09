import re
from decimal import Decimal

from rest_framework import serializers

from .models import Country

LETTERS = re.compile(r"^[A-Za-z]+$")


def required(what):
    message = f"Please enter the {what}."
    return {"required": message, "blank": message, "null": message}


class CountrySerializer(serializers.ModelSerializer):
    """The Admin's view of a country: add, edit, activate / deactivate."""

    name = serializers.CharField(max_length=100, error_messages=required("country name"))
    code = serializers.CharField(max_length=3, error_messages=required("country code"))
    currency = serializers.CharField(max_length=3, error_messages=required("currency"))
    currency_symbol = serializers.CharField(
        max_length=8, error_messages=required("currency symbol")
    )
    shipping_zone = serializers.CharField(max_length=100, error_messages=required("shipping zone"))
    tax_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        error_messages={
            **required("tax percentage"),
            "invalid": "Please enter the tax percentage as a number.",
            "min_value": "The tax percentage cannot be below 0.",
            "max_value": "The tax percentage cannot be above 100.",
            "max_decimal_places": "Use at most 2 decimal places.",
            "max_digits": "The tax percentage cannot be above 100.",
            "max_whole_digits": "The tax percentage cannot be above 100.",
        },
    )

    class Meta:
        model = Country
        fields = [
            "id",
            "name",
            "code",
            "currency",
            "currency_symbol",
            "shipping_zone",
            "tax_percentage",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def _unique(self, field, value, message):
        others = Country.objects.filter(**{f"{field}__iexact": value})
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise serializers.ValidationError(message)
        return value

    def validate_name(self, value):
        value = " ".join(value.split())
        return self._unique("name", value, "A country with this name already exists.")

    def validate_code(self, value):
        value = value.strip().upper()
        if not LETTERS.match(value) or len(value) not in (2, 3):
            raise serializers.ValidationError("Use the 2 or 3 letter country code (e.g. IN).")
        return self._unique("code", value, "A country with this code already exists.")

    def validate_currency(self, value):
        value = value.strip().upper()
        if not LETTERS.match(value) or len(value) != 3:
            raise serializers.ValidationError("Use the 3 letter currency code (e.g. INR).")
        return value

    def validate_currency_symbol(self, value):
        return value.strip()

    def validate_shipping_zone(self, value):
        return " ".join(value.split())


class CountryOptionSerializer(serializers.ModelSerializer):
    """An active country as offered when creating a shipment."""

    class Meta:
        model = Country
        fields = ["id", "name", "code", "currency", "currency_symbol"]
        read_only_fields = fields
