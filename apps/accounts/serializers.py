import re

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError
from rest_framework import serializers

from .models import User
from .permissions import permissions_for

DUPLICATE_EMAIL = "An account with this email address already exists."
PHONE_CHARS = re.compile(r"^\+?[\d\s\-()]+$")


def required(what):
    """Same friendly message whether the field is missing or left blank."""
    message = f"Please enter your {what}."
    return {"required": message, "blank": message}


class UserSerializer(serializers.ModelSerializer):
    """The logged-in user, with the access rules of their account type (ROLE-002)."""

    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "phone",
            "role",
            "email_verified",
            "permissions",
        ]
        read_only_fields = fields

    def get_permissions(self, user):
        return sorted(permissions_for(user))


class RegisterSerializer(serializers.Serializer):
    """Self-registration. Always creates an unverified CUSTOMER; any role sent is ignored.

    Registering again with the email of an account that was never verified starts
    that registration again (`restarted`): the account takes the new details instead
    of blocking its own email address. Nobody could log in to it yet.
    """

    restart_unverified = True
    restarted = False
    unverified_account = None  # set by validate_email when a registration starts again

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
        existing = User.objects.filter(email__iexact=value).first()
        if existing is None:
            return value
        if not (self.restart_unverified and self.can_restart(existing)):
            raise serializers.ValidationError(DUPLICATE_EMAIL)
        self.unverified_account = existing
        return existing.email

    @staticmethod
    def can_restart(user):
        """A self-registered account that was never verified, so never used."""
        return (
            not user.email_verified
            and user.is_active
            and user.role == User.Role.CUSTOMER
            and user.last_login is None
            and not (user.is_staff or user.is_superuser)
        )

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
        user = self.unverified_account
        if user is None:
            return self.create_account(validated_data, role=User.Role.CUSTOMER)
        for field in ("first_name", "last_name", "phone"):
            setattr(user, field, validated_data[field])
        # A new password also ends the verification links sent before.
        user.set_password(validated_data["password"])
        user.save(update_fields=["first_name", "last_name", "phone", "password"])
        self.restarted = True
        return user

    def create_account(self, validated_data, **fields):
        validated_data.pop("password_confirm")
        try:
            return User.objects.create_user(**validated_data, **fields)
        except IntegrityError as exc:  # registered at the same moment by another request
            raise serializers.ValidationError({"email": [DUPLICATE_EMAIL]}) from exc

    def to_representation(self, instance):
        return UserSerializer(instance).data


class AdminCreateUserSerializer(RegisterSerializer):
    """ROLE-001: the Admin adds an account of any type. It is active and already
    verified (the Admin created it), so it can log in straight away."""

    restart_unverified = False

    role = serializers.ChoiceField(
        choices=User.Role.choices,
        error_messages={
            "required": "Please choose an account type.",
            "invalid_choice": "Please choose a valid account type.",
        },
    )

    def create(self, validated_data):
        return self.create_account(validated_data, email_verified=True)

    def to_representation(self, instance):
        return AdminUserSerializer(instance).data


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


class ResendVerificationSerializer(serializers.Serializer):
    email = serializers.EmailField(error_messages=required("email address"))


class LoginSerializer(serializers.Serializer):
    """The login form: both fields required. The credential checks are in LoginView."""

    email = serializers.EmailField(error_messages=required("email address"))
    password = serializers.CharField(trim_whitespace=False, error_messages=required("password"))
