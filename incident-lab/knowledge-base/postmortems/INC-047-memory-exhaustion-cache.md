# Postmortem: INC-047 — Payment API Memory Exhaustion via Cache

**Incident ID:** INC-047  
**Date:** 2025-06-03  
**Duration:** 6 hours (gradual degradation)  
**Severity:** HIGH  
**Service:** payment-api  
**Author:** Alex Kumar (Backend Engineer)

---

## Summary

The payment-api pods were OOM-killed starting 6 hours after deployment of
version 1.7.2. The root cause was an unbounded in-memory cache introduced
in `cache.py` that stored payment data in a module-level dictionary with
no size limit or eviction policy.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 09:00 | DEP-071 deployed: version 1.7.2 |
| 09:30 | Memory at 45% (normal) |
| 11:00 | Memory at 62% (elevated) |
| 13:00 | Memory at 81% (alert fires) |
| 14:30 | Memory at 95% |
| 15:00 | First OOM kill — pod restarts |
| 15:07 | Pod restarts, memory climbs again |
| 15:30 | Root cause identified |

---

## Root Cause

DEP-071 introduced `app/cache.py` with an unbounded cache:

```python
# BAD — grows forever
_payment_cache: dict = {}

def cache_payment(payment_id: str, data: dict):
    _payment_cache[payment_id] = data
```

Under normal traffic (~500 unique payment IDs/hour), the cache grew at
~2MB/hour. After 6 hours, 12,000 payment records were cached in memory,
causing memory to climb from 40% to 95%.

---

## Key Diagnostic Pattern

The distinguishing signature of this incident:
- **Memory grows steadily over hours** (not sudden spike)
- Growth rate is proportional to traffic volume
- Memory does NOT drop between requests
- OOM kill causes restart — but memory climbs again immediately
- `cache_size` field in log metadata grows over time

---

## Action Items

1. [DONE] Restart all pods
2. [DONE] Replace `dict` with `TTLCache(maxsize=1000, ttl=300)`
3. [DONE] Add memory monitoring alert at 70%
4. [DONE] Add cache size metric emission

---

## Resolution

Fix replaced the unbounded dict with a bounded TTL cache.
Memory stabilized at 42% after the fix deployment.
