"""SERV-001: the delivery services Shipora offers, managed by the Admin.

Customers only see available (active) services: `Service.objects.available()`.
"""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class ServiceQuerySet(models.QuerySet):
    def available(self):
        return self.filter(is_active=True)


class Service(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    # Shown as written, e.g. "3-5 business days".
    estimated_delivery = models.CharField(max_length=100)
    weight_limit_kg = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )
    is_international = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ServiceQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("name"), name="service_name_unique_ci")]

    def __str__(self):
        return self.name
