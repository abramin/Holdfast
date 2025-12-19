"""Domain error codes for the events module."""

from dataclasses import dataclass
from enum import Enum


class ErrorCode(Enum):
    """Domain error codes."""

    EVENT_NOT_FOUND = "EVENT_NOT_FOUND"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    INVALID_EVENT_ID = "INVALID_EVENT_ID"


@dataclass(frozen=True)
class DomainError(Exception):
    """Base domain error with code and user-safe message."""

    code: ErrorCode
    message: str

    def __str__(self) -> str:
        return f"{self.code.value}: {self.message}"


class EventNotFoundError(DomainError):
    """Raised when an event is not found."""

    def __init__(self, event_id: str) -> None:
        super().__init__(
            code=ErrorCode.EVENT_NOT_FOUND,
            message=f"Event not found",
        )
        self.event_id = event_id


class SessionNotFoundError(DomainError):
    """Raised when sessions for an event are not found."""

    def __init__(self, event_id: str) -> None:
        super().__init__(
            code=ErrorCode.SESSION_NOT_FOUND,
            message=f"Sessions not found for event",
        )
        self.event_id = event_id


class InvalidEventIdError(DomainError):
    """Raised when an event ID is invalid."""

    def __init__(self) -> None:
        super().__init__(
            code=ErrorCode.INVALID_EVENT_ID,
            message="Invalid event ID format",
        )
