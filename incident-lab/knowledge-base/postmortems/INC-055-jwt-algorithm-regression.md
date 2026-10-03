# Postmortem: INC-055 — Payment API JWT Algorithm Regression

**Incident ID:** INC-055  
**Date:** 2025-09-10  
**Duration:** 23 minutes  
**Severity:** CRITICAL  
**Service:** payment-api  
**Author:** Sarah Chen (SRE)

---

## Summary

All authenticated API endpoints began returning 401 Unauthorized immediately
after deploying version 1.9.0. The root cause was a change in `auth.py`
that altered the JWT verification algorithm from HS256 to RS256, causing
all existing tokens to fail validation.

---

## Timeline

| Time (UTC) | Event |
|---|---|
| 16:45 | DEP-099 deployed: version 1.9.0 |
| 16:46 | First 401 errors appear in logs |
| 16:47 | Alert: error_rate > 50% |
| 16:48 | Alert: error_rate = 100% |
| 16:50 | On-call investigation begins |
| 16:55 | Root cause identified: algorithms=[\"RS256\"] in auth.py |
| 17:00 | Rollback of DEP-099 approved |
| 17:08 | Rollback complete, authentication restored |

---

## Root Cause

Commit `f91a22` in `auth.py` changed the JWT decode call:

```python
# BEFORE (correct)
payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])

# AFTER commit f91a22 (broken — RS256 mismatch)
payload = jwt.decode(token, settings.jwt_secret, algorithms=["RS256"])
```

Since all tokens are issued with HS256 (using `jwt.encode(..., algorithm="HS256")`),
changing the allowed algorithms to RS256 causes every token to fail verification
with `InvalidSignatureError: Signature verification failed`.

---

## Detection

- `error_rate` metric reached 1.0 within 60 seconds of deployment
- Log query for `auth.validation_failed` returned hundreds of entries per minute
- Health check endpoint (unauthenticated) remained healthy — confirming auth-layer issue

---

## What Worked Well

- 1-minute metric alert caught the issue within 3 minutes
- Authentication failures were immediately distinguishable from service outages
  (health check was still returning 200)
- Rollback procedure was fast and well-rehearsed

---

## Action Items

1. [DONE] Rollback DEP-099
2. [DONE] Add unit test: verify JWT encode → decode round-trip in CI
3. [PENDING] Add startup assertion: `settings.jwt_algorithm` must be in supported list

---

## Resolution

Rollback of DEP-099 restored HS256 verification.
100% of users regained access within 8 minutes of issue detection.

---

## Notes for Future Investigators

If you see:
- 100% error rate on authenticated endpoints
- `auth.validation_failed` logs with `Signature verification failed`
- Unauthenticated endpoints working normally
- Recent `auth.py` diff

→ Check the `algorithms` parameter in `jwt.decode()`.
