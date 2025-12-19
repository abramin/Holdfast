
# Event Ticketing Platform - Architecture Overview

## System Purpose

Practice Django, FastAPI, RabbitMQ, and distributed system patterns (idempotency, outbox, eventual consistency) by building an event ticketing system with inventory holds and order processing.

## Technology Stack

- **Django + DRF**: Monolith (events catalog, holds orchestration, public API)
- **FastAPI**: Inventory service (high-throughput seat allocation)
- **Postgres**: All service databases (separate schemas per service)
- **Redis**: Caching layer for read-heavy endpoints
- **RabbitMQ**: Message broker (topics, fanout exchanges)
- **Celery**: Background workers (hold expiry, outbox publisher)
- **Docker Compose**: Local orchestration

## Service Architecture

### 1. Django Monolith (`django-api`)

**Port**: 8000  
**Database**: `ticketing_main`

**Responsibilities**:

- Event catalog management (CRUD via admin)
- Public read API (cached)
- Hold orchestration (creates holds, calls Inventory service)
- Checkout orchestration (calls Orders service)
- Authentication (simple token auth)

**Models**:

```python
# events/models.py
class Event:
    id: UUID
    name: str
    description: text
    location: str
    image_url: str (optional)
    created_at: datetime
    updated_at: datetime

class Session:
    id: UUID
    event: FK(Event)
    starts_at: datetime
    ends_at: datetime
    total_capacity: int
    created_at: datetime

class TicketType:
    id: UUID
    session: FK(Session)
    name: str  # e.g. "General Admission", "VIP"
    price: decimal
    quantity: int
    created_at: datetime

class Hold:
    id: UUID
    session: FK(Session)
    ticket_type: FK(TicketType)
    quantity: int
    customer_email: str
    status: str  # active, expired, converted
    expires_at: datetime
    created_at: datetime
    updated_at: datetime

class Customer:
    id: UUID
    email: str (unique)
    name: str
    created_at: datetime
```

**Endpoints**:

```
GET  /api/events                    # List events (cached, 5min TTL)
GET  /api/events/{id}               # Event detail (cached)
GET  /api/events/{id}/sessions      # Sessions for event (cached)
POST /api/holds                     # Create hold (calls Inventory)
POST /api/checkout                  # Start checkout (calls Orders)
GET  /api/orders/{id}               # Order status (proxies to Orders service)
```

**Key Patterns**:

- Cache invalidation on admin save (cache.delete_pattern)
- Synchronous HTTP call to Inventory service during hold creation
- No direct DB writes to orders—proxy to Orders service
- Publishes events via outbox table

### 2. Inventory Service (`inventory-api`)

**Port**: 8001  
**Database**: `ticketing_inventory`

**Responsibilities**:

- Atomic seat allocation
- Hold management (reserve, release, commit)
- Inventory consistency under concurrency
- Consumes order events to finalize inventory

**Models**:

```python
# models.py
class InventoryItem:
    id: UUID
    session_id: UUID  # references Session in Django
    ticket_type_id: UUID
    total_quantity: int
    available_quantity: int  # updated atomically
    created_at: datetime
    updated_at: datetime
    
    # Index: (session_id, ticket_type_id) unique

class InventoryHold:
    id: UUID  # matches Hold.id from Django
    inventory_item: FK(InventoryItem)
    quantity: int
    status: str  # held, released, committed
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    
    # Index: (id) unique, (expires_at, status)
```

**Endpoints**:

```
POST /inventory/hold      # Reserve inventory (idempotent via hold_id)
POST /inventory/release   # Release a hold
POST /inventory/commit    # Commit hold to order (via event consumer)
GET  /inventory/items/{session_id}/{ticket_type_id}  # Check availability
```

**Request/Response Examples**:

```json
POST /inventory/hold
{
  "hold_id": "uuid",
  "session_id": "uuid",
  "ticket_type_id": "uuid",
  "quantity": 2,
  "expires_at": "2025-01-15T10:30:00Z"
}
→ 200 {"success": true, "available_quantity": 48}
→ 409 {"success": false, "error": "insufficient_inventory"}

POST /inventory/release
{
  "hold_id": "uuid"
}
→ 200 {"success": true}
```

**Key Patterns**:

