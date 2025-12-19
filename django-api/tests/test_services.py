"""Unit tests for EventService.

These test error handling and domain error mapping.
Run with: pytest tests/test_services.py -v
"""

import pytest


class TestEventService:
    """Tests for EventService."""

    def test_get_event_invalid_id_raises_error(self):
        """get_event raises InvalidEventIdError for malformed UUID."""
        pytest.fail("Not implemented")

    def test_get_event_not_found_raises_error(self):
        """get_event raises EventNotFoundError when store returns None."""
        pytest.fail("Not implemented")

    def test_get_sessions_invalid_id_raises_error(self):
        """get_sessions_for_event raises InvalidEventIdError for malformed UUID."""
        pytest.fail("Not implemented")

    def test_get_sessions_event_not_found_raises_error(self):
        """get_sessions_for_event raises EventNotFoundError when event doesn't exist."""
        pytest.fail("Not implemented")
