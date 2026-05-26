# Release 6H: Configurable Protected Admin Emails — Plan

## Status: ✅ DEPLOYED & PRODUCTION VALIDATED (2026-05-22)

**Deployment:** Terraform 9 Lambdas updated + Frontend S3/CloudFront
**Validation:** All guardrails confirmed — POST/PATCH/link-cognito blocking, is_protected field, fallback defaults
**Final terraform plan:** No changes — infrastructure fully aligned

## Objective
Move the hardcoded protected admin/owner email and Cognito sub lists into configuration so protected accounts can be managed without editing backend or frontend code.

## Current State: Where Protected Lists Are Hardcoded

### Backend (3 locations)

**1. `src/backend/handlers/admin_handler.py` (lines 39-40)**
```python
PROTECTED_SUBS = ["74b86488-1011-7029-bb6d-dad984e1463c"]
PROTECTED_USERNAMES = ["admin@toganddogs.com", "mbn@usmissionhero.com"]
```
Used by `is_protected_profile()` to block: DELETE, disable, unlink, delete_profile, delete_cognito, role/email change on protected accounts.

**2. `src/backend/common/client_profile.py` (line 61)**
```python
PROTECTED_EMAILS = ["admin@toganddogs.com", "mbn@usmissionhero.com", "support@usmissionhero.com"]
```
Used to skip auto-creating client profiles for protected admin emails during CUSTOMER_INTAKE approval.

**3. `src/backend/common/auth.py` (line ~60)**
```python
if user_email in ['mattnicomn10@gmail.com', 'support@toganddogs.usmissionhero.com']:
    return 'owner'
```
Hardcoded owner email fallback (separate from protected list but related).

### Frontend (2 locations)

**4. `web/src/components/AdminDashboard.jsx` (lines 16-17)**
```javascript
const PROTECTED_SUBS = ["74b86488-1011-7029-bb6d-dad984e1463c"];
const PROTECTED_EMAILS = ["admin@toganddogs.com", "mbn@usmissionhero.com"];
```
Used by `isProtectedProfile()` to hide destructive actions in the UI.

**5. `web/src/components/UserProfile.jsx` (lines 58-59)**
```javascript
const PROTECTED_SUBS = ["74b86488-1011-7029-bb6d-dad984e1463c"];
const PROTECTED_EMAILS = ["admin@toganddogs.com"];
```
Used to show "PROTECTED" badge on the user profile dropdown.

### Inconsistencies Found
| Location | Emails Protected |
|----------|-----------------|
| admin_handler.py | admin@toganddogs.com, mbn@usmissionhero.com |
| client_profile.py | admin@toganddogs.com, mbn@usmissionhero.com, support@usmissionhero.com |
| AdminDashboard.jsx | admin@toganddogs.com, mbn@usmissionhero.com |
| UserProfile.jsx | admin@toganddogs.com (missing mbn@) |
| auth.py (owner fallback) | mattnicomn10@gmail.com, support@toganddogs.usmissionhero.com |

The lists are not consistent across locations. This is a maintenance risk.

---

## Configuration Source Recommendation

### Option A: Environment Variable (Recommended for Phase 1)
```hcl
# In infra/prod/locals.tf
PROTECTED_ADMIN_EMAILS = "admin@toganddogs.com,mbn@usmissionhero.com,support@usmissionhero.com"
PROTECTED_ADMIN_SUBS   = "74b86488-1011-7029-bb6d-dad984e1463c"
```

**Advantages:**
- Simple, no new infrastructure
- Managed via Terraform (version-controlled, auditable)
- Available to all Lambdas via environment variables
- Easy to add/remove emails without code deploy (just `terraform apply`)
- Consistent with existing notification config pattern (`NOTIFICATION_ADMIN_EMAIL`, etc.)

**Disadvantages:**
- Frontend cannot read Lambda env vars directly — needs a different approach for UI
- Env var size limit (4KB total per Lambda) — not a concern for a short email list

