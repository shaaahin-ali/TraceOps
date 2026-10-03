# Authentication Failures — Runbook

**Document ID:** RUNBOOK-004  
**Service:** payment-api  
**Updated:** 2026-08-25

---

## Overview

JWT authentication failures cause all protected endpoints to return `401 Unauthorized`.
Public endpoints (e.g., `/health`) continue to work normally.
The most common cause is a JWT algorithm mismatch between token creation and validation.

---

## Symptoms

- All authenticated API requests return `401 Unauthorized`
- `auth.validation_failed` log entries with `"Signature verification failed"`
- `error_rate` metric spikes to 1.0 (100% of authenticated requests fail)
- Public endpoints (health check) work normally
- Users report they cannot access any payment data
- Issue started immediately after a deployment

---

## The JWT Algorithm Mismatch

The payment-api uses HMAC-SHA256 (HS256) for JWT signing.
If the `algorithms` list in `jwt.decode()` is changed to `["RS256"]`,
all tokens created with HS256 will fail signature verification.

**BAD (algorithm mismatch)**:
```python
# Token was CREATED with HS256 (see create_access_token)
# But decode now requires RS256 — mismatch causes all tokens to fail
payload = jwt.decode(
    token,
    settings.jwt_secret,
    algorithms=["RS256"]  # <-- WRONG, should be ["HS256"]
)
```

**GOOD (matching algorithm)**:
```python
payload = jwt.decode(
    token,
    settings.jwt_secret,
    algorithms=["HS256"]  # <-- matches token creation
)
```

---

## Diagnostic Steps

1. Check `error_rate` metric — is it at or near 1.0 (100%)?
2. Search logs for: `"auth.validation_failed"`, `"Signature verification failed"`, `"401"`
3. Verify public endpoints work (e.g., GET /health → 200)
4. Check recent deployment for changes to `app/auth.py`
5. In the diff, look for changes to the `algorithms` parameter in `jwt.decode()`
6. Confirm tokens are still being ISSUED correctly (issue is in validation, not creation)

---

## Required Evidence to Confirm

- `error_rate` = 1.0 on authenticated endpoints
- Log entries: `auth.validation_failed` with `Signature verification failed`
- `algorithms=["RS256"]` (or other non-HS256) in `auth.py` diff
- Deployment within last 30-60 minutes

---

## Remediation

### Immediate
1. Roll back the deployment that changed `auth.py`

### Short-term
1. Add automated test that validates JWT encode/decode round-trip
2. Add startup check that verifies JWT configuration

---

## Warnings

- This incident is typically 100% impact — ALL authenticated users are locked out
- Resolution requires deployment rollback (human approval required)
- Do NOT manually issue new tokens — the validation is broken, not the issuance

---

## Severity

**CRITICAL** — Complete authentication failure locks out 100% of users.
Escalate immediately. Target resolution time: <15 minutes.
