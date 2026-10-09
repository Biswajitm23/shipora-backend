from decimal import Decimal

from rest_framework import serializers

from .models import Service


def required(what):
    message = f"Please enter the {what}."
    return {"required": message, "blank": message, "null": message}


class ServiceSerializer(serializers.ModelSerializer):
    """The Admin's view of a service: create, update, activate / deactivate."""

    name = serializers.CharField(max_length=100, error_messages=required("service name"))
    description = serializers.CharField(error_messages=required("description"))
    estimated_delivery = serializers.CharField(
        max_length=100, error_messages=required("estimated delivery time")
    )
    weight_limit_kg = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=Decimal("0.01"),
        error_messages={
            **required("weight limit"),
            "invalid": "Please enter the weight limit as a number.",
            "min_value": "The weight limit must be more than 0.",
            "max_decimal_places": "Use at most 2 decimal places.",
            "max_digits": "The weight limit is too large.",
            "max_whole_digits": "The weight limit is too large.",
        },
    )

    class Meta:
        model = Service
        fields = [
            "id",
            "name",
            "description",
            "estimated_delivery",
            "weight_limit_kg",
            "is_international",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_name(self, value):
        value = " ".join(value.split())
        others = Service.objects.filter(name__iexact=value)
        if self.instance is not None:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise serializers.ValidationError("A service with this name already exists.")
        return value

    def validate_description(self, value):
        return value.strip()

    def validate_estimated_delivery(self, value):
        return " ".join(value.split())


class AvailableServiceSerializer(serializers.ModelSerializer):
    """An available service as customers see it, with its limitations."""

    class Meta:
        model = Service
        fields = [
            "id",
            "name",
            "description",
            "estimated_delivery",
            "weight_limit_kg",
            "is_international",
        ]
        read_only_fields = fields
