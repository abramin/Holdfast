from django.urls import path

from events.handlers import EventDetailView, EventListView, SessionListView

urlpatterns = [
    path("events", EventListView.as_view(), name="event-list"),
    path("events/<str:event_id>", EventDetailView.as_view(), name="event-detail"),
    path(
        "events/<str:event_id>/sessions",
        SessionListView.as_view(),
        name="session-list",
    ),
]
