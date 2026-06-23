# Release 18J: Tenant Usage Metering and Tier Limit Accuracy Review

**Status:** Planning
**Date:** 2026-06-23
**Priority:** Medium (validates tier enforcement accuracy before second-tenant work)
**Scope:** Review usage counting accuracy and tier limit enforcement behavior

---

## 1. Context

Release 18I confirmed Google Calendar sync is restored and working. The platform now has:
- Phase 1 entitlement enforcement active (staff limit, export gate, calendar gate)
- All users backfilled with `custom:company_id` (18C)
- Tenant-resolution fallback observation in progress (18D)
- Google Calendar reconnected and validated (18G/18I)

Before second-tenant creation can proceed, the accuracy of usage metering and tier limit enforcement must be verified for the current tenant.

---

## 2. Current Usage Metering State

### What Is Currently Counted

| Metric | Method | Where Used |
|--------|--------|-----------|
| Staff count | COUNT query on `COMPANY#{company_id} / STAFF#*` | Phase 1 staff limit gate (17D) |
| Client count | COUNT query on `COMPANY#{company_id} / CLIENT#*` | Platform Admin usage display (17P) |
| Booking count (monthly) | Not metered | Not enforced (planned Phase 2) |
| Notification count (monthly) | Existing `QUOTA#` mechanism | Notification service (partially parameterized) |

### What Is NOT Metered

| Metric | Status | Impact |
|--------|--------|--------|
| Monthly bookings | ❌ No counter | Cannot enforce max_monthly_bookings |
| Active vs disabled staff | ⚠️ Phase 1 counts ALL staff records (active + disabled) | May over-count |
| Active vs archived clients | ⚠️ COUNT query includes all CLIENT# records | May over-count |
| Monthly notifications per tenant | ⚠️ Uses `QUOTA#tog_and_dogs` (parameterized in 11E) | Works for single tenant |

---

## 3. Tier Limit Accuracy Questions

### Staff Count

| Question | Current Behavior | Desired Behavior |
|----------|------------------|------------------|
| Does count include disabled staff? | Yes (COUNT on STAFF#*) | Debatable — disabled staff hold a slot but can't work |
| Does count include unlinked staff? | Yes | Same debate |
| Is count-at-time-of-creation accurate? | Yes (query runs before each creation) | ✅ Correct |
| Can a race condition create staff over limit? | Theoretically (no conditional write) | Low risk at current scale |

**Recommendation for MVP:** Count all staff records regardless of status. A deleted profile frees the slot; a disabled one does not. This is the simplest, safest model. Document clearly for business owners.

### Client Count

| Question | Current Behavior | Desired Behavior |
|----------|------------------|------------------|
| Does count include archived clients? | Unknown — needs verification | Should probably exclude archived |
| Does count include disabled clients? | Unknown | Should probably include (still consumes resources) |
| Is client limit enforced? | ❌ Phase 2 (not implemented) | Future gate |

### Monthly Bookings

| Question | Current Behavior | Desired Behavior |
|----------|------------------|------------------|
| Is there a per-tenant monthly counter? | ❌ No | Needed for Phase 2 |
| How would it work? | Counter record per tenant per month | `USAGE#{company_id} / MONTH#{YYYY-MM}` |
| When to increment? | On successful booking creation | intake_handler + admin offline booking |
| When to reset? | Monthly (new SK key per month) | Automatic by design |

---

## 4. Platform Admin Usage Display Accuracy

The Platform Admin UI (17P) shows staff/client counts. These should match enforcement logic.

| Display | Source | Matches Enforcement? |
|---------|--------|---------------------|
| Staff count | COUNT query on STAFF# | ✅ Same query used by limit gate |
| Client count | COUNT query on CLIENT# | ⚠️ Enforcement not active (Phase 2) |
| "approximate" label | UI shows approximate | ✅ Appropriate disclaimer |

---

## 5. Validation Checklist (Read-Only)

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | Staff count shown in Platform Admin matches actual STAFF# records | Compare UI count vs DynamoDB query | Match |
| 2 | Staff limit gate uses same counting logic as UI | Code review | Confirmed same query |
| 3 | Current tog_and_dogs staff count vs limit (5) | Platform Admin or read-only query | Should show X/5 |
| 4 | 6th staff creation still blocked (if at 5/5) | Attempt blocked by gate (confirmed in 17I) | 403 |
| 5 | Client count shown in Platform Admin is reasonable | Platform Admin display | Non-negative, plausible |
| 6 | Export gate still functions | `GET /admin/export-data` | 200 for professional tier |
| 7 | Calendar gate still functions | `GET /admin/auth/google` | 200 for professional tier (already connected) |
| 8 | Notification quota uses tenant-parameterized key | Code review | `QUOTA#{company_id}` pattern |

---

## 6. Phase 2 Gate Design (Future)

### Booking Monthly Limit

```
PK: USAGE#{company_id}
SK: BOOKINGS#{YYYY-MM}

{
  "count": 47,
  "limit": 250,
  "last_incremented_at": "ISO"
}
```

- Increment on each successful booking creation
- Check before creation: if `count >= limit` → 403
- Soft warning at 80% (future UI feature)
- New month = new SK = automatic reset

### Client Active Limit

- Count active (non-archived) CLIENT# records
- Check before client profile creation
- Do not count archived clients toward limit

---

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Staff count includes disabled → owner confused | Medium | Low | Document in "Getting Started" guide |
| Client count includes archived → limit hit prematurely | Low (if implemented) | Medium | Exclude archived in Phase 2 query |
| Monthly booking counter missing | N/A (not enforced yet) | None currently | Implement in Phase 2 |
| Race condition on staff creation | Very low | Low | Acceptable for current volume |
| Platform Admin shows wrong count | Low | Low | Uses same query as enforcement |

---

## 8. Recommended Follow-Up Releases

| Release | Scope | Priority |
|---------|-------|----------|
| **18J** | Usage metering accuracy review (this document) | ✅ Done |
| **18K** | Phase 2 entitlement gate design (client limit, booking limit) | Medium |
| **18L** | Monthly booking counter implementation | Medium |
| **18M** | Client active count refinement (exclude archived) | Low |
| **18N** | Strict-mode final gate review (June 30 target) | High |

---

## 9. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Creating metering records
- ❌ Modifying DynamoDB
- ❌ Changing entitlement limits
- ❌ Terraform/AWS changes
- ❌ Creating second tenant
- ❌ Enabling strict mode
- ❌ Cognito changes
- ❌ Frontend/mobile deployment
- ❌ Stripe/Postmark changes
- ❌ Ryan/tester changes

This is a review/planning document. Phase 2 implementation requires separate approval.
