# Release 18Q: Strict Mode Final Gate Review Preparation Plan

**Status:** Planning — Gate Review Scheduled On/After June 30, 2026
**Date:** 2026-06-24
**Priority:** High (final gate before strict multi-tenant resolution)
**Scope:** Define the read-only observation review checklist for strict-mode approval

---

## 1. Observation Window

| Parameter | Value |
|-----------|-------|
| Observation start | 2026-06-23 15:20 UTC (18B deploy + 18C backfill) |
| Minimum observation duration | 7 days |
| Earliest gate review date | **2026-06-30** |
| Required: zero fallback/failure events | Yes |

---

## 2. Final 7+ Day Observation Review Checklist

AG should execute this as a **read-only** review on or after June 30, 2026:

| # | Check | Source | Expected | Pass/Fail |
|---|-------|--------|----------|-----------|
| 1 | `TENANT_RESOLUTION_FALLBACK` total count since June 23 | CloudWatch metric: `togs-and-dogs-prod-entitlement-denied-admin` log group + google-auth | **0** | ___ |
| 2 | `TENANT_RESOLUTION_FAILED` total count since June 23 | Same log groups | **0** | ___ |
| 3 | Tenant-resolution fallback alarm state | CloudWatch Alarms | **OK** (not in ALARM) | ___ |
| 4 | Tenant-resolution failed alarm state | CloudWatch Alarms | **OK** (not in ALARM) | ___ |
| 5 | `/admin` loads successfully | Browser or authenticated GET | **200 OK** | ___ |
| 6 | `/platform-admin` loads successfully | Browser or authenticated GET | **200 OK** | ___ |
| 7 | Google Calendar connection health | `GET /admin/auth/status` | **Connected** | ___ |
| 8 | Recent `ENTITLEMENT_DENIED` alarms for tog_and_dogs | CloudWatch | **0 unexpected** (intentional staff limit 403 OK) | ___ |
| 9 | Calendar health alarm state | CloudWatch | **OK** | ___ |
| 10 | No login/access regressions reported | Matthew confirmation | **None** | ___ |

### CloudWatch Query Templates

```
# Fallback events (should return 0 results):
filter @message like "TENANT_RESOLUTION_FALLBACK"
| stats count() as fallback_count

# Failed events (should return 0 results):
filter @message like "TENANT_RESOLUTION_FAILED"
| stats count() as failed_count

# Time window: 2026-06-23T15:20:00Z to review date
```

### Log Groups to Check

- `/aws/lambda/togs-and-dogs-prod-admin`
- `/aws/lambda/togs-and-dogs-prod-google-auth`

---

## 3. Strict-Mode Readiness Criteria

ALL must be true for PASS:

| # | Criterion | Status |
|---|-----------|--------|
| R1 | Zero `TENANT_RESOLUTION_FALLBACK` events in 7+ days | ⏳ Pending review |
| R2 | Zero `TENANT_RESOLUTION_FAILED` events in 7+ days | ⏳ Pending review |
| R3 | All Cognito users have `custom:company_id` set | ✅ Done (18C) |
| R4 | `/admin` remains functional | ⏳ Pending review |
| R5 | `/platform-admin` remains functional | ⏳ Pending review |
| R6 | Google Calendar connected | ⏳ Pending review |
| R7 | No second tenant exists yet | ✅ Confirmed |
| R8 | No unresolved tenant-routing bugs | ✅ (18P fixed calendar race) |
| R9 | No orphaned calendar event defect remaining | ✅ (18P deployed) |
| R10 | Phase 1 + Phase 2 entitlement gates functioning | ✅ (18N validated) |
| R11 | Rollback plan reviewed | ✅ (17X documented) |
| R12 | Matthew explicitly approves strict-mode enablement | ⏳ Pending |

---

## 4. Explicit Non-Actions (During Gate Review)

