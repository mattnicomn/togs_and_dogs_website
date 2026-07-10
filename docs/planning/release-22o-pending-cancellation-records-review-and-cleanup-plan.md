# Release 22O: Pending Cancellation Records Review and Cleanup/Processing Plan

**Status:** Planning
**Date:** 2026-07-10
**Priority:** Medium (visible records require classification before action)
**Scope:** Decision framework for handling pending cancellation records in production

---

## 1. Background

Release 22M fixed a visibility gap where pending cancellation requests (`CANCELLATION_REQUESTED`) were hidden from the admin portal. After deployment, 2 records are now visible in the Needs Action queue:

| # | Client/Pet | Service | Status | Notes |
|---|-----------|---------|--------|-------|
| 1 | Joey Rockwell | Overnight | Cancellation Requested | Visible in Needs Action |
| 2 | TestPet_ScenarioB | Pet Sitting | Cancellation Requested | Visible in Needs Action |

No action has been taken on either record. They remain unmodified in DynamoDB.

---

## 2. Decision Tree

```
┌─────────────────────────────────────────────────────────┐
│ For each CANCELLATION_REQUESTED record:                 │
│                                                         │
│ 1. Is this a REAL customer/business cancellation?       │
│    → YES: Review through standard Approve/Deny flow     │
│           (confirm with client if needed before acting) │
│                                                         │
│ 2. Is this a TEST or STALE production record?           │
│    → YES: Use controlled cleanup process                │
│           (archive or trash with explicit approval)     │
│                                                         │
│ 3. Is the classification UNCERTAIN?                     │
│    → HOLD: Do not modify. Document for later review.    │
│           Label in admin notes if possible.             │
└─────────────────────────────────────────────────────────┘
```

### Classification Criteria

| Signal | Suggests Real | Suggests Test/Stale |
|--------|:---:|:---:|
| Client name matches a known paying customer | ✅ | |
| Pet name follows test naming pattern (e.g., "TestPet_*", "ScenarioB") | | ✅ |
| Booking has associated payment record | ✅ | |
| Record was created during a documented validation run | | ✅ |
| Client has other active bookings or history | ✅ | |
| Record was created months ago with no follow-up | | ⚠️ Likely stale |

---

## 3. Record-by-Record Classification (Matthew Decision Required)

### Record 1: Joey Rockwell — Overnight

| Field | Value | Assessment |
|-------|-------|------------|
| Client name | Joey Rockwell | Could be real or test — Matthew must classify |
| Service type | Overnight | Standard service |
| Status | CANCELLATION_REQUESTED | Pending review |
| Payment state | Unknown — check before acting | |
| Created during validation? | Unknown | |

**Matthew must classify as:** `REAL` / `TEST/STALE` / `HOLD`

**If REAL:** Use Review Cancellation → Approve or Deny based on business decision.
**If TEST/STALE:** Archive with explicit approval (see Section 5).
**If HOLD:** Leave in Needs Action; document for future review.

### Record 2: TestPet_ScenarioB — Pet Sitting

| Field | Value | Assessment |
|-------|-------|------------|
| Client/Pet name | TestPet_ScenarioB | Naming pattern strongly suggests test record |
| Service type | Pet Sitting | Standard service |
| Status | CANCELLATION_REQUESTED | Pending review |
| Payment state | Unknown — check before acting | |
| Created during validation? | Likely (naming pattern matches test conventions) | |

**Matthew must classify as:** `REAL` / `TEST/STALE` / `HOLD`

**If TEST/STALE (likely):** Archive or approve-cancellation with explicit approval.
**If HOLD:** Leave in Needs Action; document for future review.

---

## 4. Safe Handling Procedures

### Procedure A: Process Real Cancellation

1. Open the record in Admin → Needs Action
2. Click "Review Cancellation" from the row action menu
3. Review the booking details, dates, and client context
4. Decide: Approve Cancellation or Deny Cancellation
5. Confirm the action in the modal
6. Verify the record moves to the correct tab (Cancelled or back to Active)
7. Verify Google Calendar event is updated if applicable

**Requires:** Matthew classification as REAL + business decision to approve/deny.

### Procedure B: Controlled Test/Stale Record Cleanup

1. Matthew classifies the record as TEST/STALE (explicit approval)
2. Preferred action: **Approve Cancellation** through the standard admin flow
   - This moves the record to terminal "Cancelled" state cleanly
   - Preserves audit trail
   - No data deletion required
3. Alternative: Archive/soft-delete if the admin UI supports it
4. Last resort: DynamoDB record removal only with explicit Matthew approval and documented justification

**Requires:** Matthew explicit classification + approval of specific action.

### Procedure C: Hold (Uncertain Records)

1. Do not modify the record
2. Document the uncertainty in project notes
3. Revisit after gathering more context (check payment history, client communication, creation date)
4. Re-classify when information is available

---

## 5. Cleanup/Retention Policy

### Default Policy

