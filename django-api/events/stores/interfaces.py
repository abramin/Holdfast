"""Store interfaces (repository pattern).

Stores must be swappable and return domain models.
"""

from abc import ABC, abstractmethod

from events.domain import Event, EventId, Session


class EventStore(ABC):
    """Interface for event persistence operations."""

    @abstractmethod
    def list_events(self) -> list[Event]:
        """Return all events ordered by created_at descending."""
        ...

    @abstractmethod
    def get_event(self, event_id: EventId) -> Event | None:
        """Return an event by ID, or None if not found."""
        ...

    @abstractmethod
    def get_sessions_for_event(self, event_id: EventId) -> list[Session]:
        """Return all sessions for an event, ordered by starts_at ascending."""
        ...

    @abstractmethod
    def event_exists(self, event_id: EventId) -> bool:
        """Check if an event exists."""
        ...
