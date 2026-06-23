# Release 18C: Manual Cognito User Company ID Backfill Closeout

**Status:** Complete
**Date:** 2026-06-22
**Type:** Manual Cognito action (Matthew) + documentation closeout
**Scope:** All current tenant users now have `custom:company_id` set

---

## 1. Summary

Matthew manually reviewed all Cognito users in the production user pool and confirmed that `custom:company_id = tog_and_dogs` is set on all current active users.

---

## 2. Completion Status

| Item | Result |
|------|--------|
| `custom:company_id` schema exists on pool | ✅ Yes (added in 18B) |
| Cognito users reviewed | 5 |
| Users confirmed/updated with `custom:company_id = tog_and_dogs` | All current users |
| Users/groups/passwords changed (beyond attribute) | None |
| Second-tenant company_id values used | None |
| Second-tenant users created | None |
| Matthew admin login verified | ✅ Pass |
| Matthew platform_admin login verified | ✅ Pass |
| `/admin` dashboard works | ✅ Pass |
| `/platform-admin` works | ✅ Pass |
| Platform tenant detail verified | ✅ Pass |
| Platform audit page verified | ✅ Pass |

---

## 3. Observability Status

| Metric/Alarm | Status |
|--------------|--------|
| `TENANT_RESOLUTION_FALLBACK` | ⏳ Deferred to observation period (18D) |
| `TENANT_RESOLUTION_FAILED` | ⏳ Deferred to observation period (18D) |

CloudWatch fallback/failure metrics will be monitored during the 18D observation window to confirm zero fallback occurrences after backfill.

---

## 4. Security Attestation

- All current production users have `custom:company_id` explicitly set
- No user relies solely on the `DEFAULT_COMPANY_ID` fallback for tenant resolution
- No private user details (usernames, emails, passwords) were documented
- No screenshots, raw exports, or tokens were captured in the repository

---

## 5. Blocker Resolution

| Gate | Previous Status | Updated Status |
|------|----------------|----------------|
| 17Z/18C: All users have custom:company_id | ❌ Missing schema + unset | ✅ **Resolved** |

### Remaining Steps Before Strict Mode

| Step | Status |
|------|--------|
| 18D: Fallback metric observation (7 days target) | ⏳ Starting now |
| 18E: Matthew approves strict mode | ⏳ Pending |
| 18F: Enable `TENANT_RESOLUTION_MODE=multi` | ⏳ Pending 18E |

---

## 6. What Was NOT Done

- ❌ No code changes
- ❌ No Terraform/AWS changes
- ❌ No second tenant created
- ❌ No strict/multi mode enabled
- ❌ No DynamoDB writes
- ❌ No Stripe/Postmark changes
- ❌ No frontend/mobile deployment
- ❌ No Ryan/tester changes

---

## 7. Recommended Next Release

**18D — Fallback Metric Observation Period**

- Monitor `TENANT_RESOLUTION_FALLBACK` in CloudWatch for 7+ days
- Target: zero new fallback occurrences
- If zero: proceed to 18E (strict mode approval gate)
- If non-zero: investigate which user is still missing the attribute
