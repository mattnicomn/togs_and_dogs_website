# Release 17X: Company ID Resolution Hardening Design

**Status:** Design Complete
**Date:** 2026-06-21
**Priority:** Critical (blocks safe second-tenant creation)
**Scope:** Design hardening for `get_current_company_id()` to prevent cross-tenant routing

---

## 1. Current Company ID Resolution Behavior

### Code Path (`src/backend/common/auth.py`)

```python
DEFAULT_COMPANY_ID = os.environ.get("DEFAULT_COMPANY_ID", "tog_and_dogs")

def get_current_company_id(event, claims=None):
    if not claims:
        claims = get_claims(event) if isinstance(event, dict) else {}
    custom_company = claims.get('custom:company_id')
    if custom_company:
        return custom_company
    return DEFAULT_COMPANY_ID
```

### Resolution Priority

1. If JWT contains `custom:company_id` → use that value
2. Otherwise → fallback to `DEFAULT_COMPANY_ID` (env var, defaults to `tog_and_dogs`)

### Where This Is Called

Every handler that needs tenant context calls `get_current_company_id(event)`:
- `admin_handler.py` (30+ locations)
- `review_handler.py`
- `assignment_handler.py`
- `cancellation_handler.py`
- `pet_handler.py`
- `intake_handler.py`
- `google_auth_handler.py`
- `stripe_webhook_handler.py` (resolves from event metadata, not JWT)
- `entitlement.py` checks

### Platform Admin Behavior

Platform admin routes (`/platform/*`) operate across tenants — they read `company_id` from the URL path parameter, not from JWT. The platform admin handler does NOT use `get_current_company_id(event)` for tenant scoping.

---

## 2. The Problem

### Single-Tenant (Current): Safe

All Cognito users belong to tog_and_dogs. The `DEFAULT_COMPANY_ID` fallback is correct because there's only one tenant.

### Multi-Tenant (Future): DANGEROUS

If a second-tenant business owner is created but their Cognito user does NOT have `custom:company_id` set correctly:
- `get_current_company_id()` returns `tog_and_dogs`
- That owner sees/modifies tog_and_dogs data
- Tenant isolation is completely bypassed
- **This is the single most critical multi-tenant security risk.**

---

## 3. Desired Multi-Tenant-Safe Behavior

| Scenario | Current Behavior | Desired Behavior |
|----------|------------------|------------------|
| User has `custom:company_id = tog_and_dogs` | Returns `tog_and_dogs` ✅ | Same ✅ |
| User has `custom:company_id = tenant_alpha` | Returns `tenant_alpha` ✅ | Same ✅ |
| User is MISSING `custom:company_id` (single-tenant legacy) | Returns `tog_and_dogs` ⚠️ | Depends on mode (see below) |
| User is MISSING `custom:company_id` (multi-tenant mode) | Returns `tog_and_dogs` ❌ DANGEROUS | **REJECT or WARN** |

---

## 4. Hardening Options Evaluation

| Option | Safety | Compatibility | Effort | Recommendation |
|--------|--------|---------------|--------|----------------|
| A: Immediately reject missing company_id | ✅ Safest | ❌ Breaks all legacy users | High | ❌ Too disruptive |
| B: `ALLOW_DEFAULT_COMPANY_FALLBACK` env flag | ✅ | ✅ | Low | ⚠️ Acceptable |
| C: `TENANT_RESOLUTION_MODE=single\|multi` | ✅ | ✅ | Low | ✅ **Recommended** |
| D: Allow fallback only for known legacy users | ⚠️ Complex | ✅ | Medium | ❌ Hard to maintain |
| E: Keep fallback + emit warning/metric/alarm | ⚠️ Partial | ✅ | Low | ✅ **Phase 1 step** |
| F: Post-auth Lambda trigger to populate attribute | ✅ | ✅ | Medium | ⏳ Future enhancement |
| G: One-time Cognito attribute audit/migration | ✅ | ✅ | Low (manual) | ✅ **Required step** |

