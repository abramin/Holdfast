# PRD-003: Ticket Hold System

## Overview

The Ticket Hold System enables customers to temporarily reserve tickets while completing their purchase. Holds ensure that customers don't lose tickets during the checkout process while preventing inventory from being locked indefinitely.

## Problem Statement

Without a hold system:
- Customers may add tickets to cart only to find them sold out at checkout
- Long checkout times could lock inventory indefinitely
- No mechanism to fairly manage contention during high-demand events
- Poor user experience leads to abandoned purchases and customer frustration

The hold system creates a time-limited reservation that balances customer experience with inventory fairness.

## Goals & Objectives

- Allow customers to reserve tickets for a limited time (10 minutes)
- Prevent sold-out disappointments during checkout
- Automatically release expired holds to maintain inventory availability
- Coordinate between Django API and Inventory Service reliably
- Provide visibility into hold status for customers

## User Stories

### Customer Experience
- As a customer, I want to hold tickets while I enter payment details so they won't be sold to someone else
- As a customer, I want to know how long my hold is valid so I can complete checkout in time
- As a customer, I want my hold to automatically extend to checkout if I'm actively purchasing
- As a customer, I want to be notified if my hold is about to expire

### System Operations
- As the system, I want to automatically expire holds after the timeout period
- As the system, I want to release expired hold inventory back to available pool
- As the system, I want to convert holds to orders when checkout completes
- As an operator, I want to monitor hold creation rates and expiry patterns

## Functional Requirements

### FR-1: Hold Creation
- System shall create a hold when customer initiates ticket selection
- Hold shall reserve specific quantity of a ticket type for a session
- Hold shall have a configurable expiration time (default: 10 minutes)
- System shall call Inventory Service to reserve inventory atomically
- Hold shall fail if insufficient inventory is available

### FR-2: Hold Data
- Hold shall capture: customer_email, session, ticket_type, quantity
- Hold shall track status: active, expired, converted
- Hold shall store expiration timestamp
- Hold shall maintain creation and update timestamps

### FR-3: Hold Expiration
- Background worker shall run every 1 minute
- Worker shall find all holds where expires_at < now AND status = active
- Worker shall update hold status to "expired"
- Worker shall publish hold.expired event to message queue
- Inventory Service shall consume event and release inventory

### FR-4: Hold Conversion
- When order is confirmed, hold status shall update to "converted"
- Converted holds shall not be subject to expiration processing
- Hold.id shall be linked to order for traceability

### FR-5: Hold Validation
- System shall validate customer email format
- System shall validate quantity > 0
- System shall validate session and ticket_type exist
- System shall validate expiration is in the future

## Technical Requirements

### TR-1: Hold Model (Django)

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key |
| session | FK(Session) | Not Null |
| ticket_type | FK(TicketType) | Not Null |
| quantity | Integer | Not Null, > 0 |
| customer_email | String | Not Null, Valid Email |
| status | String | Enum: active, expired, converted |
| expires_at | Timestamp | Not Null, Indexed |
| created_at | Timestamp | Not Null |
| updated_at | Timestamp | Not Null |

Index: (status, expires_at) for expiry queries

### TR-2: API Endpoint
- POST /api/holds endpoint in Django REST Framework
- Request validation with DRF serializers
- Synchronous call to Inventory Service during creation
- Return hold details including expiration time

### TR-3: Inventory Service Integration
- Django makes synchronous HTTP call to POST /inventory/hold
- Pass hold_id to Inventory Service for correlation
- Handle 409 (insufficient inventory) and return to customer
- Implement timeout (5 seconds) with appropriate error handling

### TR-4: Background Worker
- Celery Beat task scheduled every 1 minute
- Query: SELECT * FROM holds WHERE status='active' AND expires_at < NOW()
- Batch update status to 'expired'
- Publish hold.expired event for each expired hold