| Principle | Rule |
|-----------|------|
| No bulk deletion | Every record must be individually classified and approved |
| No hard delete by default | Prefer archive, soft-delete, or standard workflow completion |
| Audit trail preservation | All cleanup actions must produce audit records |
| Payment-linked records | Extra caution — never delete records with payment history without accounting review |
| Standard workflow preferred | Use Approve/Deny Cancellation flow rather than direct DB manipulation |
| No silent cleanup | Every action must be documented with reason and approval |

### Record Lifecycle (Recommended)

```
CANCELLATION_REQUESTED
  ├── Approve Cancellation → CANCELLED (terminal, visible in Cancelled tab)
  ├── Deny Cancellation → returns to ACTIVE (visible in active lists)
  ├── Archive → ARCHIVED (hidden from active views, preserved for audit)
  └── HOLD → remains in Needs Action until classified
```

### What NOT to Do

- ❌ Do not delete DynamoDB records directly
- ❌ Do not bulk-process multiple records without individual review
- ❌ Do not approve/deny cancellations without confirming record identity
- ❌ Do not clean up records with associated Stripe payment IDs without payment state review
- ❌ Do not remove Google Calendar events as part of cancellation cleanup without separate planning
- ❌ Do not delete the client, pet, or staff profile associated with a cancelled booking
- ❌ Do not modify payment state (paid/unpaid/refunded) during cancellation processing

---

## 6. Production Data Safety Guardrails

| Guardrail | Enforcement |
|-----------|-------------|
| No bulk deletion | Manual one-by-one classification required |
| No cleanup without record-level approval | Matthew must approve each specific record |
| No cancellation approval/denial without business confirmation | Classify first, act second |
| No payment-state mutation | Cancellation processing does not change payment records |
| No Stripe changes | Refunds/adjustments are a separate workflow |
| No Google Calendar cleanup | Calendar event handling is automatic on approve; no manual intervention |
| No client/pet/profile deletion | Cancellation is booking-level only |
| No cross-record side effects | Processing one cancellation does not affect other bookings for the same client |

---

## 7. Future Admin UX Improvements (Recommendations)

| Improvement | Priority | Description |
|-------------|----------|-------------|
| Test record label | Medium | Add visual indicator for records identified as test/validation data |
| Archive action | Medium | Add explicit "Archive" button for stale records (separate from Approve/Deny) |
| Audit note field | Low | Allow admin to attach a note before archiving/trashing (reason for cleanup) |
| Cancellation review queue | Low | Separate "Pending Cancellations" sub-queue if Needs Action grows crowded |
| Record creation source | Low | Tag records created during validation runs vs. real client submissions |
| Staff/Ryan cleanup guide | Low | SOPs for record lifecycle decisions |
| Stale record detection | Future | Auto-flag records with no activity for 30+ days |

---

## 8. Matthew Validation Checklist

Before taking action on either record:

| # | Check | Status |
|---|-------|--------|
| 1 | Confirm record appears in Needs Action queue | ⬜ |
| 2 | Open Review Cancellation modal to inspect (read-only look) | ⬜ |
| 3 | Do NOT approve/deny until classification is decided | ⬜ |
| 4 | Check if record has associated payment history | ⬜ |
| 5 | Check if client name matches a real customer | ⬜ |
| 6 | Classify: REAL / TEST/STALE / HOLD | ⬜ |
| 7 | If TEST/STALE: decide Archive vs Approve Cancellation | ⬜ |
| 8 | If REAL: decide Approve vs Deny based on business need | ⬜ |
| 9 | Confirm action taken (or confirm HOLD / no action) | ⬜ |
| 10 | Verify record moved to correct tab after action | ⬜ |

---

## 9. Recommended Next Actions

| Option | Description | Requires |
|--------|-------------|----------|
| **A** | Matthew classifies both records → processes via standard admin workflow | Matthew decision |
| **B** | Hold both records → revisit after 22J deployment decision is made | No action needed |
| **C** | Classify TestPet_ScenarioB as test (approve cancellation) → hold Joey Rockwell for review | Matthew partial approval |

### Recommendation

**Option C** is recommended:
- `TestPet_ScenarioB` naming pattern strongly suggests a test record — approve cancellation to clear it from Needs Action
- `Joey Rockwell` requires Matthew to confirm whether this is a real client before taking action
- This reduces Needs Action noise without risking real customer data

---

## 10. What This Document Does NOT Authorize

- ❌ Approving or denying any cancellation
- ❌ Archiving, deleting, or modifying any record
- ❌ DynamoDB writes of any kind
- ❌ Code changes
- ❌ Deployment
- ❌ Terraform/AWS changes
- ❌ Cognito/identity/profile changes
- ❌ Stripe/payment changes
- ❌ Google Calendar changes
- ❌ Mobile/TestFlight/App Store changes
- ❌ Ryan/tester changes

This is a decision framework document. Record processing requires Matthew's explicit per-record classification and approval.
