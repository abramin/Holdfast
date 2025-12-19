"""Unit tests for domain primitives.

These test invariants that must hold at construction time.
Run with: pytest tests/test_domain.py -v
"""

import pytest
from decimal import Decimal


class TestMoney:
    """Tests for Money value object."""

    def test_money_accepts_positive_amount(self):
        """Money can be created with positive amount."""
        pytest.fail("Not implemented")

    def test_money_accepts_zero(self):
        """Money can be created with zero."""
        pytest.fail("Not implemented")

    def test_money_rejects_negative_amount(self):
        """Money raises ValueError for negative amount."""
        pytest.fail("Not implemented")

    def test_money_str_format(self):
        """Money string representation is formatted to 2 decimal places."""
        pytest.fail("Not implemented")


class TestCapacity:
    """Tests for Capacity value object."""

    def test_capacity_accepts_positive_value(self):
        """Capacity can be created with positive value."""
        pytest.fail("Not implemented")

    def test_capacity_accepts_zero(self):
        """Capacity can be created with zero."""
        pytest.fail("Not implemented")

    def test_capacity_rejects_negative_value(self):
        """Capacity raises ValueError for negative value."""
        pytest.fail("Not implemented")


class TestEventId:
    """Tests for EventId value object."""

    def test_from_string_valid_uuid(self):
        """EventId.from_string parses valid UUID."""
        pytest.fail("Not implemented")

    def test_from_string_invalid_uuid(self):
        """EventId.from_string raises ValueError for invalid UUID."""
        pytest.fail("Not implemented")
