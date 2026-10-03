# High API Latency — Troubleshooting Guide

**Document ID:** TROUBLESHOOT-001  
**Service:** payment-api  
**Updated:** 2026-08-20

---

## Triage Decision Tree

```
High API latency reported
        │
        ├── db_connections at max? ──YES──► See RUNBOOK-001 (Connection Pool)
        │
        ├── db_query_latency_ms spike? ──YES──► See below: Slow SQL section
        │
        ├── fraud-service latency spike? ──YES──► See RUNBOOK-005 (External Dependency)
        │
        ├── memory_percent > 85%? ──YES──► See RUNBOOK-003 (Memory Leak)
        │
        └── All metrics normal? ──YES──► Check authentication, middleware, upstream
```

---

## Slow SQL Queries (N+1 Pattern)

### Symptoms

- `db_query_latency_ms` spikes (e.g., 30ms → 900ms+)
- Only specific endpoints affected (usually history/list endpoints)
- DB connections NOT at max (this distinguishes from connection pool exhaustion)
- CPU on database server may be elevated

### Common Cause: Correlated Subquery / N+1

A common anti-pattern in `repository.py`:

**BAD (N+1 query — causes latency)**:
```python
# This generates a subquery for every row
result = await db.execute(
    select(Payment).where(
        Payment.user_id == select(User.id).where(User.id == user_id).scalar_subquery()
    )
)
```

**GOOD (direct WHERE clause)**:
```python
# Single efficient query
result = await db.execute(
    select(Payment).where(Payment.user_id == user_id)
)
```

### Diagnostic Steps

1. Check `db_query_latency_ms` metric — is it elevated?
2. Check `db_connections` metric — is it normal? (If not, see connection pool runbook)
3. Check git diff for recent changes to `app/repository.py`
4. Look for correlated subqueries, missing WHERE clauses, or ORM N+1 patterns

### Required Evidence to Confirm

- `db_query_latency_ms` spike correlated with deployment
- Code change in `repository.py` introducing inefficient query
- Normal `db_connections` (distinguishes from INC-001 pattern)

---

## External Service Latency

### Symptoms

- API latency spike on payment creation (not retrieval)
- `fraud-service` metric `response_latency_ms` elevated
- Database metrics normal

### Common Cause: Missing Timeout

If `fraud_service.py` has `timeout=None`, payment requests block indefinitely.
Under normal conditions, fraud service responds in ~50ms.
If fraud service degrades, requests wait forever.

See RUNBOOK-005 for details.

---

## Related Runbooks

- RUNBOOK-001: Database Connection Pool
- RUNBOOK-003: Memory Leak
- RUNBOOK-004: Authentication Issues
- RUNBOOK-005: External Service Latency