### Recommended Approach: Phased (E → G → C)

---

## 5. Recommended Phased Hardening

### Phase 1: Observable Fallback (17Y Code)

Add structured logging/metrics when the DEFAULT_COMPANY_ID fallback is used:

```python
def get_current_company_id(event, claims=None):
    if not claims:
        claims = get_claims(event) if isinstance(event, dict) else {}
    custom_company = claims.get('custom:company_id')
    if custom_company:
        return custom_company
    
    # FALLBACK PATH — log for visibility
    user_email = claims.get('email', 'unknown')
    print(f"TENANT_RESOLUTION_FALLBACK: user missing custom:company_id, "
          f"falling back to DEFAULT_COMPANY_ID={DEFAULT_COMPANY_ID}")
    return DEFAULT_COMPANY_ID
```

**Why:** This makes every fallback usage visible in CloudWatch without changing behavior. Allows auditing which users need migration.

### Phase 2: Cognito Attribute Audit (17Z Manual)

Matthew reviews Cognito users and sets `custom:company_id = tog_and_dogs` on all existing production users that should belong to tog_and_dogs:

```powershell
aws cognito-idp admin-update-user-attributes ^
  --user-pool-id <POOL_ID> ^
  --username <USERNAME> ^
  --user-attributes Name=custom:company_id,Value=tog_and_dogs ^
  --profile usmissionhero-website-prod
```

After migration: zero fallback occurrences should appear in CloudWatch.

### Phase 3: Strict Mode (Pre-Second-Tenant)

Introduce `TENANT_RESOLUTION_MODE` environment variable:

```python
TENANT_RESOLUTION_MODE = os.environ.get("TENANT_RESOLUTION_MODE", "single")

def get_current_company_id(event, claims=None):
    if not claims:
        claims = get_claims(event) if isinstance(event, dict) else {}
    custom_company = claims.get('custom:company_id')
    if custom_company:
        return custom_company
    
    if TENANT_RESOLUTION_MODE == "multi":
        # STRICT: reject requests without explicit company_id
        raise PermissionError("TENANT_RESOLUTION_FAILED: user missing custom:company_id in multi-tenant mode")
    
    # SINGLE-TENANT COMPATIBILITY: fallback allowed
    print(f"TENANT_RESOLUTION_FALLBACK: using DEFAULT_COMPANY_ID={DEFAULT_COMPANY_ID}")
    return DEFAULT_COMPANY_ID
```

### Phase 4: Enable Strict Mode Before Second Tenant

Set `TENANT_RESOLUTION_MODE=multi` via Terraform ONLY after:
- All existing users have `custom:company_id` set
- Zero fallback occurrences in CloudWatch for 7+ days
- Matthew explicitly approves

---

## 6. Required Tests for AG (17Y Implementation)

### Fallback Logging Tests

| # | Test | Input | Expected |
|---|------|-------|----------|
| 1 | User with custom:company_id → resolves correctly | JWT with `custom:company_id=tog_and_dogs` | Returns `tog_and_dogs`, no fallback log |
| 2 | User with custom:company_id=<other> → resolves to other | JWT with `custom:company_id=test_tenant` | Returns `test_tenant` |
| 3 | User missing company_id (single mode) → fallback + log | No attribute, mode=single | Returns DEFAULT, emits TENANT_RESOLUTION_FALLBACK |
| 4 | User missing company_id (multi mode) → rejected | No attribute, mode=multi | Raises PermissionError |

### Integration Tests

| # | Test | Expected |
|---|------|----------|
| 5 | Admin handler with correct company_id → normal operation | 200 |
| 6 | Admin handler in multi mode, missing company_id → 403 | 403 with clear error |
| 7 | Platform admin routes unaffected by resolution mode | Platform routes use path param, not JWT |
| 8 | `validate_tenant_ownership` still works for both modes | Correct allow/deny |
| 9 | Existing handler tests still pass in single mode | All 526+ pass |

