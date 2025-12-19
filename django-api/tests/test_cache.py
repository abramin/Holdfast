"""Tests for cache behavior.

Run with: pytest tests/test_cache.py -v
"""

import pytest


@pytest.mark.django_db
class TestCacheInvalidation:
    """Tests for cache invalidation on model changes."""

    def test_event_save_invalidates_list_cache(self):
        """Saving an event invalidates the events:list cache key."""
        pytest.fail("Not implemented")

    def test_event_save_invalidates_detail_cache(self):
        """Saving an event invalidates the events:{id} cache key."""
        pytest.fail("Not implemented")

    def test_session_save_invalidates_sessions_cache(self):
        """Saving a session invalidates the events:{id}:sessions cache key."""
        pytest.fail("Not implemented")

    def test_ticket_type_save_invalidates_sessions_cache(self):
        """Saving a ticket type invalidates the sessions cache."""
        pytest.fail("Not implemented")
