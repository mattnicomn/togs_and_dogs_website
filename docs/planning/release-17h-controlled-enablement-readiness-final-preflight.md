# Release 17H: Controlled Enablement Readiness — Final Preflight

**Status:** Planning / Readiness Checklist
**Date:** 2026-06-20
**Priority:** High (final gate before enforcement enablement)
**Scope:** Define exact enablement path, smoke checklist, observability, rollback — do NOT enable

---

## 1. Should Enforcement Be Enabled Now (During 17H)?

### Decision: NO

17H is **preflight only**. Enforcement enablement is a separate **17I release** requiring Matthew's explicit approval.

| Reason | Detail |
|--------|--------|
| Separation of concerns | Planning and enablement are distinct approval gates |
| Matthew approval required | Flipping a production behavior flag needs explicit go-ahead |
| Observability readiness | Confirm CloudWatch alarms exist before flipping |
| Rollback confidence | Matthew should review rollback plan before go-live |

---

## 2. Exact 17I Enablement Path

### Terraform Change

In `infra/prod/main.tf`, update the environment blocks for **admin** and **google_auth** Lambdas:

```hcl
# Current:
ENTITLEMENT_ENFORCEMENT_ENABLED = "false"

# 17I target:
ENTITLEMENT_ENFORCEMENT_ENABLED = "true"
```

### Enablement Order

| Option | Approach | Recommendation |
|--------|----------|----------------|
| A: Both Lambdas simultaneously | Single Terraform apply | ✅ Recommended — simpler, consistent state |
| B: Staged (admin first, then google-auth) | Two separate applies | ❌ Unnecessary complexity — both affect same tenant |

**Decision:** Enable both simultaneously in one Terraform apply.

### Expected Terraform Plan

```
Plan: 0 to add, 2 to change, 0 to destroy.

~ aws_lambda_function.admin
    ~ environment.variables.ENTITLEMENT_ENFORCEMENT_ENABLED: "false" → "true"

~ aws_lambda_function.google_auth
    ~ environment.variables.ENTITLEMENT_ENFORCEMENT_ENABLED: "false" → "true"
```

No other resources should change. If the plan shows additional changes (code hash, other vars), investigate before applying.

### What 17I Does NOT Require

- ❌ No frontend/mobile changes
- ❌ No Stripe/live payment involvement
- ❌ No DynamoDB writes
- ❌ No Cognito changes
- ❌ No new Lambda functions or API routes
- ❌ No code deployment (code already deployed in 17E/17G)

---

## 3. 17I Smoke Validation Checklist

After enabling enforcement, validate within 15 minutes:

| # | Check | Method | Expected | Fail Action |
|---|-------|--------|----------|-------------|
| 1 | Admin dashboard loads | Browser → /admin | ✅ Normal load | Rollback |
| 2 | Request list displays | Admin dashboard | ✅ Shows bookings | Rollback |
| 3 | Export/download backup works | Click export or call GET /admin/export-data | ✅ 200 + data returned | Rollback |
| 4 | Google Calendar status check | GET /admin/auth/status | ✅ Returns connection state | Rollback |
| 5 | Google Calendar OAuth initiation | GET /admin/auth/google | ✅ Returns OAuth URL (or already connected) | Rollback |
| 6 | Staff list loads | GET /admin/staff | ✅ Staff displayed | Rollback |
| 7 | Staff creation available (if under limit) | POST /admin/staff/onboard with test data (only if approved) | ✅ 200 or skip | Rollback if 403 |
| 8 | No 403 entitlement errors in admin operations | Normal admin workflow | ✅ Zero unexpected 403s | Rollback |
| 9 | Client portal unaffected | Client login (if tested) | ✅ Normal | Rollback |
| 10 | Mobile unaffected | Mobile app (if tested) | ✅ Normal (no mobile enforcement) | Rollback |

### Pass Criteria

- All checks 1–8 pass
- Zero `ENTITLEMENT_DENIED` log entries for `tog_and_dogs` in first 15 minutes
- No user-facing errors

### Monitoring Period

After initial smoke, monitor passively for **24 hours** before declaring 17I complete:
- Check CloudWatch every 4–6 hours for unexpected denial logs
- If any ENTITLEMENT_DENIED appears for tog_and_dogs → investigate immediately

---

## 4. Observability Checks

### CloudWatch Log Groups

| Lambda | Log Group |
|--------|-----------|
| admin | `/aws/lambda/togs-and-dogs-prod-admin` |
| google-auth | `/aws/lambda/togs-and-dogs-prod-google-auth` |

### Search/Filter Patterns

```
# Find all entitlement events:
"ENTITLEMENT_"

# Find allowed events (expected for professional tier):
"ENTITLEMENT_ALLOWED"

# Find denied events (should be ZERO for tog_and_dogs):
"ENTITLEMENT_DENIED"

# Find load errors (should be ZERO):
"ENTITLEMENT_LOAD_ERROR"

# Filter by company:
"tog_and_dogs" "ENTITLEMENT_DENIED"
```

### CloudWatch Metric Filter/Alarm Recommendation

**Should alarms be created before 17I?** Yes — prefer having the alarm ready before flipping enforcement.