### Edge Cases

| # | Test | Expected |
|---|------|----------|
| 10 | Empty string company_id in JWT → treated as missing | Fallback or reject (mode-dependent) |
| 11 | Null company_id in JWT → treated as missing | Fallback or reject |
| 12 | Platform admin user in multi mode → unaffected | Platform routes don't use get_current_company_id |

---

## 7. Cognito Attribute Audit / Migration Checklist (17Z)

**Matthew manual action** (no usernames/emails in repo):

| # | Step | Notes |
|---|------|-------|
| 1 | List all Cognito users | `aws cognito-idp list-users` |
| 2 | For each user: check if `custom:company_id` attribute exists | Inspect attributes |
| 3 | If missing: set `custom:company_id = tog_and_dogs` | Use `admin-update-user-attributes` |
| 4 | Verify custom attribute is defined on the user pool | May need pool schema update if attribute doesn't exist |
| 5 | After all users updated: monitor CloudWatch for fallback logs | Should drop to zero |
| 6 | Report safe summary (count only, no usernames) | "X users updated, Y already had attribute" |

### Important: Custom Attribute Schema

Cognito custom attributes must be defined on the user pool before they can be set on users. Verify `custom:company_id` exists as a pool attribute:

```powershell
aws cognito-idp describe-user-pool ^
  --user-pool-id <POOL_ID> ^
  --profile usmissionhero-website-prod ^
  --query "UserPool.SchemaAttributes[?Name=='custom:company_id']"
```

If the attribute doesn't exist on the pool schema, it must be added (this is a one-time pool configuration change, not a code change).

---

## 8. Operational Controls

### CloudWatch Metric/Alarm

| Metric | Filter Pattern | Alarm |
|--------|----------------|-------|
| `TenantResolutionFallback` | `"TENANT_RESOLUTION_FALLBACK"` | > 0 in 5 min after migration → investigate |
| `TenantResolutionFailed` (multi mode) | `"TENANT_RESOLUTION_FAILED"` | > 0 → immediate investigation |

### Rollback

| Scenario | Action | Time |
|----------|--------|------|
| Strict mode blocks legitimate users | Set `TENANT_RESOLUTION_MODE=single` in Terraform → apply | ~5 min |
| Fallback logging causes issues | Revert logging code → deploy | ~10 min |
| Cognito attribute migration breaks login | Attribute is additive — removing it restores fallback behavior | Immediate |

---

## 9. Updated Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **17X** | Company ID resolution hardening design (this document) | ✅ Kiro (done) |
| **17Y** | Fallback logging + TENANT_RESOLUTION_MODE implementation (code) | AG |
| **17Z** | Cognito custom:company_id attribute audit/migration (manual Matthew) | Matthew |
| **18A** | Enable strict mode (`TENANT_RESOLUTION_MODE=multi`) after zero fallbacks | AG + Matthew |
| **18B** | Second-tenant creation approval gate | Matthew |
| **18C** | Second-tenant dry run (create test tenant, run isolation checklist) | AG + Matthew |
| **18D** | Second-tenant UI/mobile isolation validation | AG + Matthew |
| **18E** | Ryan testing re-entry review | Kiro |

---

## 10. Is Second-Tenant Creation Approved Now?

**No.** The following must be completed first:
1. 17Y: Implement fallback logging + strict mode toggle
2. 17Z: Matthew migrates all existing users to have `custom:company_id`
3. 18A: Enable strict mode, confirm zero fallbacks
4. 18B: Matthew explicitly approves second-tenant creation

---

## 11. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Modifying `auth.py`
- ❌ Deploying Lambdas
- ❌ Changing Cognito attributes
- ❌ Running Terraform
- ❌ Creating a second tenant
- ❌ Modifying tenant metadata
- ❌ DynamoDB writes
- ❌ Stripe/Postmark changes
- ❌ Frontend/mobile changes
- ❌ Ryan/tester changes

This is a design document. Implementation (17Y) requires separate approval.
