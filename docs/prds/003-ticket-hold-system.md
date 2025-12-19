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

### TR-1: Architecture Constraints

Per AGENTS.md, the implementation must follow these patterns:

**Handler Layer (Views)**
- Handle HTTP concerns only: request parsing, validation, response mapping
- No business logic in views/viewsets
- Accept and pass through request context
- Map domain errors to appropriate HTTP status codes
- Never expose internal error details to clients

**Service Layer**
- All business logic lives in services (HoldService)
- Depend only on interfaces (HoldStore, InventoryClient)
- Validate domain invariants
- Orchestrate hold creation with Inventory Service call
- Return domain models or domain errors

**Store Layer**
- Interfaces only (repository pattern)
- Must be swappable (in-memory for tests, Django ORM for production)
- Return domain models, never Django ORM objects directly
- Handle OutboxEvent insertion atomically with hold creation

### TR-2: Domain Model & State

Per AGENTS.md, entity lifecycle state must use closed sets (typed constants), never magic strings.

**HoldStatus (Value Object)**
```python
class HoldStatus(models.TextChoices):
    ACTIVE = "active"
    EXPIRED = "expired"
    CONVERTED = "converted"
```

**Domain State Checks**
Do not compare status directly in application logic. Use intent-revealing methods:
```python
class Hold:
    def is_active(self) -> bool: ...
    def is_expired(self) -> bool: ...
    def is_converted(self) -> bool: ...
    def can_expire(self) -> bool: ...  # active and past expiration
    def can_convert(self) -> bool: ...  # active only
```

**Hold Model**
| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key |
| session | FK(Session) | Not Null |
| ticket_type | FK(TicketType) | Not Null |
| quantity | Integer | Not Null, > 0 |
| customer_email | EmailAddress | Domain primitive, validated |
| status | HoldStatus | Typed enum, not string |
| expires_at | Timestamp | Not Null, Indexed |
| created_at | Timestamp | Not Null |
| updated_at | Timestamp | Not Null |

Index: (status, expires_at) for expiry queries

### TR-3: API Endpoint
- POST /api/holds endpoint in Django REST Framework
- Request validation with DRF serializers
- Synchronous call to Inventory Service during creation
- Return hold details including expiration time

### TR-4: Inventory Service Integration
- Django makes synchronous HTTP call to POST /inventory/hold
- Pass hold_id to Inventory Service for correlation
- Handle 409 (insufficient inventory) and return to customer
- Implement timeout (5 seconds) with appropriate error handling

### TR-5: Background Worker
- Celery Beat task scheduled every 1 minute
- Query: SELECT * FROM holds WHERE status='active' AND expires_at < NOW()
- Batch update status to 'expired'
- Publish hold.expired event for each expired hold

### TR-6: Event Publishing
- Hold events published via outbox pattern
- Insert OutboxEvent in same transaction as hold creation (atomic per AGENTS.md)
- Celery worker publishes outbox events to RabbitMQ
- Event types: hold.created, hold.expired

### TR-7: Error Handling

Per AGENTS.md:
- Use domain error codes (e.g., INSUFFICIENT_INVENTORY, INVENTORY_SERVICE_UNAVAILABLE, INVALID_HOLD_STATE)
- Map external service errors to domain errors at service boundary
- Never leak internal error details (HTTP client errors, timeouts) to clients
- Expected business failures (insufficient inventory) modeled as results, not exceptions
- Log internal details with correlation IDs for debugging

**Error Response Mapping**
| Domain Error | HTTP Status | Client Message |
|--------------|-------------|----------------|
| INSUFFICIENT_INVENTORY | 409 | Only N ticket(s) available |
| INVENTORY_SERVICE_UNAVAILABLE | 503 | Unable to process request |
| INVALID_SESSION | 400 | Session not found |
| INVALID_EMAIL | 400 | Invalid email format |

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

### NFR-5: Security (Secure-by-Design)

Per AGENTS.md secure-by-design principles:

- Strict input validation order: Origin → Size → Lexical → Syntax → Semantics
- EmailAddress as domain primitive (validated at construction, immutable)
- Quantity validated as positive integer via domain primitive
- Session/TicketType existence validated before hold creation
- No echoing of raw user input in responses
- Customer email treated as sensitive data (logged redacted)
- Request structs contain API validation; domain entities contain invariants only

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

## Testing Approach

Per AGENTS.md testing guidelines, this component follows contract-first, behavior-driven testing:

### Feature-Driven Integration Tests (Primary)
- Gherkin feature files define the authoritative contract
- Scenarios cover: hold creation, expiration, conversion, validation errors
- Execute against real components (database, Inventory Service mock)

### Example Scenarios
```gherkin
Feature: Ticket Hold System
  Scenario: Create hold successfully
    Given session "concert-123" has available tickets
    When a customer requests a hold for 2 tickets
    Then a hold is created with status "active"
    And the hold expires in 10 minutes
    And inventory is reserved in the Inventory Service

  Scenario: Hold expires automatically
    Given an active hold that expired 1 minute ago
    When the expiry worker runs
    Then the hold status is "expired"
    And a hold.expired event is published

  Scenario: Convert hold to order
    Given an active hold for customer "user@example.com"
    When the order is confirmed
    Then the hold status is "converted"
    And the hold is not processed by the expiry worker

  Scenario: Insufficient inventory
    Given only 1 ticket is available for session "concert-123"
    When a customer requests a hold for 5 tickets
    Then the request fails with "insufficient_inventory"
    And the available quantity is returned
```

### Non-Cucumber Integration Tests
- Celery worker behavior and task scheduling
- Inventory Service timeout and retry behavior
- Concurrent hold creation scenarios

### Unit Tests (Exceptional)
- HoldStatus state transition methods (can_expire, can_convert)
- EmailAddress domain primitive validation
- Must justify: "What invariant would break if removed?"

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