| Metric | Filter Pattern | Alarm |
|--------|----------------|-------|
| `EntitlementDenied` | `"ENTITLEMENT_DENIED"` | > 0 in 5 minutes → alert Matthew |
| `EntitlementLoadError` | `"ENTITLEMENT_LOAD_ERROR"` | > 0 in 5 minutes → alert Matthew |

**Implementation option:**
- AG adds metric filters + alarms as the first step of 17I (before flipping the var)
- Or: include as a small separate 17H.1 release
- Either approach is safe — the important thing is alarms exist before enforcement goes live

### Alarm Notification Target

Use existing `ryan_alerts_topic_arn` (SNS) or Matthew's alert email — whichever is already configured for CloudWatch alarms in the observability module.

---

## 5. Rollback Plan

### Trigger Conditions

| Condition | Action |
|-----------|--------|
| Any ENTITLEMENT_DENIED for tog_and_dogs | Investigate; rollback if not expected |
| Export returns 403 | Immediate rollback |
| Calendar OAuth returns 403 | Immediate rollback |
| Staff creation returns 403 (under limit) | Immediate rollback |
| Multiple users report issues | Immediate rollback |

### Rollback Steps

| Step | Action | Time |
|------|--------|------|
| 1 | Update `terraform.tfvars` or `main.tf`: `ENTITLEMENT_ENFORCEMENT_ENABLED = "false"` | Immediate |
| 2 | `terraform plan -out=rollback-17i.tfplan` — confirm only env var change | 1 min |
| 3 | `terraform apply rollback-17i.tfplan` | 1 min |
| 4 | Verify Lambda env var is `false` via AWS CLI | 1 min |
| 5 | Retry the failed operation — confirm it works | 1 min |

**Total rollback time:** ~5 minutes

### Rollback Safety Properties

- No data is lost or modified by enforcement checks
- Disabling enforcement restores exact pre-17I behavior
- Rollback is idempotent (safe to apply multiple times)
- No Stripe/Cognito/DynamoDB dependency
- No tenant metadata changes needed
- No frontend/mobile deployment needed for rollback

---

## 6. Denied-Path Testing Recommendation

### Do NOT Do During 17I

- ❌ Do not modify tog_and_dogs `subscription_tier`
- ❌ Do not modify `subscription_status`
- ❌ Do not create fake staff to hit the 5/5 boundary
- ❌ Do not create a second tenant

### Rationale

- Unit tests (17D, 422 passing) already validate denied-path logic
- Production testing with professional tier only validates the allowed path
- Denied-path production validation requires a separate test tenant (17J)

### Future Plan (17J)

- Create a clearly-marked test tenant with `starter` tier
- Validate: export returns 403, calendar connect returns 403, 2nd staff creation returns 403
- Clean up test tenant after validation
- Requires Matthew approval and careful isolation

---

## 7. Pre-17I Readiness Checklist (For Matthew Review)

| # | Item | Status | Required Before 17I? |
|---|------|--------|---------------------|
| 1 | Structured logging deployed (17G) | ✅ Done | Yes |
| 2 | Unit tests pass for all enforcement scenarios | ✅ Done (442/442) | Yes |
| 3 | Production smoke with enforcement disabled passes | ✅ Done (17E) | Yes |
| 4 | CloudWatch metric filter for ENTITLEMENT_DENIED exists | ⏳ Needed | Yes (add in first step of 17I) |
| 5 | Rollback plan reviewed | ✅ This document | Yes |
| 6 | Matthew explicitly approves 17I enablement | ⏳ Pending | Yes |
| 7 | Terraform saved plan shows only 2 env var changes | ⏳ Verify at 17I time | Yes |
| 8 | No other Terraform changes pending | ⏳ Verify at 17I time | Yes |

---

## 8. Recommended Next Releases

| Release | Scope | Owner |
|---------|-------|-------|
| **17I** | Phase 1 enforcement enablement: add CloudWatch alarm → flip var → smoke → monitor 24h | AG (with Matthew approval) |
| **17J** | Second-tenant denied-path dry-run planning | Kiro |
| **17K** | Phase 2 gates planning (client limit, booking limit, subscription active check) | Kiro |

### What AG Should Do for 17I

1. Add CloudWatch metric filter + alarm for `ENTITLEMENT_DENIED` (if not already present)
2. `terraform plan` — confirm only 2 Lambda env var changes (+ possible alarm addition)
3. Report plan to Matthew for approval
4. On approval: `terraform apply`
5. Run smoke checklist (Section 3)
6. Monitor CloudWatch for 24h
7. Report results → closeout 17I

---

## 9. What This Document Does NOT Authorize

- ❌ Enabling `ENTITLEMENT_ENFORCEMENT_ENABLED`
- ❌ Running Terraform apply
- ❌ Adding CloudWatch alarms/filters
- ❌ Code changes
- ❌ DynamoDB writes
- ❌ Modifying tenant metadata
- ❌ Creating a second tenant
- ❌ Stripe/Cognito/Postmark changes
- ❌ Frontend/mobile changes
- ❌ Adding Ryan

This is a preflight/readiness document. Enablement (17I) requires Matthew's separate explicit approval.