- `SELECT FOR UPDATE` on InventoryItem during hold/release
- Idempotency: if hold_id exists and status=held, return success
- Consumer: listens to `order.confirmed` and commits holds
- Consumer: listens to `hold.expired` and releases inventory

### 3. Orders Service (`orders-api`)

**Port**: 8002  
**Database**: `ticketing_orders`

**Responsibilities**:

- Order lifecycle state machine
- Payment processing (stubbed)
- Idempotency enforcement
- Event publishing via outbox

**Models**:

```python
# models.py
class Order:
    id: UUID
    customer_email: str
    status: str  # pending, confirmed, cancelled
    total_amount: decimal
    idempotency_key: str (unique, indexed)
    created_at: datetime
    updated_at: datetime

class OrderItem:
    id: UUID
    order: FK(Order)
    session_id: UUID
    ticket_type_id: UUID
    quantity: int
    unit_price: decimal
    created_at: datetime

class Payment:
    id: UUID
    order: FK(Order, unique)
    amount: decimal
    status: str  # pending, succeeded, failed
    payment_method: str  # stub: "card_stub"
    created_at: datetime
    updated_at: datetime

class OutboxEvent:
    id: UUID
    event_type: str  # order.confirmed, order.cancelled
    aggregate_id: UUID  # order_id
    payload: jsonb
    published: bool (default False)
    created_at: datetime
    published_at: datetime (nullable)
    
    # Index: (published, created_at)
```

**Endpoints**:

```
POST /orders           # Create order (idempotent via Idempotency-Key header)
POST /orders/{id}/confirm  # Confirm order (triggers payment stub)
POST /orders/{id}/cancel   # Cancel order
GET  /orders/{id}      # Get order details
```

**Request/Response Examples**:

```json
POST /orders
Headers: Idempotency-Key: {uuid}
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
→ 201 {"order_id": "uuid", "status": "pending", "total": 100.00}

POST /orders/{id}/confirm
{}
→ 200 {"status": "confirmed"}
```

**Key Patterns**:

- Check idempotency_key on POST /orders, return existing order if found
- On confirm: update Payment.status → succeeded, Order.status → confirmed
- Insert into OutboxEvent on state changes
- Celery worker publishes outbox events to RabbitMQ every 5s

## Data Flow: Hold → Checkout → Confirm

```
1. User requests hold
   → POST /api/holds (Django)
   → Django creates Hold (status=active, expires_at=now+10min)
   → Django calls POST /inventory/hold (Inventory)
   → Inventory decrements available_quantity with SELECT FOR UPDATE
   → Django publishes hold.created to outbox
   → Returns hold_id to user

2. User checks out
   → POST /api/checkout (Django)
   → Django calls POST /orders (Orders) with Idempotency-Key
   → Orders creates Order (status=pending)
   → Returns order_id to user

3. User confirms payment
   → POST /api/orders/{id}/confirm (Django proxies to Orders)
   → Orders stubs payment (Payment.status=succeeded)
   → Orders updates Order.status=confirmed
   → Orders inserts OutboxEvent (event_type=order.confirmed)
   → Celery worker publishes to RabbitMQ
   → Inventory consumes order.confirmed
   → Inventory updates InventoryHold.status=committed

4. Hold expires (background)
   → Celery beat task runs every 1min
   → Finds Hold where expires_at < now AND status=active
   → Updates Hold.status=expired
   → Publishes hold.expired to outbox
   → Inventory consumes hold.expired
   → Inventory releases hold (increments available_quantity)
```

## RabbitMQ Event Schema

**Exchange**: `ticketing.events` (topic)

**Events**:

