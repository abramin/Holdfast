"""Integration tests for Event Catalog (PRD-001).

These tests validate the contract defined in features/event_catalog.feature.
Run with: pytest tests/test_event_catalog.py -v
"""

import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestEventList:
    """Tests for GET /api/events"""

    def test_list_events_returns_paginated_results(self, api_client: APIClient):
        """Given events exist, returns paginated list."""
        # TODO: Create events in DB
        # TODO: Make request
        # TODO: Assert response structure
        pytest.fail("Not implemented")

    def test_list_events_empty_catalog(self, api_client: APIClient):
        """Given no events, returns empty list."""
        pytest.fail("Not implemented")

    def test_list_events_cached_response(self, api_client: APIClient):
        """Given cached data, returns from cache."""
        pytest.fail("Not implemented")


@pytest.mark.django_db
class TestEventDetail:
    """Tests for GET /api/events/{id}"""

    def test_get_event_returns_details(self, api_client: APIClient):
        """Given event exists, returns event details."""
        pytest.fail("Not implemented")

    def test_get_event_not_found(self, api_client: APIClient):
        """Given event does not exist, returns 404."""
        pytest.fail("Not implemented")

    def test_get_event_invalid_id_format(self, api_client: APIClient):
        """Given invalid UUID, returns 400."""
        pytest.fail("Not implemented")


@pytest.mark.django_db
class TestSessionList:
    """Tests for GET /api/events/{id}/sessions"""

    def test_list_sessions_with_ticket_types(self, api_client: APIClient):
        """Given event with sessions, returns sessions with ticket types."""
        pytest.fail("Not implemented")

    def test_list_sessions_event_not_found(self, api_client: APIClient):
        """Given event does not exist, returns 404."""
        pytest.fail("Not implemented")

    def test_list_sessions_ordered_by_start_time(self, api_client: APIClient):
        """Sessions are ordered by starts_at ascending."""
        pytest.fail("Not implemented")
