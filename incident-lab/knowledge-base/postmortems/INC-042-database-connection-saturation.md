# Postmortem: INC-042 — Payment API Database Connection Saturation

**Incident ID:** INC-042  
**Date:** 2025-11-14  
**Duration:** 47 minutes  
**Severity:** HIGH  
**Service:** payment-api  
**Author:** Sarah Chen (SRE)

---

## Summary

The payment-api experienced a significant latency spike that lasted 47 minutes.
API p99 latency increased from 135ms to 720ms.
The root cause was database connection pool exhaustion caused by a configuration
change that removed the connection pool size limit.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 14:30 | DEP-089 deployed: version 1.8.2, commit c44a91 |
| 14:45 | First db_connections warning (65 connections) |
| 14:52 | db_connections reached 100 (PostgreSQL max_connections) |
| 14:53 | Connection timeout errors begin in logs |
| 14:55 | Alert triggered: p99 latency > 500ms |
| 14:58 | SRE Sarah Chen begins investigation |
| 15:05 | Root cause identified: pool_size=None in config change |
| 15:10 | Rollback of DEP-089 approved and initiated |
| 15:17 | Rollback complete, connections begin recovering |

---

## Root Cause

Commit `c44a91` modified `database.py` to "improve connection handling".
The change set `pool_size=None` in the `create_async_engine()` call.

When `pool_size=None` is passed to SQLAlchemy's `create_async_engine`, 
the engine uses a `StaticPool` or unbounded pool depending on the dialect.
With asyncpg, this caused every incoming request to acquire a new connection 
without limit. Under normal traffic (~50 req/s), the connection count rapidly
climbed from 30 to 100, at which point PostgreSQL began refusing new connections.

---

## Symptoms

- **API latency**: 135ms → 720ms (p99)
- **DB connections**: 30 → 100 (max)
- **Log entries**: `QueuePool limit reached`, `database connection timeout`
- **Error rate**: 0.2% → 14%

---

## What Worked Well

- Monitoring alert fired within 2 minutes of metric threshold breach
- Runbook RUNBOOK-001 provided correct diagnostic steps
- Rollback procedure was well-documented

---

## What Could Be Improved

- The code review for c44a91 did not catch the `pool_size=None` change
- No automated test validates pool configuration

---

## Action Items

1. [DONE] Rollback DEP-089
2. [DONE] Add pool_size validation in startup check
3. [PENDING] Add automated test: assert pool_size is not None
4. [PENDING] Add `db_connections` alert threshold at 70 connections

---

## Resolution

Rollback of DEP-089 restored the previous configuration with `pool_size=10`.
Connection count returned to normal within 7 minutes of rollback completion.

---

## Similar Incidents

This is the third connection pool incident in the payment-api history.
Previous incidents: INC-019 (2024-08), INC-031 (2025-03).
All three had the same root cause: pool_size misconfiguration in config.py.
