# Release 17Z: Cognito Company ID Attribute Audit / Manual Closeout

**Status:** Planning — Awaiting Matthew Manual Execution
**Date:** 2026-06-22
**Priority:** High (prerequisite for strict multi-tenant mode)
**Scope:** Manual Cognito audit checklist + safe completion documentation

---

## 1. Purpose

Before `TENANT_RESOLUTION_MODE=multi` can ever be enabled, every active Cognito user that should belong to the `tog_and_dogs` tenant must have the `custom:company_id` attribute explicitly set. This prevents the DEFAULT_COMPANY_ID fallback from being used in multi-tenant mode.

**This is a manual Matthew action — not a code change.**

---

## 2. Manual Cognito Audit Checklist for Matthew

### Step 1: Verify Custom Attribute Exists on Pool

```powershell
aws cognito-idp describe-user-pool ^
  --user-pool-id <POOL_ID> ^
  --profile usmissionhero-website-prod ^
  --query "UserPool.SchemaAttributes[?Name=='custom:company_id']"
```

- If the attribute exists: proceed to Step 2
- If NOT present: the attribute must be added to the pool schema first (one-time pool config change — requires separate approval)

### Step 2: List All Users

```powershell
aws cognito-idp list-users ^
  --user-pool-id <POOL_ID> ^
  --profile usmissionhero-website-prod
```

Review all users in the pool.

### Step 3: For Each User, Check Attributes

For each user, inspect whether `custom:company_id` is present:
- If `custom:company_id = tog_and_dogs` → already correct, no action
- If `custom:company_id` is missing or empty → needs update
- If user is disabled/unused → may skip or disable further

### Step 4: Set Missing Attributes

For users that need `custom:company_id` set:

```powershell
aws cognito-idp admin-update-user-attributes ^
  --user-pool-id <POOL_ID> ^
  --username <USERNAME> ^
  --user-attributes Name=custom:company_id,Value=tog_and_dogs ^
  --profile usmissionhero-website-prod
```

### Step 5: Verify Login After Updates

- Log in as Matthew admin → confirm `/admin` loads
- Log in as Matthew platform_admin → confirm `/platform-admin` loads
- If a staff test account was updated → confirm staff login works

### Step 6: Verify No Fallback Events

After updating all users, check CloudWatch within the next 24 hours:
- Search admin Lambda logs for `TENANT_RESOLUTION_FALLBACK`
- Should show zero new occurrences after audit completion

---

## 3. User Categories (Without Private Details)

| Category | Expected Action | Notes |
|----------|----------------|-------|
| Primary admin / platform admin | Set `custom:company_id = tog_and_dogs` if missing | Must not break login |
| Staff users (active) | Set `custom:company_id = tog_and_dogs` if missing | May need to test login after |
| Staff users (disabled) | Skip or set if low-effort | Not urgent |
| Client users (if any) | Set `custom:company_id = tog_and_dogs` if missing | May not log in regularly |
| Legacy test/dev users | Set or disable | Clean up leftover accounts |
| Platform admin (group membership) | Verify attribute doesn't conflict with platform behavior | Platform routes use path param, not JWT company_id |

---

## 4. Safe Completion Summary Format

After Matthew completes the audit, report ONLY the following safe summary:

```
Cognito Company ID Audit Summary:
- Users reviewed: [COUNT]
- Users already had correct custom:company_id: [COUNT]
- Users updated (attribute added): [COUNT]
- Users skipped (disabled/unused): [COUNT]
- Admin login verified: Pass/Fail
- Platform_admin login verified: Pass/Fail
- /admin dashboard works: Pass/Fail
- /platform-admin works: Pass/Fail
- TENANT_RESOLUTION_FALLBACK occurrences after audit: [COUNT, target: 0]
```

### What Must NOT Be in Summary

- ❌ Usernames
- ❌ Email addresses
- ❌ User pool ID
- ❌ Raw `list-users` output
- ❌ Screenshots
- ❌ JWT tokens or claims
- ❌ Passwords

---

## 5. CloudWatch Verification Checklist

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | `TENANT_RESOLUTION_FALLBACK` count after audit | CloudWatch filter on admin/google-auth log groups | 0 new occurrences |
| 2 | `TENANT_RESOLUTION_FAILED` count | CloudWatch filter | 0 (multi mode not enabled) |
| 3 | No unexpected 403 errors | Admin operations work normally | Normal behavior |
| 4 | Alarm not firing | Check alarm state | OK |

