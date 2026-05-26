# Release 6H: Configurable Protected Admin Accounts

## Overview
Moves hardcoded protected admin/owner email and Cognito sub lists into configurable environment variables managed via Terraform. Adds guardrails against identity hijacking, unauthorized linking, and accidental profile creation using protected identities.

## Status: ✅ Deployed & Production Validated (2026-05-22)

## Deployment
- **Terraform:** 0 added, 9 changed, 0 destroyed (Lambda env var + code updates)
- **Final plan:** No changes — infrastructure fully aligned
- **Frontend:** S3 sync + CloudFront invalidation `I3ILYWDT8G4DT6LYSTBYP7YEJM`

## Changes

### Phase 1: Backend Configuration + Guardrails

**New shared module:** `src/backend/common/protected_accounts.py`
- `get_protected_emails()` — reads from `PROTECTED_ADMIN_EMAILS` env var + hardcoded fallback defaults
- `get_protected_subs()` — reads from `PROTECTED_ADMIN_SUBS` env var + hardcoded fallback defaults
- `is_protected_email(email)` / `is_protected_sub(sub)` / `is_protected_profile(profile)`
- Fallback defaults always included — core accounts can never be unprotected by misconfiguration

**Terraform env vars** (in `locals.tf`, distributed to all Lambdas):
```hcl
PROTECTED_ADMIN_EMAILS = "admin@toganddogs.com,mbn@usmissionhero.com,support@usmissionhero.com"
PROTECTED_ADMIN_SUBS   = "74b86488-1011-7029-bb6d-dad984e1463c"
```

**Guardrails added to `admin_handler.py`:**
- POST staff/client creation: blocks protected email usage (403)
- POST staff/client onboard: blocks protected email usage (403)
- PATCH staff/client: blocks changing email/sub to protected values on non-protected profiles (403)
- Link-cognito: blocks linking protected Cognito identity to non-protected profiles (403)
- Existing destructive action blocking preserved (delete, disable, unlink, role change)

**Updated `client_profile.py`:**
- `SKIPPED_PROTECTED_EMAIL` now uses shared module instead of hardcoded list

### Phase 2: Frontend Cleanup

- Removed hardcoded `PROTECTED_SUBS` and `PROTECTED_EMAILS` from `AdminDashboard.jsx` and `UserProfile.jsx`
- Frontend now uses backend-provided `is_protected` field on staff profiles
- Backend staff list merge enriches every profile with `is_protected: true/false`
- Protected badge and action hiding still work — driven by backend data

## Production Validation Results

| Check | Result |
|-------|--------|
| `admin@toganddogs.com` returns `is_protected=True` | ✅ |
| `mbn@usmissionhero.com` returns `is_protected=True` | ✅ |
| Normal profiles return `is_protected=False` | ✅ |
| POST creation with protected email blocked (403) | ✅ |
| PATCH hijacking with protected email blocked (403) | ✅ |
| Link-cognito with protected identity blocked (403) | ✅ |
| No persistent production test data | ✅ |
| Terraform state aligned (no changes) | ✅ |
| Frontend protected badge displays correctly | ✅ |
| Destructive actions hidden for protected profiles | ✅ |

## Files Changed
- `src/backend/common/protected_accounts.py` (NEW)
- `src/backend/handlers/admin_handler.py`
- `src/backend/common/client_profile.py`
- `infra/prod/locals.tf`
- `web/src/components/AdminDashboard.jsx`
- `web/src/components/UserProfile.jsx`
- `tests/backend/test_r6h_protected_config.py` (NEW)

## Rollback
Remove `PROTECTED_ADMIN_EMAILS` and `PROTECTED_ADMIN_SUBS` from `locals.tf` → `terraform apply`. Backend falls back to hardcoded defaults — no behavior change for existing protected accounts.
