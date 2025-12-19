# PRD-005: Messaging & Event Infrastructure

## Overview

The Messaging & Event Infrastructure provides the backbone for asynchronous communication between services in the ticketing platform. It enables reliable event-driven architecture using RabbitMQ, the outbox pattern, and idempotent consumers.

## Problem Statement

In a distributed microservices architecture:
- Services need to communicate state changes without tight coupling
- Synchronous calls create cascading failures and latency
- Data consistency across services requires reliable event delivery
- Message loss or duplication can cause data corruption
- Debugging distributed flows requires event traceability

The messaging infrastructure solves these problems with reliable, auditable, and idempotent event processing.

## Goals & Objectives

- Enable reliable asynchronous communication between services
- Guarantee at-least-once event delivery
- Prevent duplicate processing through consumer idempotency
- Provide dead letter handling for failed messages
- Support system observability through event tracing
- Maintain loose coupling between services

## User Stories

### Event Publishing
- As the Django service, I want to publish hold events when holds are created or expire
- As the Orders service, I want to publish order events when orders are confirmed or cancelled
- As a publisher, I want my events to be durably stored before acknowledgment

### Event Consumption
- As the Inventory service, I want to receive order.confirmed events to commit holds
- As the Inventory service, I want to receive hold.expired events to release inventory
- As a consumer, I want to safely retry failed messages without duplication

### Operations
- As an operator, I want to monitor queue depths and consumer lag
- As an operator, I want to inspect failed messages in the dead letter queue
- As an operator, I want to replay failed messages after fixing issues

## Functional Requirements

### FR-1: Event Exchange
- System shall create a topic exchange named `ticketing.events`
- Exchange shall route messages based on event_type as routing key
- Exchange shall be durable (survives broker restart)

### FR-2: Event Types
- hold.created - When a new hold is created
- hold.expired - When a hold expires
- order.confirmed - When an order is confirmed
- order.cancelled - When an order is cancelled

### FR-3: Consumer Queues
- Inventory service queue bound to: hold.*, order.confirmed
- Future notification service queue bound to: order.confirmed, order.cancelled
- Queues shall be durable with message persistence

### FR-4: Outbox Pattern
- Publishers shall insert events into outbox table within business transaction
- Background worker shall poll outbox and publish to RabbitMQ
- Worker shall mark events as published after successful delivery
- Pattern ensures events are published if and only if transaction commits

### FR-5: Event Schema
- All events shall include: event_id, event_type, occurred_at, aggregate_id
- Events shall include idempotency_key where applicable
- Events shall include payload with event-specific data
- Schema versioning via event_type naming (future consideration)

### FR-6: Consumer Idempotency
- Consumers shall maintain consumed_events table
- Before processing, check if event_id exists in table
- If exists, acknowledge message without processing
- After processing, insert event_id into table within same transaction

### FR-7: Retry and Dead Letter
- Failed messages shall be requeued with exponential backoff
- After 3 retry attempts, route to dead letter queue (DLQ)
- DLQ messages shall be persisted for manual inspection
- DLQ shall retain messages for 7 days minimum

### FR-8: Message Acknowledgment
- Consumers shall use manual acknowledgment mode
- Ack only after successful processing and idempotency insert
- Nack with requeue on transient failures
- Nack without requeue after max retries (routes to DLQ)

## Technical Requirements

### TR-1: Architecture Constraints

Per AGENTS.md, the messaging infrastructure must support the following patterns:

**Outbox Pattern (Publishers)**
- Events inserted in same transaction as business state change
- Background worker publishes events asynchronously
- Ensures exactly-once semantics for event creation (linked to transaction commit)
- At-least-once delivery to message broker

**Consumer Architecture**
- Consumers follow handler/service/store pattern
- Message handler: deserialize, validate, route to service
- Service: business logic, state changes, idempotency checks
- Store: persistence, consumed_events tracking
- All multi-write operations must be atomic (per AGENTS.md)

