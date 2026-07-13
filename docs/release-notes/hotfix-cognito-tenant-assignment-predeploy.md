# Hotfix: Cognito Tenant Assignment on User Provisioning (Pre-Deploy)

**Date:** 2026-07-12
**Status:** Pre-Deploy (awaiting Matthew deployment approval)
**Type:** Backend security fix
**Scope:** Ensure `custom:company_id` is set on all Cognito identity provisioning paths

---

## 1. User-Visible Failure

**Symptom:** `TENANT_RESOLUTION_FAILED: user missing custom:company_id in multi-tenant mode`

**Affected user:** brearockwell@gmail.com (test account with deleted/recreated profile)

**Impact:** Authenticated requests fail because the Cognito identity token lacks `custom:company_id`, which is required for tenant resolution in strict multi-tenant mode.

---

## 2. Root Cause

The `admin_create_user` calls in staff and client onboarding only set `email` and `email_verified` as UserAttributes. They did NOT include `custom:company_id`. This means:

- Newly onboarded users received Cognito accounts without tenant assignment
- The existing production users work only because they were manually backfilled during Release 18C
- Deleting a profile and recreating/relinking it could reuse a Cognito identity whose `custom:company_id` was never set or was cleared

Additionally, the `link-cognito` flow did not verify or repair the tenant attribute on the target Cognito user.

---

## 3. Affected Provisioning Paths (Before Fix)

