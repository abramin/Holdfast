# PRD-001: Event Catalog & Discovery

## Overview

The Event Catalog & Discovery system provides the public-facing interface for customers to browse, search, and view details about available events and their sessions. This is the primary entry point for users discovering events to attend.

## Problem Statement

Customers need an intuitive, fast, and reliable way to discover events, view available sessions with timing and pricing information, and understand ticket availability before initiating a purchase. Without this foundation, users cannot make informed decisions about event attendance.

## Goals & Objectives

- Provide a performant API for browsing and searching events
- Enable customers to view detailed event information including sessions and ticket types
- Deliver sub-100ms response times for catalog queries through effective caching
- Support high read throughput for popular event launches
- Maintain data freshness while optimizing for read performance

## User Stories

### Event Browsing
- As a customer, I want to view a list of all upcoming events so that I can discover what's available
- As a customer, I want to see event details including name, description, location, and images so I can decide if I'm interested
- As a customer, I want to view all available sessions for an event so I can choose a convenient time

### Session & Ticket Information
- As a customer, I want to see session start and end times so I can plan my schedule
- As a customer, I want to view ticket types and pricing for each session so I can choose within my budget
- As a customer, I want to see remaining capacity for sessions so I know if tickets are still available

### Admin Management
- As an admin, I want to create and edit events through an admin interface
- As an admin, I want to define sessions with specific dates, times, and capacities
- As an admin, I want to configure multiple ticket types with different prices per session

## Functional Requirements

### FR-1: Event Listing
- System shall provide an endpoint to list all events
- Event list shall include: id, name, description, location, image_url
- Events shall be returned in a paginated format
- Endpoint shall support basic filtering (future: by date, location)

### FR-2: Event Details
- System shall provide an endpoint to retrieve a single event by ID
- Response shall include full event details and associated metadata
- System shall return 404 for non-existent events

### FR-3: Session Listing
- System shall provide an endpoint to list sessions for a given event
- Sessions shall include: id, starts_at, ends_at, total_capacity
- Sessions shall be ordered by start time (ascending)

### FR-4: Ticket Type Information
- Each session shall expose its available ticket types
- Ticket types shall include: id, name, price, quantity
- Pricing shall be displayed in the system's base currency (decimal format)

### FR-5: Admin Management
- Django Admin interface shall allow CRUD operations on Events
- Django Admin shall allow management of Sessions linked to Events
- Django Admin shall allow management of TicketTypes linked to Sessions

## Technical Requirements

### TR-1: API Layer
- REST API built with Django REST Framework (DRF)
- JSON response format
- Consistent error response structure with appropriate HTTP status codes
- API versioning support for future compatibility

### TR-2: Caching Strategy
- Redis caching layer for all read endpoints
- Event list cache with 5-minute TTL
- Event detail cache with 5-minute TTL
- Session list cache with 5-minute TTL
- Cache key patterns: `events:list`, `events:{id}`, `events:{id}:sessions`

### TR-3: Cache Invalidation
- Django signals shall trigger cache invalidation on model save/delete
- Use `cache.delete_pattern()` for invalidating related cache keys
- Admin saves shall immediately invalidate relevant caches

### TR-4: Database Design
- PostgreSQL database (`ticketing_main`)
- UUID primary keys for all entities
- Proper foreign key relationships with cascading deletes
- Indexed fields for query performance

### TR-5: Data Models
- Event: id, name, description, location, image_url, created_at, updated_at
- Session: id, event_id (FK), starts_at, ends_at, total_capacity, created_at
- TicketType: id, session_id (FK), name, price, quantity, created_at

## Non-Functional Requirements

### NFR-1: Performance
- API response time < 100ms for cached requests
- API response time < 500ms for uncached requests
- Support 1000+ concurrent read requests

### NFR-2: Availability
- 99.9% uptime for read endpoints
- Graceful degradation if cache unavailable (fall back to database)

### NFR-3: Scalability
- Stateless API design to support horizontal scaling
- Cache layer designed for distributed deployment

### NFR-4: Security
- Read endpoints are public (no authentication required)
- Admin endpoints protected by Django authentication
- Input validation on all parameters

## API Specification

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/events` | List all events (cached) |
| GET | `/api/events/{id}` | Get event details (cached) |
| GET | `/api/events/{id}/sessions` | List sessions for event (cached) |

### Response Examples

**GET /api/events**
```json
{
  "results": [
    {
      "id": "uuid",
      "name": "Summer Concert",
      "description": "Annual outdoor concert",
      "location": "Central Park",
      "image_url": "https://...",
      "created_at": "2025-01-01T00:00:00Z"
    }
  ],
  "count": 1,
  "next": null,
  "previous": null
}
```

**GET /api/events/{id}/sessions**
```json
{
  "results": [
    {
      "id": "uuid",
      "starts_at": "2025-06-15T18:00:00Z",
      "ends_at": "2025-06-15T22:00:00Z",
      "total_capacity": 500,
      "ticket_types": [
        {
          "id": "uuid",
          "name": "General Admission",
          "price": "50.00",
          "quantity": 400
        },
        {
          "id": "uuid",
          "name": "VIP",
          "price": "150.00",
          "quantity": 100
        }
      ]
    }
  ]
}
```

## Dependencies

- PostgreSQL 16+ for data persistence
- Redis 7+ for caching layer
- Django 4.x with Django REST Framework

## Acceptance Criteria

- [ ] Events can be created/edited/deleted via Django Admin
- [ ] Sessions can be managed with proper event association
- [ ] Ticket types can be configured per session
- [ ] GET /api/events returns paginated event list
- [ ] GET /api/events/{id} returns event details or 404
- [ ] GET /api/events/{id}/sessions returns session list with ticket types
- [ ] All read endpoints are cached with 5-minute TTL
- [ ] Cache is invalidated when admin modifies data
- [ ] Response times < 100ms for cached requests
- [ ] API handles concurrent requests without errors

## Success Metrics

- Average response time < 50ms for cached requests
- Cache hit rate > 90% during steady state
- Zero downtime during deployments
- Admin can create a complete event with sessions and ticket types in < 5 minutes