**Idempotency**
- All consumers must be idempotent (at-least-once delivery)
- Deduplication via consumed_events table
- Business logic and dedup insert in same transaction

### TR-2: RabbitMQ Configuration
- RabbitMQ 3.x with management plugin
- Virtual host: / (default)
- User: ticketing (configurable credentials)
- Management UI on port 15672

### TR-3: Exchange Configuration
```
Exchange: ticketing.events
Type: topic
Durable: true
Auto-delete: false
```

### TR-4: Queue Configuration
```
Queue: inventory.events
Durable: true
Arguments:
  x-dead-letter-exchange: ticketing.dlx
  x-dead-letter-routing-key: inventory.events.dlq
Bindings:
  - routing_key: hold.*
  - routing_key: order.confirmed
```

### TR-5: Dead Letter Exchange
```
Exchange: ticketing.dlx
Type: direct
Durable: true

Queue: inventory.events.dlq
Durable: true
Binding: inventory.events.dlq
```

### TR-6: Outbox Table Schema

| Field | Type | Constraints |
|-------|------|-------------|
| id | UUID | Primary Key |
| event_type | String | Not Null, Indexed |
| aggregate_id | UUID | Not Null |
| payload | JSONB | Not Null |
| published | Boolean | Default: False |
| created_at | Timestamp | Not Null |
| published_at | Timestamp | Nullable |

Index: (published, created_at) for publisher polling

### TR-7: Consumed Events Table

| Field | Type | Constraints |
|-------|------|-------------|
| event_id | UUID | Primary Key |
| event_type | String | Not Null |
| consumed_at | Timestamp | Not Null |

### TR-8: Outbox Publisher Worker
- Celery task running every 5 seconds
- Batch size: 100 events per poll
- Publish message, then mark as published
- Handle RabbitMQ connection failures with retry

### TR-9: Consumer Implementation
- Async consumer using aio-pika (FastAPI) or pika (Django)
- Prefetch count: 10 (configurable)
- Manual ack mode
- Graceful shutdown with in-flight message completion

### TR-10: Error Handling

Per AGENTS.md:
- Consumer errors mapped to domain errors at service boundary
- Never leak internal error details in logs exposed externally
- Expected failures (validation errors, business rule violations) logged and sent to DLQ
- Transient failures (connection issues, timeouts) retried with backoff
- Permanent failures logged with full context for debugging

**Error Categories**
| Category | Action | Example |
|----------|--------|---------|
| Transient | Retry with backoff | RabbitMQ connection timeout |
| Validation | DLQ immediately | Malformed event payload |
| Business | DLQ after logging | Invalid state transition |
| Infrastructure | Alert + retry | Database unavailable |

## Non-Functional Requirements

### NFR-1: Reliability
- At-least-once delivery guarantee
- Zero message loss for published events
- Outbox ensures no missed events on crash

### NFR-2: Performance
- Outbox publish latency < 5 seconds
- Consumer processing < 100ms per message (excluding business logic)
- Support 100+ messages/second throughput

### NFR-3: Durability
- All queues and exchanges are durable
- Messages persisted to disk
- Survives RabbitMQ restart

### NFR-4: Observability
- Queue depth metrics exposed
- Consumer lag monitoring
- DLQ message count alerting
- Correlation IDs for request tracing

### NFR-5: Operations
- DLQ messages inspectable via management UI
- Manual message replay capability
- Queue purge capability (with confirmation)

### NFR-6: Security (Secure-by-Design)

Per AGENTS.md secure-by-design principles:

- RabbitMQ credentials never hardcoded (environment variables)
- Message payloads validated at consumer boundary before processing
- Sensitive data (customer_email) redacted in logs
- Event payloads do not contain raw user input without sanitization
- Consumer services validate event schema strictly (fail-fast)
- DLQ messages may contain sensitive data - access restricted
- Correlation IDs for tracing do not contain sensitive information

