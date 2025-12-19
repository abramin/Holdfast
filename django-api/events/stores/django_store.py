"""Django ORM implementation of the EventStore.

TODO: Implement each method to query Django ORM and convert to domain models.
"""

from events.domain import Event, EventId, Session
from events.stores.interfaces import EventStore


class DjangoEventStore(EventStore):
    """PostgreSQL-backed event store using Django ORM."""

    def list_events(self) -> list[Event]:
        raise NotImplementedError

    def get_event(self, event_id: EventId) -> Event | None:
        raise NotImplementedError

    def get_sessions_for_event(self, event_id: EventId) -> list[Session]:
        raise NotImplementedError

    def event_exists(self, event_id: EventId) -> bool:
        raise NotImplementedError
