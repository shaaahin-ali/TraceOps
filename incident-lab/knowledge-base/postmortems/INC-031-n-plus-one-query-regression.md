# Postmortem: INC-031 — Payment API N+1 Query Performance Regression

**Incident ID:** INC-031  
**Date:** 2025-03-22  
**Duration:** 2 hours 15 minutes  
**Severity:** HIGH  
**Service:** payment-api  
**Author:** Alex Kumar (Backend Engineer)

---

## Summary

The payment history endpoint `/payments/history` degraded from 28ms to 1200ms
after a repository refactoring change was merged. The change introduced a
correlated subquery in `repository.py` that caused N+1 database queries
for every payment history request.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:00 | DEP-041 deployed: version 1.5.4, commit b44e12 |
| 14:18 | First reports of slow payment history page |
| 14:25 | Alert: db_query_latency_ms > 500ms |
| 14:30 | On-call SRE begins investigation |
| 14:45 | Root cause identified: correlated subquery in repository.py |
| 15:00 | Fix commit prepared and reviewed |
| 16:15 | Fix deployed and latency returned to normal |

---

## Root Cause

Commit `b44e12` modified `repository.py` to use a subquery for user_id filtering:

```python
# BEFORE (fast)
.where(Payment.user_id == user_id)

# AFTER (slow — introduced in b44e12)
.where(Payment.user_id == select(User.id).where(User.id == user_id).scalar_subquery())
```

The correlated subquery causes PostgreSQL to execute an inner SELECT for
every row in the payments table, resulting in N+1 query behavior.

---

## Impact

- Payment history page: 28ms → 1200ms average response time
- Affected all users attempting to view payment history
- Database CPU utilization: 15% → 65%

---

## Key Distinction

This incident is characterized by:
- HIGH `db_query_latency_ms` (not `db_connections`)
- Only history/list endpoints affected (not payment creation)
- Database connections WITHIN NORMAL RANGE

This distinguishes it from connection pool exhaustion (INC-019, INC-042)
where `db_connections` reaches the PostgreSQL limit.

---

## Action Items

1. [DONE] Revert correlated subquery to direct WHERE clause
2. [DONE] Add query performance test for payment history endpoint  
3. [PENDING] Add EXPLAIN ANALYZE to CI pipeline for critical queries

---

## Resolution

Fix commit `c88e91` reverted the subquery to a direct WHERE clause.
Latency returned to baseline within 3 minutes of deployment.