### Option B: DynamoDB Config Record
Store in DynamoDB as `PK: CONFIG#protected_accounts`, `SK: METADATA`.

**Advantages:** Runtime-editable without deploy. Frontend could fetch via API.
**Disadvantages:** Adds a DynamoDB read to every protection check. More complex. Overkill for a short list.

### Option C: Secrets Manager
**Disadvantages:** Expensive for frequent reads. Designed for secrets, not config.

### Recommendation
**Phase 1: Environment variable (backend) + API endpoint (frontend)**
- Backend reads `PROTECTED_ADMIN_EMAILS` and `PROTECTED_ADMIN_SUBS` from env vars
- Frontend gets the list from the backend via the existing staff/admin API response (backend enriches the response with `is_protected` flag — already done)
- Frontend removes hardcoded lists and relies on backend `is_protected` field

---

## Implementation Plan

### Phase 1: Backend Configuration + Guardrails (~3-4 hours)

#### 1A. Shared Protected Accounts Module

**Create `src/backend/common/protected_accounts.py`:**
```python
import os

# Hardcoded fallback defaults — used when env vars are missing.
# These MUST always be protected regardless of configuration.
_FALLBACK_EMAILS = ["admin@toganddogs.com", "mbn@usmissionhero.com", "support@usmissionhero.com"]
_FALLBACK_SUBS = ["74b86488-1011-7029-bb6d-dad984e1463c"]

def get_protected_emails():
    raw = os.environ.get('PROTECTED_ADMIN_EMAILS', '')
    configured = [e.strip().lower() for e in raw.split(',') if e.strip()]
    # Always include fallback defaults even if env var is set
    combined = set(configured) | set(_FALLBACK_EMAILS)
    return list(combined)

def get_protected_subs():
    raw = os.environ.get('PROTECTED_ADMIN_SUBS', '')
    configured = [s.strip() for s in raw.split(',') if s.strip()]
    combined = set(configured) | set(_FALLBACK_SUBS)
    return list(combined)

def is_protected_email(email):
    return (email or '').lower().strip() in get_protected_emails()

def is_protected_sub(sub):
    return (sub or '') in get_protected_subs()

def is_protected_profile(profile):
    if not profile:
        return False
    if is_protected_sub(profile.get('cognito_sub')):
        return True
    if is_protected_email(profile.get('email')):
        return True
    return False
```

#### 1B. Terraform Environment Variables

**Add to `locals.tf` notification_env_vars (or a new protected_env_vars block):**
```hcl
PROTECTED_ADMIN_EMAILS = "admin@toganddogs.com,mbn@usmissionhero.com,support@usmissionhero.com"
PROTECTED_ADMIN_SUBS   = "74b86488-1011-7029-bb6d-dad984e1463c"
```

**Add env vars to ALL Lambdas that may use protected account logic:**
- `intake` — imports `client_profile.py` which checks protected emails
- `admin` — uses `is_protected_profile()` for destructive action blocking
- `review` — imports `client_profile.py` via auto-profile on approval
- `assign` — may cascade to handlers that check protection
- `cancellation` — may cascade to handlers that check protection

#### 1C. Update `admin_handler.py`

1. Replace hardcoded `PROTECTED_SUBS` and `PROTECTED_USERNAMES` with imports from `common.protected_accounts`
2. Replace `is_protected_profile()` local function with the shared module version

#### 1D. Update `client_profile.py`

1. Replace hardcoded `PROTECTED_EMAILS` list with `is_protected_email()` from shared module

#### 1E. Link-Cognito Guardrails (NEW)

**In `admin_handler.py` link-cognito endpoint:**
- Before linking a Cognito user to a staff/client profile, check if the Cognito username/email/sub being linked is a protected value
- If the TARGET profile is NOT already protected, block the link with: "Cannot link a protected admin account to this profile."
- This prevents a non-protected profile from gaining protected status by linking to a protected Cognito identity

