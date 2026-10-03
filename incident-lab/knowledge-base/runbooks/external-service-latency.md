# External Service Latency — Runbook

**Document ID:** RUNBOOK-005  
**Service:** payment-api  
**Updated:** 2026-08-22

---

## Overview

The payment-api calls the `fraud-service` synchronously during payment creation.
If the fraud-service becomes slow and no timeout is configured,
all payment creation requests will hang for the duration of the fraud check.

---

## Symptoms

- High API latency on **payment creation** endpoints specifically
- Normal latency on payment **retrieval** endpoints (does not call fraud-service)
- `fraud-service` `response_latency_ms` metric elevated (e.g., 50ms → 5000ms+)
- Database connection count and query latency are NORMAL
- Log entries showing `fraud.check waiting — no timeout configured`

---

## The Critical Difference vs. DB Pool Exhaustion (INC-001 Pattern)

| Signal | External Service Issue | DB Pool Issue |
|--------|----------------------|--------------|
| `db_connections` | NORMAL | AT MAX (100) |
| `db_query_latency_ms` | NORMAL | ELEVATED |
| `fraud-service latency` | ELEVATED | NORMAL |
| Affected endpoints | Payment creation only | All DB endpoints |

This distinction is important. Both cause high API latency, but the root cause is different.

---

## Common Cause: Missing Timeout

`app/fraud_service.py` with `timeout=None`:

```python
# BAD — blocks forever if fraud service is slow
response = await client.post(
    f"{settings.fraud_service_url}/check",
    json=payload,
    timeout=None   # <-- NO TIMEOUT
)

# GOOD — fails fast after 5 seconds
response = await client.post(
    f"{settings.fraud_service_url}/check",
    json=payload,
    timeout=5.0
)
```

When `timeout=None` is set, the HTTP client will wait indefinitely.
If fraud-service has a performance issue, all payment requests are blocked.

---

## Diagnostic Steps

1. Check `fraud-service` `response_latency_ms` — is it elevated?
2. Check `payment-api` `api_latency_ms` — does it track fraud-service latency?
3. Search logs for: `"no timeout configured"`, `"fraud.check waiting"`
4. Check git diff of `app/fraud_service.py` — was `timeout` changed to `None`?
5. Verify database metrics are normal (confirms this is NOT a DB issue)

---

## Remediation

### Immediate
1. Set `FRAUD_SERVICE_TIMEOUT=5` in the payment-api environment variables
2. Restart payment-api (picks up new timeout)

### Short-term
1. Add circuit breaker to fraud service client
2. Implement fallback: if fraud-service unavailable, default to approved=True

---

## Related Runbooks

- RUNBOOK-001: Database Connection Pool
- TROUBLESHOOT-001: High API Latency
