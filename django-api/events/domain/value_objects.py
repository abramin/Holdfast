"""Domain primitives that enforce validity at creation time."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Self
from uuid import UUID


@dataclass(frozen=True)
class EventId:
    """Unique identifier for an Event."""

    value: UUID

    @classmethod
    def from_string(cls, value: str) -> Self:
        return cls(value=UUID(value))


@dataclass(frozen=True)
class SessionId:
    """Unique identifier for a Session."""

    value: UUID

    @classmethod
    def from_string(cls, value: str) -> Self:
        return cls(value=UUID(value))


@dataclass(frozen=True)
class TicketTypeId:
    """Unique identifier for a TicketType."""

    value: UUID

    @classmethod
    def from_string(cls, value: str) -> Self:
        return cls(value=UUID(value))


@dataclass(frozen=True)
class Money:
    """Price representation with validation."""

    amount: Decimal

    def __post_init__(self) -> None:
        if self.amount < 0:
            raise ValueError("Money amount cannot be negative")

    def __str__(self) -> str:
        return f"{self.amount:.2f}"


@dataclass(frozen=True)
class Capacity:
    """Non-negative integer representing capacity."""

    value: int

    def __post_init__(self) -> None:
        if self.value < 0:
            raise ValueError("Capacity cannot be negative")
