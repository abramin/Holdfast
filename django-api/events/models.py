"""Django ORM models (persistence layer).

These models handle database concerns. Domain logic lives in domain/models.py.
"""

import uuid

from django.db import models


class Event(models.Model):
    """Persistence model for events."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField()
    location = models.CharField(max_length=255)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self) -> str:
        return self.name


class Session(models.Model):
    """Persistence model for event sessions."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sessions")
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    total_capacity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["starts_at"]
        indexes = [
            models.Index(fields=["event", "starts_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.event.name} - {self.starts_at}"


class TicketType(models.Model):
    """Persistence model for ticket types."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        Session, on_delete=models.CASCADE, related_name="ticket_types"
    )
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["session"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} - {self.price}"
