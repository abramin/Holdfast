# PRD-002: Inventory Management Service

## Overview

The Inventory Management Service is a high-throughput microservice responsible for atomic seat allocation, hold management, and maintaining inventory consistency under concurrent load. It serves as the source of truth for ticket availability.

## Problem Statement

Event ticketing systems face significant challenges with inventory management:
- Concurrent users attempting to purchase the same limited tickets
- Race conditions leading to overselling
- Need for temporary holds during checkout process
- Maintaining accurate availability counts in real-time

Without a dedicated, optimized inventory service, the system risks overselling tickets, poor user experience from failed purchases, and data inconsistency across services.

## Goals & Objectives

- Provide atomic inventory operations that prevent overselling
- Support high-throughput concurrent requests (100+ RPS per session)
- Enable temporary holds with automatic expiration
- Maintain strong consistency guarantees for inventory counts
- Expose real-time availability information
- Process inventory commits and releases based on order events

## User Stories

### Inventory Operations
- As the Django API, I want to reserve inventory for a hold so customers can proceed to checkout
- As the Django API, I want to check current availability so customers see accurate counts
- As the Orders service, I want to commit held inventory when an order is confirmed
- As the system, I want to release inventory when holds expire so tickets become available again

### Reliability
- As an operator, I want inventory operations to be idempotent so retries don't cause issues
- As an operator, I want to see inventory state for debugging and customer support
- As an operator, I want the service to handle concurrent requests without data corruption

## Functional Requirements

### FR-1: Inventory Item Management
- System shall track inventory per session and ticket type combination
- Each inventory item shall maintain total and available quantities
- Inventory items shall be uniquely identified by (session_id, ticket_type_id)

### FR-2: Hold Creation
- System shall accept hold requests with hold_id, session_id, ticket_type_id, quantity, and expiration
- System shall atomically decrement available_quantity when creating a hold
- System shall reject holds when available_quantity < requested quantity
- System shall return success if hold_id already exists with held status (idempotency)

### FR-3: Hold Release
- System shall accept release requests by hold_id
- System shall atomically increment available_quantity when releasing
- System shall update hold status to "released"
- System shall be idempotent (releasing already-released hold returns success)

### FR-4: Hold Commit
- System shall accept commit requests by hold_id
- System shall update hold status to "committed" (no quantity change)
- System shall be idempotent (committing already-committed hold returns success)
- Commits shall be triggered by order.confirmed events

### FR-5: Availability Query
- System shall provide endpoint to check current availability
- Query by session_id and ticket_type_id
- Return total_quantity, available_quantity, and held count

### FR-6: Event Consumption
- System shall consume `order.confirmed` events and commit corresponding holds
- System shall consume `hold.expired` events and release inventory
- System shall maintain idempotency through event deduplication

## Technical Requirements

### TR-1: Framework & Language
- FastAPI framework for high-performance async operations
- Python 3.11+ with async/await patterns
- Pydantic for request/response validation

### TR-2: Database Design
- PostgreSQL database (`ticketing_inventory`)
- Separate database from Django monolith (data isolation)
- UUID references to Django entities (session_id, ticket_type_id)

### TR-3: Concurrency Control
- `SELECT FOR UPDATE` on InventoryItem during hold/release/commit
- Row-level locking to prevent race conditions
- Transaction isolation level: READ COMMITTED

### TR-4: Data Models

**InventoryItem**
| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key |
| session_id | UUID | Not Null |
| ticket_type_id | UUID | Not Null |
| total_quantity | Integer | Not Null |
| available_quantity | Integer | Not Null, >= 0 |
| created_at | Timestamp | Not Null |
| updated_at | Timestamp | Not Null |

Index: UNIQUE(session_id, ticket_type_id)

**InventoryHold**
| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key (matches Django Hold.id) |
| inventory_item_id | UUID | Foreign Key |
| quantity | Integer | Not Null |
| status | String | Enum: held, released, committed |
| expires_at | Timestamp | Not Null |
| created_at | Timestamp | Not Null |
| updated_at | Timestamp | Not Null |

Index: (expires_at, status) for expiry queries

### TR-5: Message Consumption
- RabbitMQ consumer for `hold.expired` and `order.confirmed` events
- Consumer deduplication table: consumed_events(event_id UNIQUE, consumed_at)
- At-least-once delivery with idempotent processing

### TR-6: Idempotency
- Hold operations idempotent by hold_id
- If hold_id exists with status=held, return success without modification
- If hold_id exists with status=released/committed, return appropriate response

## Non-Functional Requirements

### NFR-1: Performance
- Hold creation < 50ms at p99
- Support 100+ concurrent hold requests per session
- Support 500+ read requests per second

### NFR-2: Consistency
- Zero oversells (available_quantity never goes negative)
- Strong consistency for inventory writes
- Eventual consistency acceptable for read replicas (if added)

### NFR-3: Availability
- 99.9% uptime for critical hold/release/commit operations
- Graceful degradation on consumer failures (queue backpressure)

### NFR-4: Durability
- All inventory changes persisted before acknowledgment
- No data loss during service restarts

## API Specification

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/inventory/hold` | Reserve inventory for a hold |
| POST | `/inventory/release` | Release a hold |
| POST | `/inventory/commit` | Commit a hold to order |
| GET | `/inventory/items/{session_id}/{ticket_type_id}` | Check availability |

### Request/Response Examples

**POST /inventory/hold**
```json
Request:
{
  "hold_id": "uuid",
  "session_id": "uuid",
  "ticket_type_id": "uuid",
  "quantity": 2,
  "expires_at": "2025-01-15T10:30:00Z"
}

Response (200):
{
  "success": true,
  "available_quantity": 48
}

Response (409):
{
  "success": false,
  "error": "insufficient_inventory",
  "available_quantity": 1
}
```

**POST /inventory/release**
```json
Request:
{
  "hold_id": "uuid"
}

Response (200):
{
  "success": true
}
```

**GET /inventory/items/{session_id}/{ticket_type_id}**
```json
Response (200):
{
  "session_id": "uuid",
  "ticket_type_id": "uuid",
  "total_quantity": 100,
  "available_quantity": 48,
  "held_quantity": 52
}
```

## Dependencies

- PostgreSQL 16+ for data persistence
- RabbitMQ 3.x for event consumption
- Django Monolith (source of session/ticket type definitions)
- Orders Service (source of order.confirmed events)

## Acceptance Criteria

- [ ] POST /inventory/hold reserves inventory atomically
- [ ] Concurrent hold requests for same inventory don't oversell
- [ ] Hold with insufficient inventory returns 409 with available count
- [ ] Duplicate hold_id requests return success (idempotency)
- [ ] POST /inventory/release increments available_quantity
- [ ] POST /inventory/commit updates hold status without quantity change
- [ ] GET availability returns accurate counts
- [ ] Consumer processes order.confirmed and commits holds
- [ ] Consumer processes hold.expired and releases inventory
- [ ] Event deduplication prevents duplicate processing
- [ ] Load test: 50 concurrent holds on same session, zero oversells

## Success Metrics

- Zero oversells in production
- p99 latency < 50ms for hold operations
- 100% event processing success rate (after retries)
- Consumer lag < 1 second during normal operation
