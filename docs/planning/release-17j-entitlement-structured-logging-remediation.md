# Release 17J: Entitlement Structured Logging Remediation

**Status:** Completed
**Priority:** High (observability is required before broader SaaS testing)
**Risk to Production:** Low (logging change only; entitlement behavior unchanged)
**Terraform Required:** Yes (Lambda code hash update via terraform apply)
**Code Changes:** Yes (logger configuration in entitlement.py)
**Scope:** Fix structured logging so ENTITLEMENT_ALLOWED/DENIED appear in CloudWatch

---

## 1. Problem

Structured entitlement log events (`ENTITLEMENT_ALLOWED`, `ENTITLEMENT_DENIED`) are not appearing in CloudWatch production logs despite enforcement being active and working correctly.

**Root cause:** The module-level logger in `src/backend/common/entitlement.py` is not explicitly configured to emit at INFO level in the AWS Lambda environment. Lambda's default logging may suppress module loggers that haven't had their level set.

**Impact:**
- CloudWatch metric filters for `ENTITLEMENT_DENIED` cannot trigger (no matching log lines)
- Alarm `togs-and-dogs-prod-entitlement-denied` is effectively blind
- Cannot verify enforcement behavior via logs
- Cannot detect unexpected denials for the current tenant

---

## 2. Priority Confirmation

| Prerequisite | Status |
|--------------|--------|
| Fix logging BEFORE second-tenant denied-path dry run | ✅ Required |
| Fix logging BEFORE declaring entitlement enforcement fully validated | ✅ Required |
| Fix logging BEFORE Phase 2 gates | ✅ Required |

**Do not proceed to broader SaaS testing or second-tenant work until CloudWatch observability is confirmed working.**

---

## 3. Implementation Scope for AG

### What to Change

**File:** `src/backend/common/entitlement.py`

**Fix:** Ensure the logger is explicitly configured to emit at INFO level in Lambda:

```python
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
```

Or use `print()` statements instead of `logger.info()` (Lambda reliably captures `print()` to CloudWatch without logger configuration). Choose whichever pattern is consistent with the rest of the codebase.

### Existing Pattern Check

Review how other modules in `src/backend/common/` and `src/backend/handlers/` emit logs:
- If they use `print()` → use `print()` for entitlement logs
- If they use a configured `logging.getLogger()` → match that configuration

### What NOT to Change

- ❌ Do not change tier limits
- ❌ Do not change entitlement enforcement behavior
- ❌ Do not change tenant metadata
- ❌ Do not add Phase 2 gates
- ❌ Do not change frontend/mobile
- ❌ Do not touch Stripe/live payments
- ❌ Do not change `ENTITLEMENT_ENFORCEMENT_ENABLED` value (remains `true`)

---

## 4. Validation Checklist for AG

### Pre-Deploy

| # | Check | Method |
|---|-------|--------|
| 1 | Entitlement observability tests pass | `py -m pytest tests/backend/test_r17g_entitlement_observability.py -v` |
| 2 | Phase 1 gate tests pass | `py -m pytest tests/backend/test_r17d_entitlement_gates.py -v` |
| 3 | Full backend suite passes | `py -m pytest tests/backend/ -v` (all 442+ pass) |
| 4 | py_compile entitlement.py | `py -m py_compile src/backend/common/entitlement.py` |

### Deploy

| # | Step |
|---|------|
| 5 | Commit logging fix |
| 6 | `terraform plan` — expect Lambda code hash change only (admin, google-auth, and any other Lambdas sharing the backend zip) |
| 7 | Matthew approves → `terraform apply` |

### Post-Deploy Validation

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 8 | Trigger allowed check: export | `GET /admin/export-data` (authenticated) | 200 OK |
| 9 | Trigger allowed check: calendar | `GET /admin/auth/google` (authenticated) | 200 OK or OAuth URL |
| 10 | Trigger allowed check: staff list | `GET /admin/staff` (authenticated) | 200 OK |
| 11 | Check CloudWatch for ENTITLEMENT_ALLOWED | Filter admin Lambda logs | ✅ Log lines appear |
| 12 | (Optional, if approved) Trigger denied check: 6th staff | `POST /admin/staff/onboard` with test data | 403 |
| 13 | (If step 12 run) Check CloudWatch for ENTITLEMENT_DENIED | Filter admin Lambda logs | ✅ Log line appears |
| 14 | Confirm alarm would fire | Check metric filter matches ENTITLEMENT_DENIED pattern | ✅ Metric increments if step 12 ran |

---

## 5. Should the 6th-Staff Denied Check Be Repeated?

### Recommendation: Yes, if safe test data is used

The 6th-staff creation test was already performed during 17I smoke and returned the expected 403. Repeating it after the logging fix confirms:
- The ENTITLEMENT_DENIED log line actually appears in CloudWatch
- The metric filter matches the log pattern
- The alarm would trigger if a real unexpected denial occurred

**Requirements for repeating:**
- Use clearly fake/test staff data (non-real name, test email)
- Do NOT actually create a real 6th staff member (the 403 prevents this)
- Confirm the attempt is rejected with 403 and logged
- No cleanup needed (403 = nothing was created)

---

## 6. Rollback Plan

### If Logging Fix Breaks Lambda Behavior

| Step | Action | Time |
|------|--------|------|
| 1 | `git revert` the logging commit | Immediate |
| 2 | `terraform plan` → confirm code hash rollback | 1 min |
| 3 | `terraform apply` | 1 min |
| 4 | Verify Lambda functions respond normally | 2 min |

### If Entitlement Behavior Breaks (Unlikely)

| Step | Action | Time |
|------|--------|------|
| 1 | Set `ENTITLEMENT_ENFORCEMENT_ENABLED=false` in terraform.tfvars | Immediate |
| 2 | `terraform apply` (disables enforcement) | 2 min |
| 3 | Investigate root cause | — |

### Safety Properties

- Logging changes cannot alter enforcement decisions (separate code paths)
- If `print()` is used, there is virtually zero risk of Lambda failure
- No data loss possible from logging changes
- No Stripe/Cognito/DynamoDB dependency
- Rollback restores previous behavior completely

---

## 7. Release Boundary

### 17J IS

- ✅ Fix entitlement structured logging
- ✅ Deploy updated Lambda code
- ✅ Verify CloudWatch receives ENTITLEMENT_ALLOWED/DENIED
- ✅ Confirm alarm/metric infrastructure works end-to-end

### 17J IS NOT

- ❌ Second-tenant setup
- ❌ Denied-path dry-run expansion
- ❌ Phase 2 gate wiring
- ❌ Frontend/mobile entitlement UI
- ❌ Tier/limit changes

---

## 8. Recommended Next Releases After 17J

| Release | Scope |
|---------|-------|
| **17K** | Second-tenant denied-path dry-run planning (Kiro) |
| **17L** | Phase 2 entitlement gates planning (client limit, booking limit) (Kiro) |
| **17M** | Frontend entitlement UI states (upgrade prompts, feature hiding) (Kiro/AG) |

After 17J logging is verified, the entitlement system has full observability and the platform is ready for broader multi-tenant testing.

---

## 9. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Terraform apply
- ❌ Lambda deployment
- ❌ DynamoDB writes
- ❌ Tenant metadata changes
- ❌ Second-tenant creation
- ❌ Stripe/Cognito/Postmark changes
- ❌ Frontend/mobile changes
- ❌ Ryan invitation
- ❌ Enforcement setting changes

This is a planning document. AG implements after Matthew reviews/approves.
