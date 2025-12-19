# PRD-004: Order & Checkout System

## Overview

The Order & Checkout System manages the complete order lifecycle from checkout initiation through payment confirmation. It handles order creation, payment processing (stubbed), order status management, and event publishing for downstream systems.

## Problem Statement

After customers hold tickets, they need to complete a purchase through a reliable checkout flow that:
- Converts temporary holds into permanent orders
- Processes payments securely and reliably
- Prevents duplicate orders from retries or network issues
- Communicates order status to other services for inventory finalization
- Provides order history and status for customers and support

## Goals & Objectives

- Provide reliable order creation with idempotency guarantees
- Process payments through a stubbed payment provider (extensible)
- Maintain accurate order state through a clear state machine
- Publish order events for inventory finalization and notifications
- Support order cancellation with proper inventory release
- Enable order lookup for customers and customer support

## User Stories

### Customer Experience
- As a customer, I want to complete checkout with my held tickets
- As a customer, I want to confirm my payment to finalize the order
- As a customer, I want to see my order status and confirmation
- As a customer, I want to cancel my order if I change my mind
- As a customer, I want my retry attempts to not create duplicate orders

### System Operations
- As the Django API, I want to create orders in the Orders service
- As the Inventory service, I want to know when orders are confirmed so I can commit holds
- As an operator, I want to track order metrics and failure rates
- As customer support, I want to look up order details

## Functional Requirements

### FR-1: Order Creation
- System shall create orders with associated items
- Order shall be linked to a hold_id for traceability
- Order shall capture customer_email and item details
- Order creation shall be idempotent via Idempotency-Key header
- Duplicate idempotency keys shall return existing order

### FR-2: Order Items
- Each order shall have one or more order items
- Items shall capture: session_id, ticket_type_id, quantity, unit_price
- Total order amount shall be calculated from items

### FR-3: Order State Machine
- Orders shall transition through defined states: pending → confirmed/cancelled
- Initial state shall be "pending"
- Confirm action moves state to "confirmed" (with successful payment)
- Cancel action moves state to "cancelled"
- Terminal states (confirmed, cancelled) cannot transition further

### FR-4: Payment Processing
- System shall create a payment record when order is confirmed
- Payment shall be stubbed (always succeeds for development)
- Payment record shall track: amount, status, payment_method
- Payment status: pending → succeeded/failed
- Failed payments shall not confirm the order

### FR-5: Order Confirmation
- Confirm endpoint shall process payment and update order status
- Successful confirmation shall publish order.confirmed event
- Event shall include hold_id for inventory commit
- Confirmation shall be idempotent (confirming confirmed order succeeds)

### FR-6: Order Cancellation
- Cancel endpoint shall update order status to cancelled
- Cancellation shall publish order.cancelled event
- Cancelled orders shall trigger inventory release (via hold expiry flow)
- Only pending orders can be cancelled

### FR-7: Event Publishing
- All state changes shall be recorded in outbox table
- Background worker shall publish outbox events to RabbitMQ
- Events shall include idempotency keys for consumer deduplication

## Technical Requirements

### TR-1: Architecture Constraints

Per AGENTS.md, the implementation must follow these patterns:

**Handler Layer (Routes)**
- Handle HTTP concerns only: request parsing, validation, response mapping
- No business logic in route handlers
- Accept and pass through request context
- Map domain errors to appropriate HTTP status codes
- Never expose internal error details to clients

**Service Layer**
- All business logic lives in services (OrderService, PaymentService)
- Depend only on interfaces (OrderStore, PaymentProvider)
- Validate domain invariants and enforce state machine rules
- Orchestrate order creation, confirmation, cancellation
- Return domain models or domain errors

**Store Layer**
- Interfaces only (repository pattern)
- Must be swappable (in-memory for tests, PostgreSQL for production)
- Return domain models, never ORM objects directly
- Handle OutboxEvent insertion atomically with order state changes

### TR-2: Service Framework
- FastAPI or Django REST Framework (separate service)
- Separate database for order data isolation
- REST API with JSON payloads

### TR-3: Domain Models & State

Per AGENTS.md, entity lifecycle state must use closed sets (typed constants), never magic strings.

**OrderStatus (Value Object)**
```python
class OrderStatus(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
```

**PaymentStatus (Value Object)**
```python
class PaymentStatus(Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
```

**Domain State Checks**
Do not compare status directly in application logic. Use intent-revealing methods:
```python
class Order:
    def is_pending(self) -> bool: ...
    def is_confirmed(self) -> bool: ...
    def is_cancelled(self) -> bool: ...
    def can_confirm(self) -> bool: ...  # pending only
    def can_cancel(self) -> bool: ...   # pending only
    def is_terminal(self) -> bool: ...  # confirmed or cancelled
```

