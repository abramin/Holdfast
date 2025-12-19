# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Event ticketing platform for practicing Django, FastAPI, RabbitMQ, and distributed system patterns (idempotency, outbox, eventual consistency). Implements inventory holds and order processing with three services.

## Technology Stack

- **Django + DRF** (port 8000): Events catalog, holds orchestration, public API
- **FastAPI** (port 8001): Inventory service for high-throughput seat allocation
- **FastAPI** (port 8002): Orders service with payment processing
- **Postgres**: Separate schemas per service
- **Redis**: Caching for read-heavy endpoints
- **RabbitMQ**: Topic exchange for events (`ticketing.events`)
- **Celery**: Background workers (hold expiry, outbox publisher)
- **Docker Compose**: Local orchestration

## Commands

```bash
# Start all services
docker compose up

# Run Django migrations
docker compose exec django-api python manage.py migrate

# Run tests (when implemented)
docker compose exec django-api pytest
docker compose exec inventory-api pytest
docker compose exec orders-api pytest

# Access RabbitMQ management UI
open http://localhost:15672  # user: ticketing, pass: dev
```

## Architecture

### Service Boundaries

1. **Django Monolith** (`django-api`): Event catalog CRUD, hold orchestration, proxies checkout to Orders
2. **Inventory Service** (`inventory-api`): Atomic seat allocation with `SELECT FOR UPDATE`, consumes order events
3. **Orders Service** (`orders-api`): Order lifecycle state machine, idempotency via header, publishes via outbox

### Data Flow: Hold → Checkout → Confirm

1. POST /api/holds → Django creates Hold → calls Inventory to decrement
2. POST /api/checkout → Django proxies to Orders with Idempotency-Key
3. POST /orders/{id}/confirm → Orders stubs payment → publishes order.confirmed
4. Inventory consumes order.confirmed → commits hold
5. Celery beat expires holds → publishes hold.expired → Inventory releases

### RabbitMQ Events

Exchange: `ticketing.events` (topic). Events: `hold.created`, `hold.expired`, `order.confirmed`, `order.cancelled`. Consumers must be idempotent (dedupe table with event_id).

## Non-Negotiable Rules (from AGENTS.md)

- **No business logic in handlers** — handlers do HTTP concerns only
- **No globals** — depend on interfaces
- **Services own orchestration** — all business logic lives in services
- **Domain entities have no API input rules** — keep domain and transport separate
- **Stores return domain models** — never persistence structs
- **Internal errors never exposed** — map to domain errors at service boundary
- **All multi-write operations atomic** — use `RunInTx` for multi-store writes

### Domain State Checks

- Never compare states directly (e.g., `status == Pending`)
- Use intent-revealing methods: `IsPending()`, `CanTransitionTo()`
- Direct comparisons only for: serialization, transport wiring, test setup

### Validation Placement

- **Domain invariants**: Must always hold; enforced via constructors
- **API input rules**: Flow-specific; may change without data migration; enforced on request structs

## Testing Approach

Contract-first, behavior-driven testing:

1. **Feature-driven integration tests (primary)**: Gherkin feature files are authoritative contracts. Execute real components.
2. **Non-Cucumber integration tests**: Only when behavior involves concurrency, timing, or partial failure
3. **Unit tests (exceptional)**: Only for invariants, edge cases unreachable via integration, or pure functions

**Testing Rules**:
- Avoid mocks; use only for failure modes
- No behavior tested at multiple layers without justification
- Tests are not deleted automatically — classify first, then justify

## Review Agents

Five focused agents with narrow scopes. Use the smallest set needed for the task.

| Agent | Scope | When to use |
|-------|-------|-------------|
| `/security-review` | AuthN/AuthZ, secrets, config, logging safety | Changing exposed surfaces, auth, config, deps |
| `/ddd-review` | Aggregates, invariants, value objects, boundaries | Changing domain logic or service boundaries |
| `/testing-review` | Contracts, behavior verification, scenario coverage | Changing behavior, contracts, or refactoring |
| `/performance-review` | p95, saturation, DB patterns, cache correctness | Changing hot paths, concurrency, caching, DB |

**Note**: A 5th agent (Secure-by-Design) exists for architectural security but is invoked manually when changing boundaries, auth, lifecycles, or domain primitives.

### Conflict Resolution

1. Correctness beats performance
2. Security beats convenience
3. Contracts beat implementation details
4. If agents disagree, prefer the smallest change that satisfies both

## Key Patterns to Implement

1. **Idempotency**: `Idempotency-Key` header stored in Orders
2. **Outbox**: Insert events in same transaction, publish async via Celery
3. **Optimistic Locking**: `SELECT FOR UPDATE` in Inventory
4. **Cache Invalidation**: Django signals delete cache on model save
5. **Consumer Dedupe**: `consumed_events(event_id unique)`
6. **DLQ**: Dead Letter Queue after 3 retries
