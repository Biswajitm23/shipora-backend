"""Shared pytest fixtures for every app's tests.

Fixtures:
    api_client   unauthenticated DRF APIClient
    customer     an unverified CUSTOMER user
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User

TEST_PASSWORD = "Tr1cky-Harbour-42"


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def customer(db):
    return User.objects.create_user(
        "customer@example.com",
        TEST_PASSWORD,
        first_name="Casey",
        last_name="Customer",
        phone="+44 113 496 0000",
    )