| ❌ Do NOT | Reason |
|-----------|--------|
| Enable `TENANT_RESOLUTION_MODE=multi` | Separate release after approval |
| Run `terraform apply` | No infra changes during review |
| Deploy Lambda code | No code changes during review |
| Modify Cognito users/attributes | Backfill already complete |
| Create a second tenant | Gate must pass first |
| Modify tenant metadata | Not needed for review |
| Create bookings/clients/jobs | Not needed for review |

---

## 5. AG Execution Prompt (Read-Only Gate Review)

When the review date arrives (≥ June 30, 2026), AG should:

### Inputs

| Parameter | Value |
|-----------|-------|
| Observation start time | `2026-06-23T15:20:00Z` |
| Review time | Current time (≥ 2026-06-30) |
| Log groups | `/aws/lambda/togs-and-dogs-prod-admin`, `/aws/lambda/togs-and-dogs-prod-google-auth` |
| Alarm names | `togs-and-dogs-prod-entitlement-denied-admin`, `togs-and-dogs-prod-entitlement-denied-google-auth`, `togs-and-dogs-prod-entitlement-denied` |
| AWS profile | `usmissionhero-website-prod` |

### Actions (Read-Only)

1. Query CloudWatch Logs for `TENANT_RESOLUTION_FALLBACK` in the time window
2. Query CloudWatch Logs for `TENANT_RESOLUTION_FAILED` in the time window
3. Check alarm states (DescribeAlarms)
4. Verify `/admin` returns 200 (authenticated GET)
5. Verify `/platform-admin` returns 200 (authenticated GET)
6. Check Google Calendar status endpoint

### Report Fields

- Observation window: start → end (days elapsed)
- Fallback count: X (target: 0)
- Failed count: X (target: 0)
- Alarm states: OK/ALARM/INSUFFICIENT_DATA
- `/admin` status: 200/error
- `/platform-admin` status: 200/error
- Calendar health: connected/disconnected
- Decision: PASS / WARN / FAIL

### Stop Conditions

- If ANY CloudWatch query fails with auth/permission error → report but don't invent data
- If fallback count > 0 → FAIL
- If failed count > 0 → FAIL
- If alarms are in ALARM state → investigate

---

## 6. Decision Outcomes

| Outcome | Criteria | Action |
|---------|----------|--------|
| **PASS** | Zero fallback + zero failed + all systems healthy + 7+ days elapsed | Recommend Matthew approve strict-mode enablement as a separate release |
| **WARN** | Zero events but < 7 days elapsed, or minor alarm issue | Extend observation window by 3–7 days |
| **FAIL** | Any fallback or failed event found, or system health issue | Do NOT enable strict mode; investigate root cause |

---

## 7. Follow-Up Release Sequence

| Release | Scope | Depends On |
|---------|-------|------------|
| **18Q** | Strict mode gate review prep (this document) | ✅ Done |
| **18R** | AG executes read-only gate review (on/after June 30) | Calendar date |
| **18S** | Matthew approval checkpoint for strict-mode enablement | 18R = PASS |
| **18T** | Strict-mode enablement (`TENANT_RESOLUTION_MODE=multi`) via Terraform | 18S approved |
| **18U** | Post-enable validation smoke | 18T deployed |
| **19A** | Second-tenant dry-run planning | 18U passed |

---

## 8. What This Document Does NOT Authorize

- ❌ Enabling strict mode
- ❌ Running Terraform
- ❌ Deploying Lambda code
- ❌ Modifying Cognito
- ❌ Creating a second tenant
- ❌ DynamoDB writes
- ❌ Creating bookings/clients/jobs
- ❌ Google Calendar changes
- ❌ Stripe/Postmark/payment changes
- ❌ Frontend/mobile deployment
- ❌ Ryan/tester changes
- ❌ Executing the gate review itself (that's 18R)

This is a preparation/checklist document. The actual gate review (18R) happens on or after June 30, 2026.
