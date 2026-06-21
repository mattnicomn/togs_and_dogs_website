# Release 17N: Platform Admin Access Bootstrap and Authorized API Smoke — Closeout

**Status:** ✅ Completed  
**Type:** Validation / Security Smoke  
**Date:** 2026-06-21  
**Baseline:** Release 17L fully deployed (`ade31e0`), zero Terraform drift confirmed

---

## 1. Context

Release 17L completed the platform backend APIs and API Gateway stage redeployment. This release (17N) validates that:

- Matthew's Cognito user was successfully added to the `platform_admin` group (manual action by Matthew, as planned in the 17M design doc).
- Unauthenticated access remains denied.
- The platform API authorization logic is correct via unit and integration tests.
- Infrastructure remains at zero drift.
- No production tenant metadata was mutated.

---

## 2. Platform Admin Group Membership

Matthew manually added his Cognito user to the `platform_admin` group via the AWS Console or CLI, as specified in the [Release 17M plan](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/planning/release-17m-platform-admin-access-bootstrap-and-ui-readiness.md).

**Safe summary:** 1 expected `platform_admin` user present in user pool `us-east-1_counlsXGU` ✅

> No usernames, emails, session tokens, or auth headers are recorded in this document.

---

## 3. Unauthenticated Access Denial

Unauthenticated `GET /platform/tenants` returns:

```
HTTP/1.1 401 Unauthorized
x-amzn-ErrorType: UnauthorizedException
{"message":"Unauthorized"}
```

✅ API Gateway Cognito Authorizer correctly rejects unauthenticated requests.

---

## 4. Authorized API Smoke Validation

Authorized smoke tests (requiring a live Cognito ID token) are deferred to Matthew's manual validation per the security guardrail against AG handling or exposing production auth tokens. The authorization logic is fully validated at the unit test level — see Section 6.

**Expected results when Matthew runs authenticated smoke:**

| Route | Expected | Test Coverage |
|---|---|---|
| `GET /platform/tenants` | `200` + tenant list with safe fields only | `test_get_tenants_returns_safe_summary_only` |
| `GET /platform/tenants/tog_and_dogs` | `200` + tenant profile, usage counts, entitlement summary | `test_get_tenant_details_success` |
| `GET /platform/audit` | `200` + audit array (empty or recent entries) | `test_get_audit_history_pagination` |
| Non-platform-admin authenticated user | `403 Forbidden` | `test_other_roles_denied`, `test_platform_only_admin_denied_from_normal_admin_endpoints` |

**Manual smoke command (for Matthew's reference):**
```bash
# Obtain ID token via Cognito hosted UI or admin-initiate-auth, then:
curl -H "Authorization: Bearer <ID_TOKEN>" \
  https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/platform/tenants
```

---

## 5. Response Safety Verification

Verified via code review of [platform_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/platform_handler.py):

### `GET /platform/tenants` — safe fields only:
```python
{
  "company_id": ...,
  "display_name": ...,
  "subscription_tier": ...,
  "subscription_status": ...,
  "created_at": ...
}
```

### `GET /platform/tenants/{company_id}` — safe aggregate only:
```python
{
  "company_id": ...,
  "profile": {
    # company_id, display_name, timezone, branding fields, created_at, updated_at, notes, admin_override_until
    # NO client names, emails, addresses, phone numbers, or pet records
  },
  "subscription": { "tier": ..., "status": ... },
  "entitlement_summary": { ... },   # entitlement config only
  "usage_counts": {
    "active_staff": <count only>,   # not names or details
    "active_clients": <count only>,
    "monthly_bookings": <count only>
  }
}
```

**Confirmed absent from all responses:**
- ❌ No client private details (name, email, phone, address)
- ❌ No staff private details
- ❌ No pet records
- ❌ No raw DynamoDB items
- ❌ No Stripe keys or payment secrets
- ❌ No tokens or credentials
- ❌ No webhook secrets

✅ Response safety confirmed.

---

## 6. Non-Platform-Admin Denial Tests

Validated via unit tests in `tests/backend/test_r17l_platform_admin.py`. No real user tokens were used.

| Test | Result |
|---|---|
| `test_other_roles_denied` — Admin, Staff, Client, owner groups all return 403 | ✅ PASSED |
| `test_missing_claims_denied` — No Cognito claims returns 403 | ✅ PASSED |
| `test_platform_only_admin_denied_from_normal_admin_endpoints` — platform_admin cannot access `/admin/*` tenant business routes | ✅ PASSED |

Tenant admin / business owner users are **not** automatically granted access to `/platform/*` routes.

---

## 7. PATCH Validation

**PATCH smoke test: SKIPPED.**

Per scope instructions: "Prefer not to mutate production tenant metadata during this release. Do not perform unless Matthew explicitly approves the exact safe field and value." No explicit approval was given for a PATCH test in this release.

PATCH field validation is covered by unit tests:
- `test_patch_tenant_success` ✅
- `test_patch_tenant_rejects_unsupported_fields` ✅
- `test_patch_tenant_validation_display_name` ✅
- `test_patch_tenant_validation_override_until` ✅

If Matthew wishes to perform a safe PATCH smoke in a future session, the recommended field is `notes` (internal-only, no entitlement enforcement impact).

---

## 8. Test Results

### Targeted Test Suites (verbose)

| Suite | Result |
|---|---|
| `tests/backend/test_r17l_platform_admin.py` | **12/12 passed** |
| `tests/backend/test_r17b_entitlement_enforcement.py` | **9/9 passed** |
| `tests/backend/test_r17d_entitlement_wiring.py` | **15/15 passed** |
| `tests/backend/test_r17g_entitlement_observability.py` | **5/5 passed** |
| **Targeted total** | **41/41 passed** |

### Full Backend Suite

```
454 passed, 78 warnings in 9.31s
```

✅ **454/454 passed** — zero regressions.

Warnings are pre-existing `datetime.utcnow()` deprecation notices unrelated to this release.

---

## 9. Terraform Drift Check

```
No changes. Your infrastructure matches the configuration.
```

✅ Infrastructure is fully converged — zero drift.

---

## 10. Operational Guarantees

- `ENTITLEMENT_ENFORCEMENT_ENABLED` remains `true` for `admin` and `google-auth` Lambdas ✅
- No entitlement behavior changed ✅
- No Phase 2 entitlement gates added ✅
- No production tenant metadata was modified ✅
- No second tenant was created ✅
- No Stripe Dashboard, Postmark, live key, payment, email/SMS, frontend, mobile, EAS, TestFlight, App Store Connect, Ryan/tester, or Apple Beta Review changes occurred ✅
- No users were added to or removed from any Cognito group by AG ✅ (Matthew's manual group assignment is a separate action performed by Matthew, not AG)

---

## 11. Files Changed

| File | Action |
|---|---|
| `docs/release-notes/release-17n-platform-admin-access-bootstrap-and-authorized-api-smoke.md` | ✅ Created (this file) |
| `docs/release-notes/index.md` | ✅ Updated (17N entry added) |

No source code, infrastructure, or test files were modified during 17N.

---

## 12. Next Release

**Release 17O:** Platform Management UI MVP — tenant list page, tenant detail page, edit form (tier, status, notes, override), and audit log panel. Scoped to `/platform-admin/*` routes, Cognito-gated, using the existing design system.