```python
# In POST /admin/staff/{id}/link-cognito and /admin/clients/{id}/link-cognito:
from common.protected_accounts import is_protected_email, is_protected_sub

# Check if the Cognito user being linked is protected
if is_protected_email(username) or is_protected_sub(cognito_sub):
    if not is_protected_profile(user_profile):
        return error(403, "Cannot link a protected admin account to a non-protected profile.", event)
```

#### 1F. PATCH/Update Hijacking Prevention (NEW)

**In `admin_handler.py` PATCH endpoint for staff and clients:**
- Before allowing email, cognito_sub, or cognito_username updates, check if the NEW value is a protected value
- If the profile is NOT already protected, block the update: "Cannot assign a protected email/sub to this profile."
- This prevents promotion hijacking where someone changes a normal profile's email to a protected admin email

```python
# In PATCH /admin/staff/{id} and PATCH /admin/clients/{id}:
if 'email' in body:
    new_email = body['email'].strip().lower()
    if is_protected_email(new_email) and not is_protected_profile(staff_profile):
        return error(403, "Cannot assign a protected admin email to a non-protected profile.", event)

if 'cognito_sub' in body:
    new_sub = body['cognito_sub'].strip()
    if is_protected_sub(new_sub) and not is_protected_profile(staff_profile):
        return error(403, "Cannot assign a protected admin sub to a non-protected profile.", event)
```

#### 1G. POST Creation Protection (NEW)

**In `admin_handler.py` POST /admin/staff and POST /admin/clients (both profile-only and onboard flows):**
- Before creating a new staff or client profile, check if the provided email or cognito_sub matches the protected accounts list
- Block creation with: "Cannot create a standard profile using a protected account identity."
- This prevents creating a new non-protected profile that uses a protected admin's email/sub, which could cause identity confusion or bypass protection checks

```python
# In POST /admin/staff, POST /admin/staff/onboard, POST /admin/clients, POST /admin/clients/onboard:
from common.protected_accounts import is_protected_email, is_protected_sub

email = body.get('email', '').strip().lower()
if is_protected_email(email):
    return error(403, "Cannot create a standard profile using a protected account identity.", event)
```

This applies to:
- `POST /admin/staff` (profile-only creation)
- `POST /admin/staff/onboard` (Cognito + profile creation)
- `POST /admin/clients` (profile-only creation, if applicable)
- `POST /admin/clients/onboard` (Cognito + profile creation)

### Phase 2: Frontend Cleanup (~1 hour)

1. **Remove hardcoded `PROTECTED_SUBS` and `PROTECTED_EMAILS`** from `AdminDashboard.jsx` and `UserProfile.jsx`
2. **Rely on backend-provided `is_protected` field** in staff/client profile API responses
3. The backend staff list merge already calls `is_protected_profile()` — ensure the result is included as `is_protected: true/false` in the response
4. Frontend `isProtectedProfile()` becomes: `return !!staff.is_protected`
5. Frontend is display-only — all security enforcement remains on the backend

### Phase 3: Auth.py Owner Fallback (Deferred)

The `auth.py` hardcoded owner email fallback (`mattnicomn10@gmail.com`) is a separate concern. It's a Cognito group fallback for when group membership is missing, not a protection list. Defer to a future release.

---

## Migration / Backward Compatibility

1. **Hardcoded fallback defaults are ALWAYS included** — even if env var is set, the fallback emails/subs are merged in. This ensures core admin accounts can never be accidentally unprotected by misconfiguring the env var.
2. **No data migration needed** — this is config-only
3. **Rollback:** Remove env vars from Terraform → code uses fallback defaults only → identical to current behavior
2. **No data migration needed** — this is config-only
3. **Rollback:** Remove env vars → code falls back to hardcoded defaults → no behavior change

---

## Backend Tests Needed

