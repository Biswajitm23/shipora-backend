"""CNTRY-001: the countries Shipora ships to, managed by the Admin.

Only active countries can be chosen for new shipments (`Country.objects.active()`).
"""

from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.functions import Lower


class CountryQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class Country(models.Model):
    name = models.CharField(max_length=100)
    # ISO 3166 code, stored upper case (e.g. "IN", "GBR").
    code = models.CharField(max_length=3)
    # ISO 4217 currency code, stored upper case (e.g. "INR").
    currency = models.CharField(max_length=3)
    currency_symbol = models.CharField(max_length=8)
    shipping_zone = models.CharField(max_length=100)
    tax_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = CountryQuerySet.as_manager()

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="country_name_unique_ci"),
            models.UniqueConstraint(Lower("code"), name="country_code_unique_ci"),
        ]

    def __str__(self):
        return self.name