### Do NOT

- Do not intentionally trigger production auth failures to test
- Do not log or copy raw JWT claims
- Do not share CloudWatch output containing user identifiers

---

## 6. Strict-Mode Enablement Gate

`TENANT_RESOLUTION_MODE=multi` must NOT be enabled until ALL of the following are confirmed:

| # | Criterion | Status |
|---|-----------|--------|
| 1 | Every active tenant user has `custom:company_id` set | ⏳ Pending audit |
| 2 | `TENANT_RESOLUTION_FALLBACK` metric is zero for 7+ days after audit | ⏳ Pending observation |
| 3 | Matthew admin login works with attribute set | ⏳ Pending verification |
| 4 | Staff/client login works with attribute set | ⏳ Pending verification |
| 5 | Rollback plan reviewed (set mode=single if issues) | ✅ Documented (17X) |
| 6 | Matthew explicitly approves enabling multi mode | ⏳ Pending |

**If any criterion fails, do NOT enable multi mode.**

---

## 7. Rollback Notes

| Scenario | Action |
|----------|--------|
| User attribute set incorrectly | Fix via `admin-update-user-attributes` (immediate) |
| User can't log in after attribute change | Attribute is additive — shouldn't break login; investigate JWT claims |
| Fallback still occurring | Some user still missing attribute — identify and fix |
| Need to undo all changes | Attributes can't be "removed" easily, but can be set to empty or correct value |

### Production Remains Safe

- `TENANT_RESOLUTION_MODE=single` remains active throughout 17Z
- The fallback still works even if attributes are partially migrated
- No user is locked out by attribute changes alone
- Strict mode is a future, separate approval gate (18A)

---

## 8. Important: Pool Schema Prerequisite

If `custom:company_id` does not exist as a defined attribute on the Cognito user pool schema:

1. It must be added before users can have the attribute set
2. Adding a custom attribute to an existing pool is a one-time operation
3. It does NOT require recreating the pool
4. It does NOT affect existing users
5. Command: `aws cognito-idp add-custom-attributes --user-pool-id <POOL_ID> --custom-attributes Name=company_id,AttributeDataType=String,Mutable=true`
6. This is a safe, non-destructive operation but should be documented and approved

If Matthew discovers the attribute already exists on the pool (from earlier setup), skip this step.

---

## 9. Recommended Next Steps

| Step | Actor | Action |
|------|-------|--------|
| 1 | Matthew | Check if `custom:company_id` exists on pool schema |
| 2 | Matthew | If missing, add custom attribute (one-time) |
| 3 | Matthew | List users, audit attributes |
| 4 | Matthew | Set `custom:company_id = tog_and_dogs` on affected users |
| 5 | Matthew | Verify own login (admin + platform_admin) |
| 6 | Matthew | Report safe completion summary |
| 7 | Kiro | Document closeout in 18A |
| 8 | All | Monitor CloudWatch for 7 days |
| 9 | Matthew | Approve strict mode enablement (18A) when ready |

---

## 10. Recommended Release Sequence After 17Z

| Release | Scope | Owner |
|---------|-------|-------|
| **17Z** | Cognito audit plan (this document) | ✅ Kiro (done) |
| **18A** | Matthew executes audit + closeout + strict-mode gate | Matthew + Kiro |
| **18B** | Enable `TENANT_RESOLUTION_MODE=multi` (Terraform) | AG + Matthew |
| **18C** | Second-tenant creation approval gate | Matthew |
| **18D** | Second-tenant dry run | AG + Matthew |
| **18E** | Second-tenant isolation validation | AG + Matthew |
| **18F** | Ryan testing re-entry review | Kiro |

---

## 11. What This Document Does NOT Authorize

- ❌ Modifying Cognito user attributes
- ❌ Adding pool schema attributes
- ❌ Enabling multi mode
- ❌ Creating users
- ❌ Deleting users
- ❌ Changing groups
- ❌ Code changes
- ❌ Terraform/AWS changes
- ❌ DynamoDB writes
- ❌ Creating a second tenant
- ❌ Stripe/Postmark changes
- ❌ Frontend/mobile changes
- ❌ Ryan/tester changes

This is a planning/checklist document. Matthew executes manually at his discretion.