## Event Message Format

### Standard Envelope
```json
{
  "event_id": "uuid",
  "event_type": "hold.created",
  "occurred_at": "2025-01-15T10:20:00Z",
  "aggregate_id": "uuid",
  "idempotency_key": "uuid",
  "payload": {
    // Event-specific data
  }
}
```

### Message Properties
```
content_type: application/json
delivery_mode: 2 (persistent)
message_id: {event_id}
timestamp: {occurred_at as unix timestamp}
headers:
  x-retry-count: 0
```

## Consumer Bindings Summary

| Service | Queue | Routing Keys |
|---------|-------|--------------|
| Inventory | inventory.events | hold.*, order.confirmed |
| Notifications (future) | notifications.events | order.confirmed, order.cancelled |

## Dependencies

- RabbitMQ 3.x with management plugin
- PostgreSQL (for outbox and consumed_events tables)
- Celery (for outbox publisher worker)
- Redis (for Celery broker)

## Testing Approach

Per AGENTS.md testing guidelines, this infrastructure component follows contract-first, behavior-driven testing:

### Feature-Driven Integration Tests (Primary)
- Gherkin feature files define the authoritative contract
- Scenarios cover: event publishing, consumption, idempotency, DLQ routing
- Execute against real RabbitMQ instance

### Example Scenarios
```gherkin
Feature: Event Publishing and Consumption
  Scenario: Publish event via outbox pattern
    Given an order is confirmed in the database
    And an outbox event is created in the same transaction
    When the outbox publisher runs
    Then the event is published to RabbitMQ
    And the outbox event is marked as published

  Scenario: Consumer idempotency
    Given an event with id "event-123" was previously processed
    When the same event is received again
    Then the event is acknowledged without processing
    And no duplicate business action occurs

  Scenario: Failed message routing to DLQ
    Given a consumer that fails to process a message
    When the message has been retried 3 times
    Then the message is routed to the dead letter queue
    And an alert is raised

  Scenario: System recovery after RabbitMQ restart
    Given events are queued in RabbitMQ
    When RabbitMQ restarts
    Then queued messages are preserved
    And consumers resume processing
```

### Non-Cucumber Integration Tests
- Connection failure and reconnection behavior
- Concurrent consumer processing
- Outbox publisher under load
- Message ordering guarantees (or lack thereof)

### Unit Tests (Exceptional)
- Event envelope serialization/deserialization
- Retry count calculation and backoff timing
- Must justify: "What invariant would break if removed?"

## Acceptance Criteria

- [ ] ticketing.events exchange created and configured
- [ ] Consumer queues bound with correct routing keys
- [ ] Outbox table created in Django and Orders databases
- [ ] Outbox publisher runs every 5 seconds
- [ ] Published events visible in RabbitMQ management UI
- [ ] Consumers receive and process events
- [ ] Duplicate event_id not processed twice
- [ ] Failed message retried up to 3 times
- [ ] After 3 failures, message routed to DLQ
- [ ] DLQ messages visible in management UI
- [ ] Consumer gracefully shuts down
- [ ] System recovers from RabbitMQ restart

## Success Metrics

- Event publishing lag < 5 seconds p95
- Consumer processing success rate > 99.9%
- DLQ message rate < 0.1%
- Zero duplicate event processing
- Zero lost events
- RabbitMQ uptime > 99.9%

## Monitoring & Alerting

### Key Metrics
- `rabbitmq_queue_depth` - Messages waiting in queue
- `rabbitmq_consumer_lag` - Time since oldest unacked message
- `outbox_unpublished_count` - Events waiting to be published
- `dlq_message_count` - Messages in dead letter queue

### Alert Thresholds
- Queue depth > 1000: Warning
- Queue depth > 5000: Critical
- Consumer lag > 60 seconds: Warning
- DLQ messages > 10: Warning (investigate failures)
- Outbox unpublished > 100: Critical (publisher may be stuck)