| Test | Validates |
|------|-----------|
| Protected email from env var blocks destructive actions | Config is read correctly |
| Protected sub from env var blocks destructive actions | Config is read correctly |
| Empty env var falls back to hardcoded defaults | Backward compatibility — core accounts always protected |
| Configured env var PLUS fallback defaults are both active | Merge behavior correct |
| New email added to env var is immediately protected | Dynamic config works |
| Non-protected email is not blocked | No false positives |
| `client_profile.py` uses shared module — SKIPPED_PROTECTED_EMAIL preserved | Consistency with Release 6E |
| Link-cognito: protected Cognito user cannot be linked to non-protected profile | Prevents privilege escalation |
| Link-cognito: protected Cognito user CAN be linked to already-protected profile | Normal admin linking works |
| PATCH: changing email to protected value on non-protected profile is blocked | Prevents hijacking |
| PATCH: changing cognito_sub to protected value on non-protected profile is blocked | Prevents hijacking |
| PATCH: protected profile can update its own email (no self-block) | Normal admin self-edit works |
| POST: creating staff profile with protected email is blocked | Prevents identity confusion |
| POST: creating client profile with protected email is blocked | Prevents identity confusion |
| POST: creating staff/client with non-protected email succeeds | No false positives on creation |
| Frontend `isProtectedProfile()` uses backend `is_protected` field | Display-only, no hardcoded list |

---

## Deployment Impact

- **Terraform:** Adds 2 env vars (`PROTECTED_ADMIN_EMAILS`, `PROTECTED_ADMIN_SUBS`) to ALL relevant Lambdas: intake, admin, review, assign, cancellation
- **Lambda code:** New shared module `protected_accounts.py` + updates to `admin_handler.py` and `client_profile.py`
- **Frontend:** Removes hardcoded lists, relies on backend `is_protected` field
- **No DynamoDB changes**
- **No API Gateway changes**
- **No IAM changes**
- **No new infrastructure**

### Rollback
Remove the env vars from `locals.tf` → `terraform apply`. Backend falls back to hardcoded defaults (always-protected core accounts). No behavior change for existing protected accounts.

---

## Frontend UI (Deferred)

A future release could add an admin UI to manage the protected list (add/remove emails). This would require:
- A DynamoDB config record (upgrade from env var)
- An admin API endpoint to read/write the list
- A settings panel in the Admin Dashboard

**Not needed for Phase 1** — Terraform-managed env vars are sufficient for the current team size.

---

## Risks / Blockers

| Risk | Mitigation |
|------|-----------|
| Env var missing on deploy → protection lost | Fall back to hardcoded defaults if env var is empty |
| Frontend still has hardcoded list after Phase 1 | Phase 2 removes it; Phase 1 backend is the security boundary |
| Adding too many emails exceeds env var size | Extremely unlikely for admin protection list |

---

## Files Likely Involved

| File | Change |
|------|--------|
| `src/backend/common/protected_accounts.py` | NEW — shared config reader |
| `src/backend/handlers/admin_handler.py` | Replace hardcoded lists with shared module |
| `src/backend/common/client_profile.py` | Replace hardcoded list with shared module |
| `infra/prod/locals.tf` | Add `PROTECTED_ADMIN_EMAILS`, `PROTECTED_ADMIN_SUBS` |
| `infra/prod/main.tf` | Add env vars to relevant Lambdas |
| `web/src/components/AdminDashboard.jsx` | Phase 2: remove hardcoded lists |
| `web/src/components/UserProfile.jsx` | Phase 2: remove hardcoded lists |
| `tests/backend/test_r6h_protected_config.py` | NEW — tests for configurable protection |

## Estimated Effort

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1: Backend config + guardrails | ~3-4 hours | Very Low |
| Phase 2: Frontend cleanup | ~1 hour | Low |
| Phase 3: Auth.py fallback | Deferred | — |
| **Total** | **~4-5 hours** | |
