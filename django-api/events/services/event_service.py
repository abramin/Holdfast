"""Event service - all business logic lives here.

Services:
- Depend only on interfaces (stores)
- Validate domain invariants
- Perform orchestration and error mapping
- Return domain models or domain errors

TODO: Implement service methods. Raise domain errors for invalid IDs and not found.
"""

from events.domain.models import Event, Session
from events.stores.interfaces import EventStore


class EventService:
    """Service for event catalog operations."""

    def __init__(self, store: EventStore) -> None:
        self._store = store

    def list_events(self) -> list[Event]:
        """Return all events."""
        raise NotImplementedError

    def get_event(self, event_id: str) -> Event:
        """Return an event by ID.

        Raises:
            InvalidEventIdError: If the event_id is not a valid UUID.
            EventNotFoundError: If the event does not exist.
        """
        raise NotImplementedError

    def get_sessions_for_event(self, event_id: str) -> list[Session]:
        """Return sessions for an event.

        Raises:
            InvalidEventIdError: If the event_id is not a valid UUID.
            EventNotFoundError: If the event does not exist.
        """
        raise NotImplementedError
