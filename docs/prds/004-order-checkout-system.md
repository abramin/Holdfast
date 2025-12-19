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

### TR-1: Service Framework
- FastAPI or Django REST Framework (separate service)
- Separate database for order data isolation
- REST API with JSON payloads

### TR-2: Data Models

**Order**
| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key |
| customer_email | String | Not Null |
| status | String | Enum: pending, confirmed, cancelled |
| total_amount | Decimal | Not Null |
| idempotency_key | String | Unique, Indexed |
| created_at | Timestamp | Not Null |
| updated_at | Timestamp | Not Null |

**OrderItem**
| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key |
| order_id | UUID | Foreign Key |
| session_id | UUID | Not Null |
| ticket_type_id | UUID | Not Null |
| quantity | Integer | Not Null |
| unit_price | Decimal | Not Null |
| created_at | Timestamp | Not Null |

**Payment**
| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key |
| order_id | UUID | Foreign Key, Unique |
| amount | Decimal | Not Null |
| status | String | Enum: pending, succeeded, failed |
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

### TR-3: Idempotency Implementation
- Extract Idempotency-Key from request header
- Check if order exists with matching key
- If exists, return existing order (don't create duplicate)
- If not exists, create order with key stored

### TR-4: Outbox Publisher
- Celery worker polls outbox every 5 seconds
- Query: SELECT * FROM outbox WHERE published=false ORDER BY created_at LIMIT 100
- Publish to RabbitMQ and mark published=true
- Transaction: publish, then mark (at-least-once delivery)

### TR-5: Django Proxy
- Django /api/checkout endpoint proxies to Orders service
- Django /api/orders/{id} endpoint proxies to Orders service
- Django adds Idempotency-Key header from client or generates one
- Handle Orders service errors gracefully

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