| Path | Missing `custom:company_id`? | Fixed? |
|------|:---:|:---:|
| POST /admin/staff/onboard (admin_create_user) | ✅ Missing | ✅ Fixed |
| POST /admin/clients/onboard (admin_create_user) | ✅ Missing | ✅ Fixed |
| POST /admin/staff/{id}/link-cognito | ✅ Not verified/repaired | ✅ Fixed |
| POST /admin/clients/{id}/link-cognito | ✅ Not verified/repaired | ✅ Fixed |
| Resend invite (admin_set_user_password) | N/A (doesn't create user) | No change needed |
| Profile update (admin_update_user_attributes) | N/A (syncs name/phone only) | No change needed |
| Profile delete (delete DynamoDB only) | N/A (doesn't touch Cognito) | Documented |

---

## 4. Implementation

### A. Central Helper (`common/auth.py`)

Added two functions:

**`build_tenant_user_attribute(company_id)`**
- Returns `{'Name': 'custom:company_id', 'Value': company_id}`
- Rejects empty/None/whitespace company_id with ValueError
- Used by admin_create_user calls

**`ensure_cognito_tenant_attribute(cognito_client, user_pool_id, username, company_id)`**
- Reads the user's current `custom:company_id`
- If missing: sets it to the trusted company_id
- If matching: no-op
- If different non-empty value: raises PermissionError (cross-tenant conflict)
- Used by link-cognito flows

### B. Staff and Client Onboarding

Both `admin_create_user` calls now include `build_tenant_user_attribute(company_id)` in UserAttributes. The `company_id` is derived exclusively from `get_current_company_id(event)` — the trusted server-side authenticated claim. Browser payload cannot override it.

### C. Link-Cognito Flows

Tenant validation now occurs **before** any group assignment or profile mutation. The corrected order is:

1. Resolve trusted `company_id` from the authenticated event
2. Locate the target Cognito user (`admin_get_user`)
3. Protected-account guardrails check
4. **`ensure_cognito_tenant_attribute`** — validate/repair tenant
5. If conflicting: return 403 immediately (no group, no profile link)
6. If Cognito failure: return 500 immediately (no group, no profile link)
7. Only after tenant validation succeeds: `admin_add_user_to_group`
8. Only after group assignment: persist profile linkage to DynamoDB

Cross-tenant denial leaves **no partial state** — no group membership added, no `cognito_sub` written to the profile, no DynamoDB update. Error messages do not expose the conflicting tenant identifier.

---

## 5. Cross-Tenant Mismatch Protection

If a Cognito user already has a different `custom:company_id` and an admin attempts to link them, the operation is denied with a generic tenant-conflict message. The response does NOT reveal the existing tenant value.

This prevents:
- Silent tenant reassignment through link flows
- Identity theft between tenants
- Accidental cross-tenant profile binding
- Partial linkage state (group added but profile not linked)

---

## 6. Profile Deletion vs Cognito Deletion

| Action | Effect |
|--------|--------|
| `delete_profile` | Deletes DynamoDB record only. Cognito user remains. |
| `delete_cognito` | Disables and deletes the Cognito user. Updates profile status. |

Deleting only a profile leaves an orphaned Cognito identity. If that identity is later relinked, `ensure_cognito_tenant_attribute` will verify/repair the tenant assignment.

---

## 7. Public Intake Finding

The public `/requests` POST route calls `get_current_company_id(event)` which, for unauthenticated requests in multi-tenant mode, raises `TENANT_RESOLUTION_FAILED`. This is a **separate known issue** — the public intake form depends on the Cognito authorizer providing claims. When the authorizer is absent (unauthenticated), there is no trusted tenant context.

**This is NOT addressed by this hotfix.** It requires a separate architectural decision for trusted public-route tenant mapping (hostname-based, API key, or route-based). Documented as a deferred blocker.

---

## 8. Brea Remediation Plan (Deferred)

**Do NOT execute without Matthew's explicit approval.**

Idempotent one-user remediation procedure:
1. Confirm brearockwell@gmail.com exists in Cognito user pool
2. Confirm `custom:company_id` is absent or empty
3. If a different tenant value exists: STOP — escalate
4. Set `custom:company_id = tog_and_dogs` using `admin_update_user_attributes`
5. Require full logout and new login (fresh token will contain the claim)
6. Confirm the DynamoDB client profile is linked to the same Cognito sub
7. Verify authenticated request submission works

**Required command (not to be run without approval):**
```
aws cognito-idp admin-update-user-attributes \
  --user-pool-id <POOL_ID> \
  --username brearockwell@gmail.com \
  --user-attributes Name=custom:company_id,Value=tog_and_dogs \
  --profile usmissionhero-website-prod
```

---

## 9. Tests

21 new helper/unit tests in `tests/backend/test_tenant_assignment_hotfix.py`:
- 5 tests: `build_tenant_user_attribute` helper (valid, strips, empty, none, whitespace)
- 4 tests: `ensure_cognito_tenant_attribute` helper (sets missing, no-op correct, denies cross-tenant, empty raises)
- 2 tests: Staff onboarding code verification (helper present, correct value)
- 1 test: Client onboarding code verification (helper present ≥2 times)
- 4 tests: Link-cognito protection (code uses helper, repairs, denies cross-tenant, preserves)
- 4 tests: Tenant resolution (valid, missing denied, empty denied, unknown resolves)
- 1 test: Public intake (unauthenticated denied in multi mode)

8 handler-level integration tests in `tests/backend/test_tenant_assignment_handler_integration.py`:
- 2 tests: Staff onboard (tenant attribute sent, body cannot override)
- 1 test: Client onboard (tenant attribute sent)
- 4 tests: Link-cognito (repairs missing, denies cross-tenant without group/profile, succeeds with matching, Cognito failure aborts without group/profile)
- 1 test: Token refresh behavior documentation

All 29 new tests pass. Existing 65 tenant/isolation/identity tests pass without regression (94 total combined).

---

## 10. What Was NOT Changed

- ❌ No AWS deployment
- ❌ No Terraform apply
- ❌ No Cognito write to production users
- ❌ No DynamoDB changes
- ❌ No production data modification
- ❌ No tenant resolution mode changes
- ❌ No Stripe changes
- ❌ No Google Calendar changes
- ❌ No mobile/TestFlight/App Store changes
- ❌ No tenant creation
- ❌ No Ryan-testing changes
- ❌ The tenant resolver itself was not weakened (missing claims still denied in multi mode)