### TR-5: Event Publishing
- Hold events published via outbox pattern
- Insert OutboxEvent in same transaction as hold creation
- Celery worker publishes outbox events to RabbitMQ
- Event types: hold.created, hold.expired

### TR-6: Error Handling
- If Inventory Service unavailable, return 503 to customer
- If Inventory Service returns 409, return 409 with message
- Log all errors with correlation IDs
- Implement circuit breaker for Inventory Service calls (optional)

## Non-Functional Requirements

### NFR-1: Performance
- Hold creation < 500ms including Inventory Service call
- Expiry worker processes 1000+ holds per minute
- Support 100+ concurrent hold creations

### NFR-2: Reliability
- Hold creation must be atomic (all-or-nothing)
- If Inventory hold succeeds, Django hold must be created
- Expiry worker must be crash-safe (resumable)

### NFR-3: Timeliness
- Expired holds processed within 2 minutes of expiration
- Hold expiry worker lag monitoring

### NFR-4: Observability
- Log hold creation, expiration, and conversion events
- Metrics: holds_created, holds_expired, holds_converted
- Alerts on expiry worker failures

## API Specification

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/holds` | Create a new hold |
| GET | `/api/holds/{id}` | Get hold status (optional) |

### Request/Response Examples

**POST /api/holds**
```json
Request:
{
  "session_id": "uuid",
  "ticket_type_id": "uuid",
  "quantity": 2,
  "customer_email": "user@example.com"
}

Response (201):
{
  "hold_id": "uuid",
  "session_id": "uuid",
  "ticket_type_id": "uuid",
  "quantity": 2,
  "status": "active",
  "expires_at": "2025-01-15T10:30:00Z",
  "created_at": "2025-01-15T10:20:00Z"
}

Response (409):
{
  "error": "insufficient_inventory",
  "message": "Only 1 ticket(s) available",
  "available_quantity": 1
}

Response (503):
{
  "error": "service_unavailable",
  "message": "Unable to process hold request. Please try again."
}
```

## Event Schema

### hold.created
```json
{
  "event_id": "uuid",
  "event_type": "hold.created",
  "occurred_at": "ISO8601",
  "aggregate_id": "hold_id",
  "idempotency_key": "uuid",
  "payload": {
    "hold_id": "uuid",
    "session_id": "uuid",
    "ticket_type_id": "uuid",
    "quantity": 2,
    "customer_email": "user@example.com",
    "expires_at": "ISO8601"
  }
}
```

### hold.expired
```json
{
  "event_id": "uuid",
  "event_type": "hold.expired",
  "occurred_at": "ISO8601",
  "aggregate_id": "hold_id",
  "payload": {
    "hold_id": "uuid",
    "session_id": "uuid",
    "ticket_type_id": "uuid",
    "quantity": 2
  }
}
```

## Dependencies

- Inventory Service (must be available for hold creation)
- RabbitMQ (for event publishing)
- Celery + Redis (for background workers)
- PostgreSQL (for hold persistence)

## Acceptance Criteria

- [ ] POST /api/holds creates hold and reserves inventory
- [ ] Hold expiration defaults to 10 minutes from creation
- [ ] Insufficient inventory returns 409 with available count
- [ ] Invalid email returns 400 validation error
- [ ] Expiry worker runs every minute
- [ ] Expired holds status updated to 'expired'
- [ ] hold.expired event published for each expiration
- [ ] Inventory Service releases inventory on hold.expired
- [ ] Order confirmation updates hold status to 'converted'
- [ ] Converted holds not processed by expiry worker
- [ ] Hold creation < 500ms under normal conditions
- [ ] 100 concurrent hold creations succeed without errors

## Success Metrics

- Average hold creation time < 300ms
- < 1% hold creation failures (excluding inventory unavailable)
- 100% of expired holds processed within 2 minutes
- Hold-to-order conversion rate > 60% (business health metric)
- Zero orphaned holds (active past expiration + grace period)
