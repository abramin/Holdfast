"""Django signals for cache invalidation.

TODO: Implement signal handlers for Event, Session, TicketType
to invalidate cache on save/delete.
"""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from events.models import Event, Session, TicketType


@receiver([post_save, post_delete], sender=Event)
def invalidate_event_cache(sender, instance, **kwargs):
    """Invalidate caches when an event is saved or deleted."""
    pass


@receiver([post_save, post_delete], sender=Session)
def invalidate_session_cache(sender, instance, **kwargs):
    """Invalidate caches when a session is saved or deleted."""
    pass


@receiver([post_save, post_delete], sender=TicketType)
def invalidate_ticket_type_cache(sender, instance, **kwargs):
    """Invalidate caches when a ticket type is saved or deleted."""
    pass
