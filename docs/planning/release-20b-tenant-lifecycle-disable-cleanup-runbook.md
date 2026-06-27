# Release 20B: Tenant Lifecycle Disable/Cleanup Runbook

**Status:** Planning
**Date:** 2026-06-27
**Priority:** Medium (required before further tenant creation or external testing)
**Scope:** Define tenant states, disable behavior, validation checklist, and cleanup policy

---

## 1. Tenant Lifecycle States

| State | `subscription_status` | Access | Reversible? | Use Case |
|-------|----------------------|--------|-------------|----------|
| **Active** | `active` | Full access per tier | N/A | Normal operation |
| **Trialing** | `trialing` | Full access (trial period) | → active or → canceled | New tenant trial |
| **Past Due** | `past_due` | Grace → read-only → blocked | → active (on payment) | Failed payment |
| **Disabled** | `disabled` | **Blocked** — all login denied | ✅ → active | Admin manually disabled |
| **Canceled** | `canceled` | **Blocked** — login denied | ✅ → active (resubscribe) | Owner canceled subscription |
| **Archived** | N/A (future) | Blocked + data flagged for retention review | ⚠️ Complex | Long-term inactive |
| **Deleted/Purged** | N/A (future) | Data removed | ❌ Irreversible | End of retention period |

### Current Implementation

| State | Supported? | Method |
|-------|-----------|--------|
| Active | ✅ | Default on creation |
| Disabled | ✅ | Platform Admin PATCH `subscription_status = disabled` |
| Canceled | ✅ | Platform Admin PATCH or Stripe webhook (future) |
| Archived | ❌ | Not implemented — requires separate design |
| Deleted/Purged | ❌ | Not implemented — requires policy + legal review |

---

## 2. What "Disabled" Means

When `subscription_status = disabled`:

| Behavior | Expected |
|----------|----------|
| Owner login | ❌ Blocked (entitlement check returns `is_blocked = true`) |
| Staff login | ❌ Blocked (same entitlement check) |
| Client access | ❌ Blocked |
| Booking intake (public form) | ⚠️ Request may be created but no notification sent; owner can't act on it |
| Google Calendar sync | ❌ Skipped (no active access) |
| Notifications/email | ❌ Skipped (no active operations) |
| Platform Admin visibility | ✅ Tenant still appears (with "Disabled" badge) |
| Platform Admin edit | ✅ Can re-enable by setting status = active |
| DynamoDB data | ✅ Retained (not deleted) |
| Cognito user | ✅ Remains (can additionally disable in Cognito for defense-in-depth) |
| Audit trail | ✅ Platform audit records retained |

### Important: Entitlement Check Must Block Login

The `get_tenant_entitlement()` → `TenantEntitlement.is_blocked` property already returns `True` for `disabled` status. Any handler checking entitlement before proceeding will deny access.

**However:** Login itself (Cognito authentication) is NOT gated by entitlement. The user can still authenticate to Cognito but their first API call to a business endpoint will return 403.

**Defense-in-depth (optional):** Also disable the Cognito user account to prevent even token issuance.

---

## 3. Safest Disable Approach for test_tenant_alpha

### Method: Platform Admin UI

1. Matthew logs into `/platform-admin`
2. Navigates to test_tenant_alpha tenant detail
3. Clicks "Edit Subscription"
4. Changes `subscription_status` from `active` to `disabled`
5. Confirms via modal
6. PLATFORM_AUDIT record is automatically created

### What This Does NOT Do

- Does not delete the TENANT metadata record
- Does not delete the Cognito user
- Does not delete DynamoDB data (if any existed)
- Does not affect tog_and_dogs in any way
- Does not delete Google Calendar tokens (none exist for test_tenant_alpha)
- Does not affect Stripe (no subscription exists)

### Reversibility

To restore: same flow in reverse — set `subscription_status = active` via Platform Admin.

---

## 4. Validation Checklist (For Future 20C Controlled Disable)

### Pre-Disable

| # | Check | Expected |
|---|-------|----------|
| 1 | test_tenant_alpha status is `active` | Confirmed in Platform Admin |
| 2 | Owner can log in and see /admin | Login works, empty dashboard |
| 3 | tog_and_dogs is unaffected | Normal admin operations |
| 4 | Platform Admin shows both tenants | Correct |

### During Disable (Matthew Executes)

