"""HTTP handlers (views) - handle HTTP concerns only.

Handlers:
- Parse requests and validate input format
- Call services for business logic
- Map domain errors to HTTP responses
- Never contain business logic
- Never expose internal error details

TODO: Implement views with caching and error mapping.
"""

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class EventListView(APIView):
    """Handler for GET /api/events"""

    def get(self, request: Request) -> Response:
        raise NotImplementedError


class EventDetailView(APIView):
    """Handler for GET /api/events/{event_id}"""

    def get(self, request: Request, event_id: str) -> Response:
        raise NotImplementedError


class SessionListView(APIView):
    """Handler for GET /api/events/{event_id}/sessions"""

    def get(self, request: Request, event_id: str) -> Response:
        raise NotImplementedError