```python
# hold.created
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

# hold.expired
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

# order.confirmed
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
    "items": [...]
  }
}

# order.cancelled
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

**Routing Keys**: `{event_type}` (e.g., `hold.created`, `order.confirmed`)

**Consumer Bindings**:

- Inventory service: binds to `hold.*`, `order.confirmed`
- Future Notifications: binds to `order.confirmed`, `order.cancelled`

**Delivery Guarantees**:

- At-least-once delivery (consumers must be idempotent)
- Dead Letter Queue (DLQ) after 3 retries
- Consumers maintain dedupe table: `consumed_events(event_id unique, consumed_at)`

## Infrastructure

**Docker Compose Services**:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ticketing
      POSTGRES_PASSWORD: dev
      POSTGRES_DB: ticketing
    ports: [5432:5432]
    
  redis:
    image: redis:7-alpine
    ports: [6379:6379]
    
  rabbitmq:
    image: rabbitmq:3-management
    ports: [5672:5672, 15672:15672]
    environment:
      RABBITMQ_DEFAULT_USER: ticketing
      RABBITMQ_DEFAULT_PASS: dev
      
  django-api:
    build: ./django-api
    ports: [8000:8000]
    depends_on: [postgres, redis, rabbitmq]
    environment:
      DATABASE_URL: postgres://ticketing:dev@postgres/ticketing_main
      REDIS_URL: redis://redis:6379/0
      RABBITMQ_URL: amqp://ticketing:dev@rabbitmq:5672/
      
  inventory-api:
    build: ./inventory-api
    ports: [8001:8001]
    depends_on: [postgres, rabbitmq]
    environment:
      DATABASE_URL: postgres://ticketing:dev@postgres/ticketing_inventory
      RABBITMQ_URL: amqp://ticketing:dev@rabbitmq:5672/
      
  orders-api:
    build: ./orders-api
    ports: [8002:8002]
    depends_on: [postgres, rabbitmq]
    environment:
      DATABASE_URL: postgres://ticketing:dev@postgres/ticketing_orders
      RABBITMQ_URL: amqp://ticketing:dev@rabbitmq:5672/
      
  celery-worker:
    build: ./django-api
    command: celery -A config worker -l info
    depends_on: [postgres, redis, rabbitmq]
    
  celery-beat:
    build: ./django-api
    command: celery -A config beat -l info
    depends_on: [postgres, redis, rabbitmq]
```

## Development Phases

**Phase 1: Django Foundation (Days 1-3)**

- Django project with Event, Session, TicketType models
- Admin interface for creating events
- DRF endpoints: GET /events, GET /events/{id}
- Redis caching on read endpoints
- Docker Compose: postgres, redis, django-api

**Phase 2: Inventory Service (Days 4-6)**

- FastAPI project with InventoryItem, InventoryHold models
- POST /inventory/hold with SELECT FOR UPDATE
- Test concurrent hold requests (same session)
- Django calls Inventory service during hold creation
- Docker Compose: add inventory-api

**Phase 3: Events + Outbox (Days 7-10)**

- RabbitMQ setup in Docker Compose
- OutboxEvent model in Django and Orders
- Celery worker to publish outbox → RabbitMQ
- Inventory consumer for hold.created (logs only, no action yet)
- Manual testing: create hold, see event in RabbitMQ UI

**Phase 4: Orders Service (Days 11-14)**

- Flask/FastAPI orders-api with Order, OrderItem, Payment
- POST /orders with idempotency key
- POST /orders/{id}/confirm (stub payment)
- Publish order.confirmed via outbox
- Django POST /checkout calls Orders service

**Phase 5: Reliability (Days 15-18)**

- Inventory consumer commits holds on order.confirmed
- Hold expiry Celery task (every 1min)
- Publish hold.expired, Inventory releases
- Consumer dedupe table (event_id unique constraint)
- DLQ handling (log to stderr, could add dedicated table)

**Phase 6: Load Testing (Days 19-21)**

- Locust scenarios: browse events, create holds, checkout
- Find first concurrency bug (missing index, race condition)
- Add DB indexes on hot paths
- Profile slow endpoints, optimize

## Key Patterns to Implement

1. **Idempotency**: Idempotency-Key header stored in Orders.idempotency_key
1. **Outbox**: Insert events in same transaction as state change, publish async
1. **Optimistic Locking**: Use SELECT FOR UPDATE in Inventory operations
1. **Cache Invalidation**: Django signals to delete cache keys on model save
1. **Retry Logic**: RabbitMQ requeue with backoff, DLQ after 3 attempts
1. **Dedupe**: Consumers check event_id before processing
1. **Circuit Breaker**: (Optional) Wrap Inventory calls in Django with timeout + fallback

## Success Criteria

By end of 3 weeks:

- ✅ Full hold → checkout → confirm flow works
- ✅ No inventory oversells under concurrent requests
- ✅ Events published and consumed reliably
- ✅ Idempotency prevents duplicate orders
- ✅ Hold expiry worker releases inventory correctly
- ✅ Load test: 50 concurrent users, no errors
- ✅ Can explain every design decision and tradeoff
