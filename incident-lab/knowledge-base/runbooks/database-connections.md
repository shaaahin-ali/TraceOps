# Database Connection Pool — Runbook

**Document ID:** RUNBOOK-001  
**Service:** payment-api  
**Version:** 1.3  
**Updated:** 2026-08-15  
**Severity:** HIGH  
**Section:** database troubleshooting

---

## Overview

The payment-api uses SQLAlchemy with asyncpg to maintain a connection pool to PostgreSQL.
Connection pool exhaustion is one of the most common causes of latency spikes in the payment service.

---

## Symptoms

When the connection pool is exhausted, the following symptoms appear:

- **API latency** increases significantly (typically 3-10x normal baseline)
- **Log messages** containing: `QueuePool limit reached`, `connection timeout`, `pool exhausted`
- **DB connections metric** reaches or approaches the PostgreSQL `max_connections` limit (default: 100)
- **Error rate** increases as requests fail with 500/503 status codes
- Latency increase is correlated with a recent deployment or configuration change

---

## Possible Causes

1. **Pool size misconfiguration** — `db_pool_size` set too low or to `None`
2. **Connection leak** — sessions not being properly closed after use
3. **Long-running transactions** — database connections held open for too long
4. **Traffic spike** — legitimate increase in load exceeding pool capacity
5. **Database server overloaded** — PostgreSQL refusing new connections

---

## Diagnostic Steps

### Step 1: Check DB connection count
```sql
SELECT count(*), state 
FROM pg_stat_activity 
WHERE datname = 'payments'
GROUP BY state;
```

Expected normal: 10-30 connections  
Warning: >50 connections  
Critical: approaching `max_connections` (default 100)

### Step 2: Check recent deployments

Look for deployments in the last 24 hours:
- Did any deployment change `database.py` or `config.py`?
- Was `db_pool_size` or `db_max_overflow` modified?
- Was `pool_timeout` reduced?

### Step 3: Check application logs

Search for:
```
"QueuePool limit reached"
"connection timeout"
"pool exhausted"
"database connection acquisition slow"
```

### Step 4: Check metrics

Review the `db_connections` metric time series:
- When did it start rising?
- Is it correlated with a deployment?
- Is it still rising or stable?

---

## Expected Observations When Pool is Exhausted

- `db_connections` metric at or near 100
- Log entries: `ERROR database connection timeout`
- `api_latency_ms` 3-10x normal (typically 400ms-1500ms instead of 100-150ms)
- Error rate > 10% on payment endpoints
- Deployment within the last 30-60 minutes

---

## Remediation

### Immediate

1. Verify pool size configuration in `app/config.py`:
   ```python
   db_pool_size: int = 10    # should NOT be None
   db_max_overflow: int = 20  # should be > 0
   ```

2. If recently deployed: consider rollback of the deployment

3. Restart the payment-api service to reset connections

### Short-term

1. Increase `db_pool_size` if legitimate traffic growth
2. Review `pool_timeout` settings
3. Add connection pool monitoring alert

---

## Warnings

- Do NOT increase `max_connections` in PostgreSQL without also tuning `shared_buffers`
- Rollback requires human approval — do not execute autonomously
- Connection exhaustion can cascade to other services sharing the same PostgreSQL instance

---

## Historical Reference

See postmortem INC-042 for a similar incident in 2025.

---

## Related Runbooks

- RUNBOOK-002: High API Latency
- RUNBOOK-006: Deployment Rollback Procedure
