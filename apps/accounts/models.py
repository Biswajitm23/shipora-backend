"""Accounts: the custom user model.

Email is the login field; there is no username. Every user has one account type
(role). Self-registration always creates a customer whose email address still
has to be verified.
"""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("role", User.Role.ADMIN)
        extra_fields.setdefault("email_verified", True)
        extra_fields["is_staff"] = True
        extra_fields["is_superuser"] = True
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        STAFF = "STAFF", "Logistics Staff"
        AGENT = "AGENT", "Delivery Agent"
        ADMIN = "ADMIN", "Admin"

    username = None
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=32, blank=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CUSTOMER)
    email_verified = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email