| # | Action | Method |
|---|--------|--------|
| 5 | Set test_tenant_alpha `subscription_status = disabled` | Platform Admin PATCH |
| 6 | Confirm PLATFORM_AUDIT record created | Platform Admin audit log |

### Post-Disable

| # | Check | Expected |
|---|-------|----------|
| 7 | Owner login → first API call blocked | 403 or "subscription inactive" |
| 8 | Platform Admin still shows test_tenant_alpha | ✅ With "Disabled" badge |
| 9 | tog_and_dogs is unaffected | Normal operations |
| 10 | Tenant-resolution alarms remain OK | Zero fallback/failed |
| 11 | No data deleted | TENANT metadata still exists |
| 12 | Audit shows disable action | PLATFORM_AUDIT entry |

### Post-Restore (Optional)

| # | Check | Expected |
|---|-------|----------|
| 13 | Set status back to `active` via Platform Admin | PATCH succeeds |
| 14 | Owner login works again | /admin loads |
| 15 | No data loss | Tenant intact |

---

## 5. Cleanup/Deletion Policy

### Deferred — NOT Recommended for Implementation Now

Actual data deletion/purge requires:

| Prerequisite | Status |
|--------------|--------|
| Legal/retention policy defined | ❌ Not defined |
| Privacy policy covers data deletion | ⚠️ Draft mentions 90-day retention placeholder |
| Attorney/accountant review | ❌ Not completed |
| Matthew explicitly approves deletion | ❌ Not given |
| Deletion mechanism built | ❌ Not implemented |

### Data Categories That Would Need Cleanup (If Eventually Approved)

| Category | Storage | Deletion Complexity |
|----------|---------|---------------------|
| Tenant metadata (`TENANT#`) | DynamoDB | Low (single record) |
| Platform audit records | DynamoDB | Low (query + batch delete) |
| Cognito user accounts | Cognito | Low (admin-delete-user) |
| Client/staff/pet records (`COMPANY#`) | DynamoDB | Medium (query all + batch delete) |
| Booking/request/job records (`REQ#`, `JOB#`) | DynamoDB | Medium (scattered PKs) |
| Google Calendar tokens | Secrets Manager | Low (if per-tenant key exists) |
| Stripe customer/subscription | Stripe API | Low (cancel + archive in Stripe) |
| Notification ledger (`NOTIF#`) | DynamoDB | Medium (query + batch) |
| USAGE counters (`USAGE#`) | DynamoDB | Low (single record per month) |
| BILLING events (`BILLING#`) | DynamoDB | Low (query + batch) |

### Recommendation

**Use `disabled` state as the primary "deactivation" mechanism.** Data stays intact, access is blocked, tenant is invisible to its own users but visible to Platform Admin. Actual deletion is a future milestone requiring legal review.

---

## 6. Rollback / Restore

### From Disabled → Active

| Step | Action | Method |
|------|--------|--------|
| 1 | Open Platform Admin → tenant detail | Browser |
| 2 | Click Edit → set `subscription_status = active` | UI form |
| 3 | Confirm | Modal |
| 4 | Verify owner can log in | Manual login test |
| 5 | Verify no data loss | Check Platform Admin counts |

### From Disabled → Full Removal (NOT RECOMMENDED NOW)

Would require:
- Delete TENANT metadata
- Delete or disable all Cognito users for that company_id
- Delete all COMPANY# records
- Delete all REQ#/JOB# records with matching company_id
- Verify no orphan records remain
- **Requires separate planning release + Matthew explicit approval**

---

## 7. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **20B** | Disable/cleanup runbook (this document) | ✅ Kiro (done) |
| **20C** | Controlled tenant disable validation (Matthew disables test_tenant_alpha) | Matthew + AG |
| **20D** | Tenant restore validation (re-enable to active) | Matthew + AG |
| **20E** | Owner onboarding simplification plan | Kiro |
| **20F** | Stripe sandbox architecture decision | Kiro |
| **20G** | External tester readiness checklist | Kiro |

---

## 8. What This Document Does NOT Authorize

- ❌ Disabling any tenant
- ❌ Modifying tenant metadata
- ❌ Deleting data
- ❌ Creating/modifying Cognito users
- ❌ Code changes or deployment
- ❌ Terraform/AWS changes
- ❌ Stripe/payment actions
- ❌ Google Calendar changes
- ❌ Mobile/TestFlight/App Store changes
- ❌ Ryan/tester changes
- ❌ DynamoDB writes

This is a runbook/planning document. Controlled disable validation (20C) requires Matthew's explicit approval.
