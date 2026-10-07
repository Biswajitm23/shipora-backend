import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import serializers

from .models import User

DUPLICATE_EMAIL = "An account with this email address already exists."
PHONE_CHARS = re.compile(r"^\+?[\d\s\-()]+$")


def required(what):
    """Same friendly message whether the field is missing or left blank."""
    message = f"Please enter your {what}."
    return {"required": message, "blank": message}


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "role", "email_verified"]
        read_only_fields = fields


class RegisterSerializer(serializers.Serializer):
    """Self-registration. Always creates an unverified CUSTOMER; any role sent is ignored."""

    first_name = serializers.CharField(max_length=150, error_messages=required("first name"))
    last_name = serializers.CharField(max_length=150, error_messages=required("last name"))
    email = serializers.EmailField(error_messages=required("email address"))
    phone = serializers.CharField(max_length=32, error_messages=required("phone number"))
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, error_messages=required("password")
    )
    password_confirm = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        error_messages={
            "required": "Please confirm your password.",
            "blank": "Please confirm your password.",
        },
    )

    def validate_email(self, value):
        value = value.lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(DUPLICATE_EMAIL)
        return value

    def validate_phone(self, value):
        digits = re.sub(r"\D", "", value)
        if not PHONE_CHARS.match(value) or not 7 <= len(digits) <= 15:
            raise serializers.ValidationError("Please enter a valid phone number.")
        return value

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        candidate = User(
            email=attrs["email"], first_name=attrs["first_name"], last_name=attrs["last_name"]
        )
        try:
            validate_password(attrs["password"], user=candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        try:
            return User.objects.create_user(role=User.Role.CUSTOMER, **validated_data)
        except IntegrityError as exc:  # registered at the same moment by another request
            raise serializers.ValidationError({"email": [DUPLICATE_EMAIL]}) from exc

    def to_representation(self, instance):
        return UserSerializer(instance).data


class AdminUserSerializer(serializers.ModelSerializer):
    """An account as the Admin sees it (USER-002). Only `is_active` can be changed."""

    class Meta:
        model = User
        fields = [
            "id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "is_active",
            "email_verified",
            "date_joined",
            "last_login",
        ]
        read_only_fields = [f for f in fields if f != "is_active"]


class LoginSerializer(serializers.Serializer):
    """The login form: both fields required. The credential checks are in LoginView."""

    email = serializers.EmailField(error_messages=required("email address"))
    password = serializers.CharField(trim_whitespace=False, error_messages=required("password"))
