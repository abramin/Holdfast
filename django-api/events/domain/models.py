"""Domain models representing persisted state.

These are pure domain objects with no API input rules.
Django ORM models are in events/models.py (persistence layer).
"""

from dataclasses import dataclass
from datetime import datetime

from events.domain.value_objects import Capacity, EventId, Money, SessionId, TicketTypeId


@dataclass(frozen=True)
class Event:
    """Domain representation of an Event."""

    id: EventId
    name: str
    description: str
    location: str
    image_url: str | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class TicketType:
    """Domain representation of a TicketType."""

    id: TicketTypeId
    session_id: SessionId
    name: str
    price: Money
    quantity: Capacity
    created_at: datetime


@dataclass(frozen=True)
class Session:
    """Domain representation of a Session."""

    id: SessionId
    event_id: EventId
    starts_at: datetime
    ends_at: datetime
    total_capacity: Capacity
    created_at: datetime
    ticket_types: tuple[TicketType, ...] = ()
