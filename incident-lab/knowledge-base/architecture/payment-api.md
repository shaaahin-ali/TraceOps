# payment-api Architecture

**Document ID:** ARCH-001  
**Service:** payment-api  
**Version:** 2.4  
**Updated:** 2026-08-01

---

## Overview

The payment-api is a FastAPI-based payment processing service.
It handles payment creation, retrieval, and history queries.
It depends on PostgreSQL for persistence and an external fraud-service for risk assessment.

---

## Architecture Diagram

```
Client
  │
  ▼
FastAPI (payment-api)
  │
  ├── PostgreSQL (payments DB)
  │     └── SQLAlchemy + asyncpg
  │
  └── fraud-service (HTTP)
        └── POST /check
```

---

## Components

### FastAPI Application

- `app/main.py` — application entry point, lifespan, middleware
- `app/config.py` — environment-based configuration
- `app/database.py` — async engine, session factory, connection pool
- `app/auth.py` — JWT authentication
- `app/fraud_service.py` — HTTP client for fraud-service
- `app/repository.py` — database queries
- `app/services.py` — business logic
- `app/models.py` — SQLAlchemy ORM models
- `app/schemas.py` — Pydantic request/response schemas
- `app/routers/` — FastAPI router modules
- `app/cache.py` — in-memory response cache (added v2.3.2)

---

## Database

- **PostgreSQL 16**
- **Connection pool**: SQLAlchemy asyncpg with configurable pool_size and max_overflow
- **Default pool_size**: 10
- **Default max_overflow**: 20
- **Pool timeout**: 30 seconds

### Critical configuration (app/config.py)

```python
db_pool_size: int = 10       # MUST NOT be None — see RUNBOOK-001
db_max_overflow: int = 20    # Additional connections beyond pool_size
```

---

## External Dependencies

### fraud-service

- **URL**: configurable via `FRAUD_SERVICE_URL`
- **Timeout**: configurable via `FRAUD_SERVICE_TIMEOUT` (default: 5 seconds)
- **Behavior on timeout**: returns `{"approved": True, "risk_level": "unknown"}`
- **Behavior on error**: returns `{"approved": True, "risk_level": "unknown"}`

⚠️ **Critical**: If the fraud-service timeout is removed or set to `None`,
payment API requests will block indefinitely when fraud-service is slow.

---

## Authentication

- **Mechanism**: JWT Bearer tokens
- **Algorithm**: HS256 (must match in both `create_access_token` and `jwt.decode`)
- **Secret**: `JWT_SECRET` environment variable

⚠️ **Critical**: The `algorithms` parameter in `jwt.decode()` must match the
algorithm used during token creation. A mismatch causes all tokens to fail validation.

---

## Known Failure Modes

| Failure | Symptom | Runbook |
|---|---|---|
| DB pool exhaustion | High latency, connection timeouts | RUNBOOK-001 |
| Slow SQL query | High query latency, slow endpoints | RUNBOOK-002 |
| Memory leak (cache) | Memory climbing, eventual OOM | RUNBOOK-003 |
| Fraud service unavailable | Payment creation hangs | RUNBOOK-005 |
| JWT algorithm mismatch | All requests return 401 | RUNBOOK-004 |

---

## Deployment

- **CI/CD**: GitHub Actions → Docker → Kubernetes
- **Deployment strategy**: Rolling update
- **Rollback**: `kubectl rollout undo deployment/payment-api`

---

## Monitoring

- **Metrics**: `api_latency_ms`, `error_rate`, `db_connections`, `memory_percent`
- **Alerts**: latency > 500ms p99, error_rate > 5%, db_connections > 80
- **Logs**: structured JSON via structlog
