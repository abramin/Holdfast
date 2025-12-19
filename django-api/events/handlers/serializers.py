"""Serializers for transforming domain models to API responses.

TODO: Implement serializers for Event, Session, TicketType domain models.
"""

from rest_framework import serializers


class EventSerializer(serializers.Serializer):
    """Serializer for Event domain model."""

    pass


class TicketTypeSerializer(serializers.Serializer):
    """Serializer for TicketType domain model."""

    pass


class SessionSerializer(serializers.Serializer):
    """Serializer for Session domain model."""

    pass