**Order**
| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key |
| customer_email | EmailAddress | Domain primitive, validated |
| status | OrderStatus | Typed enum, not string |
| total_amount | Money | Domain primitive |
| idempotency_key | IdempotencyKey | Unique, Indexed |
| created_at | Timestamp | Not Null |
| updated_at | Timestamp | Not Null |

**OrderItem**
| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key |
| order_id | UUID | Foreign Key |
| session_id | UUID | Not Null |
| ticket_type_id | UUID | Not Null |
| quantity | Quantity | Domain primitive, > 0 |
| unit_price | Money | Domain primitive |
| created_at | Timestamp | Not Null |

**Payment**
| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key |
| order_id | UUID | Foreign Key, Unique |
| amount | Money | Domain primitive |
| status | PaymentStatus | Typed enum, not string |
| payment_method | String | Default: "card_stub" |
| created_at | Timestamp | Not Null |
| updated_at | Timestamp | Not Null |

**OutboxEvent**
| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key |
| event_type | String | Not Null |
| aggregate_id | UUID | Not Null |
| payload | JSONB | Not Null |
| published | Boolean | Default: False |
| created_at | Timestamp | Not Null |
| published_at | Timestamp | Nullable |

Index: (published, created_at) for publisher queries

### TR-4: Idempotency Implementation
- Extract Idempotency-Key from request header
- Check if order exists with matching key
- If exists, return existing order (don't create duplicate)
- If not exists, create order with key stored

### TR-5: Outbox Publisher
- Celery worker polls outbox every 5 seconds
- Query: SELECT * FROM outbox WHERE published=false ORDER BY created_at LIMIT 100
- Publish to RabbitMQ and mark published=true
- Transaction: publish, then mark (at-least-once delivery)

### TR-6: Django Proxy
- Django /api/checkout endpoint proxies to Orders service
- Django /api/orders/{id} endpoint proxies to Orders service
- Django adds Idempotency-Key header from client or generates one
- Handle Orders service errors gracefully

### TR-7: Transaction Atomicity
Per AGENTS.md, all multi-write operations must be atomic:
- Order creation + OutboxEvent insert in same transaction
- Order confirmation + Payment update + OutboxEvent in same transaction
- Order cancellation + OutboxEvent in same transaction
- Use RunInTx pattern for multi-store writes

### TR-8: Error Handling

Per AGENTS.md:
- Use domain error codes (e.g., ORDER_NOT_FOUND, INVALID_STATE_TRANSITION, PAYMENT_FAILED)
- Map store/infrastructure errors to domain errors at service boundary
- Never leak internal error details to clients
- Expected business failures (cannot cancel confirmed order) modeled as results, not exceptions

**Error Response Mapping**
| Domain Error | HTTP Status | Client Message |
|--------------|-------------|----------------|
| ORDER_NOT_FOUND | 404 | Order not found |
| INVALID_STATE_TRANSITION | 400 | Cannot perform action on order in current state |
| PAYMENT_FAILED | 402 | Payment could not be processed |
| DUPLICATE_IDEMPOTENCY_KEY | 200 | Order already exists (return existing) |

## Non-Functional Requirements

### NFR-1: Performance
- Order creation < 200ms
- Order confirmation < 300ms (including payment stub)
- Support 50+ concurrent order operations

### NFR-2: Reliability
- Zero duplicate orders from retry storms
- Outbox publisher processes events within 10 seconds
- At-least-once event delivery guarantee

### NFR-3: Consistency
- Order state transitions are atomic
- Payment and order status updated in same transaction
- Outbox insert in same transaction as state change

### NFR-4: Durability
- All order data persisted to PostgreSQL
- No data loss on service restart
- Outbox events survive service failures

### NFR-5: Security (Secure-by-Design)

Per AGENTS.md secure-by-design principles:

- Internal service API (called by Django proxy, not directly by clients)
- Domain primitives enforce validity at creation (EmailAddress, Money, Quantity)
- Strict input validation order: Origin → Size → Lexical → Syntax → Semantics
- IdempotencyKey validated and sanitized at boundary
- Customer email treated as sensitive data (not logged in full)
- Payment information never stored beyond stub (future: PCI compliance)
- No echoing of raw user input in responses

## API Specification

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/orders` | Create a new order |
| GET | `/orders/{id}` | Get order details |
| POST | `/orders/{id}/confirm` | Confirm order (process payment) |
| POST | `/orders/{id}/cancel` | Cancel order |

### Request/Response Examples

**POST /orders**
```
Headers:
  Idempotency-Key: uuid

Request:
{
  "customer_email": "user@example.com",
  "hold_id": "uuid",
  "items": [
    {
      "session_id": "uuid",
      "ticket_type_id": "uuid",
      "quantity": 2,
      "unit_price": 50.00
    }
  ]
}

Response (201):
{
  "order_id": "uuid",
  "status": "pending",
  "total_amount": 100.00,
  "items": [...],
  "created_at": "ISO8601"
}

Response (200 - Duplicate):
{
  "order_id": "uuid",
  "status": "pending",  // or current status
  "total_amount": 100.00,
  "message": "Order already exists for this idempotency key"
}
```

**POST /orders/{id}/confirm**
```
Request: {}

Response (200):
{
  "order_id": "uuid",
  "status": "confirmed",
  "payment": {
    "status": "succeeded",
    "amount": 100.00
  }
}

Response (400):
{
  "error": "invalid_state",
  "message": "Order is already confirmed"
}
```

**POST /orders/{id}/cancel**
```
Request: {}

Response (200):
{
  "order_id": "uuid",
  "status": "cancelled"
}

Response (400):
{
  "error": "invalid_state",
  "message": "Cannot cancel confirmed order"
}
```

## Event Schema

### order.confirmed
```json
{
  "event_id": "uuid",
  "event_type": "order.confirmed",
  "occurred_at": "ISO8601",
  "aggregate_id": "order_id",
  "idempotency_key": "uuid",
  "payload": {
    "order_id": "uuid",
    "hold_id": "uuid",
    "customer_email": "user@example.com",
    "total_amount": 100.00,
    "items": [
      {
        "session_id": "uuid",
        "ticket_type_id": "uuid",
        "quantity": 2,
        "unit_price": 50.00
      }
    ]
  }
}
```

### order.cancelled
```json
{
  "event_id": "uuid",
  "event_type": "order.cancelled",
  "occurred_at": "ISO8601",
  "aggregate_id": "order_id",
  "payload": {
    "order_id": "uuid",
    "reason": "user_requested"
  }
}
```

## Dependencies

- PostgreSQL 16+ for data persistence
- RabbitMQ 3.x for event publishing
- Celery + Redis for outbox publisher
- Django Monolith (API gateway/proxy)
- Inventory Service (consumes order.confirmed)

## Testing Approach

Per AGENTS.md testing guidelines, this component follows contract-first, behavior-driven testing:

### Feature-Driven Integration Tests (Primary)
- Gherkin feature files define the authoritative contract
- Scenarios cover: order creation, confirmation, cancellation, idempotency, state transitions
- Execute against real database with transaction behavior

### Example Scenarios
```gherkin
Feature: Order Management
  Scenario: Create order with idempotency
    Given a valid hold exists for customer "user@example.com"
    When an order is created with idempotency key "key-123"
    Then the order is created with status "pending"

  Scenario: Duplicate idempotency key returns existing order
    Given an order exists with idempotency key "key-123"
    When another order is created with idempotency key "key-123"
    Then the existing order is returned
    And no new order is created

  Scenario: Confirm pending order
    Given a pending order exists
    When the order is confirmed
    Then the order status is "confirmed"
    And a payment record is created with status "succeeded"
    And an order.confirmed event is published

  Scenario: Cannot cancel confirmed order
    Given a confirmed order exists
    When a cancellation is attempted
    Then the request fails with "invalid_state"
    And the order remains confirmed
```

### Non-Cucumber Integration Tests
- Outbox publisher behavior and timing
- Transaction rollback on partial failures
- Concurrent order operations with same idempotency key

### Unit Tests (Exceptional)
- OrderStatus and PaymentStatus state transition methods
- Money and Quantity domain primitive validation
- Total amount calculation from order items
- Must justify: "What invariant would break if removed?"

## Acceptance Criteria

- [ ] POST /orders creates order with pending status
- [ ] Duplicate Idempotency-Key returns existing order
- [ ] POST /orders/{id}/confirm updates status and processes payment
- [ ] Confirmed order publishes order.confirmed event
- [ ] POST /orders/{id}/cancel updates status to cancelled
- [ ] Cancelled order publishes order.cancelled event
- [ ] Cannot cancel already-confirmed order
- [ ] GET /orders/{id} returns order details
- [ ] Outbox events published within 10 seconds
- [ ] 100 concurrent orders with unique keys all succeed
- [ ] 100 retries with same key return same order (no duplicates)

## Success Metrics

- Zero duplicate orders in production
- Order confirmation success rate > 99% (stub payment)
- Outbox publishing lag < 5 seconds p99
- Order creation to confirmation < 1 second total
