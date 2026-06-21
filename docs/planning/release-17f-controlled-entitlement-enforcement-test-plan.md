# Release 17F: Controlled Entitlement Enforcement Test Plan

**Status:** Completed (observability deployed in 17G)
**Priority:** Medium (validates enforcement before broader rollout)
**Risk to Production:** None (planning only; enforcement remains disabled)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Define the safest path to validate enforcement works correctly

---

## 1. Should Enforcement Be Enabled in Production Now?

### Decision: NO — Not Yet

| Reason | Detail |
|--------|--------|
| Only one tenant exists | Cannot test denied-path scenarios without modifying tog_and_dogs or creating a second tenant |
| Professional tier allows all Phase 1 features | Enabling enforcement would change nothing observable for current tenant |
| No denied-path validation | Cannot confirm 403s work correctly without a lower-tier tenant |
| No observability in place | No structured denial logging to detect unexpected blocks |
| Risk-reward ratio | Zero user benefit now; small risk of unexpected failure mode |

**Recommendation:** Add observability/logging first (17G), then enable enforcement (17H/17I) with confidence that unexpected blocks would be immediately visible.

---

## 2. Enforcement Test Strategy Evaluation

| Strategy | Safety | Coverage | Effort | Recommendation |
|----------|--------|----------|--------|----------------|
| Unit/integration tests only (already done in 17D) | ✅ Safest | High for logic | None (done) | ✅ Continue relying on |
| Enable in production (professional tenant) | Medium | Confirms no unexpected 403s | Low (Terraform var change) | ⚠️ After observability |
| Temporary metadata override (change tier to starter) | ❌ Risky | Tests denial path | Medium | ❌ Avoid on production data |
| Second tenant dry-run | ✅ Safe | Full allowed + denied coverage | High | ⏳ Defer to 17J+ |
| Staging/sandbox environment | ✅ Safe | Full coverage | High (doesn't exist) | ❌ No separate environment exists |

### Recommended Sequence

1. **17G:** Add structured denial logging (code-only, enforcement stays off)
2. **17H:** Enable enforcement in production (Terraform var = true)
3. **17I:** Smoke validate that professional tenant sees no 403s; check CloudWatch for denial logs
4. **17J:** Plan second-tenant dry-run for denied-path coverage

---

## 3. What Can Be Verified With tog_and_dogs (Professional Tier)

When enforcement is enabled, the current tenant (`professional`, `active`) should see:

| Gate | Feature/Limit Key | Professional Value | Expected Behavior |
|------|--------------------|--------------------|-------------------|
| Export | `export_enabled` | `True` | ✅ Allowed — no change |
| Google Calendar | `google_calendar_enabled` | `True` | ✅ Allowed — no change |
| Staff limit | `max_staff = 5` | Current count likely 1–3 | ✅ Allowed — under limit |

**What this validates:**
- Entitlement loading from DynamoDB works in production
- Cache behavior works under real Lambda conditions
- `check_feature()` and `check_limit()` return correctly for professional tier
- No unexpected 403s for the active tenant

**What this does NOT validate:**
- Denial path (403 responses) for lower tiers
- Behavior when subscription_status is not `active`
- Behavior at exact limit boundary (5/5 staff)
- Behavior for unknown/missing tiers

---

## 4. Denied-Path Testing Strategy

### Why Not Modify Current Tenant

| Option | Risk | Recommendation |
|--------|------|----------------|
| Change tog_and_dogs `subscription_tier` to `starter` | ❌ Breaks export, calendar, staff limit for real operations | ❌ Never do this |
| Change `subscription_status` to `canceled` | ❌ Could block login/all operations | ❌ Never do this |
| Add 5 test staff to hit limit | Medium | ⚠️ Only with safe cleanup plan |

### Recommended Denied-Path Approach

1. **Unit tests (done):** Already cover denied scenarios with mocked entitlements
2. **Future second-tenant dry-run (17J):** Create a test tenant with `starter` tier, validate 403s work
3. **Boundary test (staff limit):** Only if Matthew approves creating test staff to reach 5/5 — and only after observability is in place

### Staff Limit Boundary Test (If Approved Later)

- Create test staff records up to limit (5)
- Attempt 6th creation → expect 403
- Delete test staff records immediately after
- Only with Matthew's explicit approval
- Prefer doing this after second-tenant dry-run is available

---

## 5. Rollback Plan

### If Enforcement Causes Issues After Enablement

| Step | Action | Time | Risk |
|------|--------|------|------|
| 1 | Set `ENTITLEMENT_ENFORCEMENT_ENABLED=false` in terraform.tfvars | Immediate | None |
| 2 | `terraform plan` → confirm only env var change | 1 min | None |
| 3 | `terraform apply` (saved plan) | 1 min | Low |
| 4 | Verify: Lambda env var updated, all operations resume | 2 min | None |

**Total rollback time:** ~5 minutes

### Rollback Triggers

| Trigger | Action |
|---------|--------|
| Any unexpected 403 in admin operations | Immediately rollback |
| Export returns 403 for professional tenant | Immediately rollback |
| Calendar connection fails with 403 | Immediately rollback |
| Staff creation blocked unexpectedly | Immediately rollback |
| CloudWatch shows EntitlementDenied for tog_and_dogs | Investigate → rollback if real |

### Rollback Safety

- Disabling enforcement restores pre-17H behavior exactly
- No data is lost or modified by enforcement checks
- Rollback is idempotent (can apply multiple times safely)
- No Stripe/Cognito/DynamoDB dependency for rollback

---

## 6. Observability Requirements (Before Enablement)

### What Should Be Logged

| Event | Log Pattern | Level |
|-------|-------------|-------|
| Entitlement check passed | `ENTITLEMENT_ALLOWED: company={company_id}, check={feature/limit}, tier={tier}` | INFO (low volume) |
| Entitlement check denied | `ENTITLEMENT_DENIED: company={company_id}, check={feature/limit}, tier={tier}, reason={msg}` | WARN |
| Entitlement load failed (fail-open) | `ENTITLEMENT_LOAD_ERROR: company={company_id}, error={msg}` | ERROR |
| Enforcement disabled (skipped) | `ENTITLEMENT_SKIPPED: enforcement_disabled` | DEBUG (optional) |

### CloudWatch Metrics/Alarms (After Enablement)

| Metric | Alarm Threshold | Action |
|--------|-----------------|--------|
| `ENTITLEMENT_DENIED` count per 5 min | > 0 for tog_and_dogs | Investigate immediately |
| `ENTITLEMENT_LOAD_ERROR` count per 5 min | > 0 | Investigate (DynamoDB issue?) |

### What NOT to Log

- Do NOT log full entitlement object (may contain billing details)
- Do NOT log request body
- Do NOT log credentials or tokens

---

## 7. Pre-Enablement Checklist

Before setting `ENTITLEMENT_ENFORCEMENT_ENABLED=true`:

| # | Check | Status |
|---|-------|--------|
| 1 | Structured denial logging deployed (17G) | ✅ Done (17G) |
| 2 | Unit tests pass for all enforcement scenarios | ✅ Done (17D) |
| 3 | Integration tests confirm professional tier allowed | ✅ Done (17D) |
| 4 | Production smoke confirms disabled mode works | ✅ Done (17E) |
| 5 | CloudWatch alarm configured for ENTITLEMENT_DENIED | ⏳ |
| 6 | Rollback plan reviewed by Matthew | ⏳ |
| 7 | Terraform saved plan ready (enable var only) | ⏳ |
| 8 | Matthew explicitly approves enablement | ⏳ |

---

## 8. Recommended Next Releases

| Release | Scope | Owner | Effort |
|---------|-------|-------|--------|
| **17G** | Add structured entitlement logging to `check_feature`/`check_limit` (code change, no enablement) | AG | Low |
| **17H** | Terraform plan: set `ENTITLEMENT_ENFORCEMENT_ENABLED=true` + CloudWatch alarm | AG | Low |
| **17I** | Apply + smoke: enable enforcement, verify no 403s for professional tenant, monitor 24h | AG + Matthew | Low |
| **17J** | Second-tenant denied-path dry-run planning | Kiro | Planning |
| **17K** | Phase 2 gates (client limit, booking limit, subscription active) — planning | Kiro | Planning |

### What AG Should Do Next (17G)

1. Add structured log lines to `check_feature()` and `check_limit()` in `entitlement.py`
2. Log pattern: `ENTITLEMENT_ALLOWED` / `ENTITLEMENT_DENIED` with company_id, check type, tier
3. Log only when enforcement is enabled (don't spam logs when disabled)
4. Run tests → confirm logging doesn't break anything
5. Commit + push + deploy via Terraform (Lambda code hash change)
6. Verify logs appear in CloudWatch for manual test requests

---

## 9. What This Document Does NOT Authorize

- ❌ Enabling `ENTITLEMENT_ENFORCEMENT_ENABLED`
- ❌ Code changes
- ❌ Terraform changes
- ❌ DynamoDB writes
- ❌ Modifying tenant metadata
- ❌ Creating test staff/clients
- ❌ Creating a second tenant
- ❌ Stripe/Cognito/Postmark changes
- ❌ Frontend/mobile changes
- ❌ Adding Ryan

This is a planning document. Implementation (17G logging) requires separate AG approval.
