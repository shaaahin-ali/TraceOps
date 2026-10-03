# Memory Leak — Runbook

**Document ID:** RUNBOOK-003  
**Service:** payment-api  
**Updated:** 2026-08-20

---

## Overview

Memory leaks in the payment-api cause `memory_percent` to climb continuously
over time until the process is killed by the OOM (out-of-memory) killer.
This pattern is distinct from a one-time memory spike.

---

## Symptoms

- `memory_percent` metric climbs steadily over hours (e.g., 40% → 95%)
- No single request causing the spike — gradual growth
- OOM kill logged as: `OOM killer triggered — process restarted`
- Cache size grows continuously in log metadata
- Pattern started after a specific deployment

---

## Common Cause: Unbounded In-Memory Cache

If `app/cache.py` uses a plain Python `dict` without eviction policy or size limit,
every unique payment ID is cached permanently. Under production traffic,
this grows without bound.

**BAD (no eviction)**:
```python
# Module-level dict — lives forever
_cache: dict = {}

def cache_payment(payment_id: str, data: dict):
    _cache[payment_id] = data  # grows forever
```

**GOOD (bounded with TTL)**:
```python
from cachetools import TTLCache
_cache = TTLCache(maxsize=1000, ttl=300)  # 5 minute TTL, max 1000 entries
```

---

## Diagnostic Steps

1. Check `memory_percent` time series — is it growing monotonically?
2. When did growth start? Correlate with deployment timestamp
3. Check git diff for `app/cache.py` — was a cache introduced?
4. Check log metadata for `cache_size` field — is it growing?
5. Check for OOM kill events in logs: `"OOM killer triggered"`

---

## Required Evidence to Confirm

- `memory_percent` rising over 4-6 hours
- `cache.py` diff showing unbounded dict with no eviction
- `cache_size` in log metadata growing over time
- OOM event log entry

---

## Remediation

### Immediate
1. Restart the pod (buys time, does not fix the issue)

### Short-term
1. Add TTL and max size to the cache implementation
2. Deploy fix and verify `memory_percent` stabilizes

---

## Warnings

- Do NOT simply restart pods in production without fixing the root cause
- Memory will climb again after restart
- Rollback of the deployment introducing the cache is the safest path
