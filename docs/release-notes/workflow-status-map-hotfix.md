# Release Notes: Workflow Status Map Hotfix

## Initial Fix (commit ff9e3ff)

Records in `QUOTED` status were visible only under "All Active" with no dedicated sidebar filter.
The M&G verification flow (`VERIFY_MEET_GREET`) was setting the request status to `READY_FOR_APPROVAL`
instead of `MG_COMPLETED`, breaking the approval path after M&G.

### Changes
- `AdminDashboard.jsx`: Added dedicated sidebar filters for `QUOTED` and `MG_COMPLETED`.
- `AdminDashboard.jsx`: Fetch logic changed so all active-status filters use the backend `ALL` scan,
  then client-side filter by exact status — eliminating the need for per-status indexed queries.
- `review_handler.py`: `VERIFY_MEET_GREET` now advances request to `MG_COMPLETED` (not `READY_FOR_APPROVAL`)
  and also sets `meet_and_greet_completed = true` on the Pet record.
- `review_handler.py`: Request item is fetched early so `VERIFY_MEET_GREET` can read the pet_id.

---

## Follow-up Correction (commit — see git log)

**Issue:** `QUOTED → APPROVED` was incorrectly blocked by the M&G validation guard.  
The guard in `review_handler.py` ran unconditionally for all APPROVE transitions, including records
already in `QUOTED` status — where M&G is implicitly resolved by virtue of having reached the quote stage.

**Root cause:** M&G guard did not account for `current_status`.

### Backend fix — `review_handler.py`
- M&G required check is now skipped when `current_status` is in:
  `QUOTED`, `QUOTE_SENT`, `MG_COMPLETED`, `QUOTE_NEEDED`
- M&G protection remains **fully active** for `MEET_GREET_REQUIRED` / `NEEDS_MG` records.

### Backend fix — `common/status.py`
Three transition gaps that were blocking valid operator workflows:
- `MEET_GREET_REQUIRED` → `CANCELLED` added (operator can cancel an M&G record).
- `MG_COMPLETED` → `QUOTED`, `QUOTE_SENT`, `CANCELLED` added.
- `QUOTE_NEEDED` → `QUOTED`, `APPROVED` added (direct paths from quote-needed stage).

### Frontend fix — `AdminDashboard.jsx`
- `statusMap` now includes explicit `'QUOTED': 'QUOTED'` and `'MEET_GREET_REQUIRED': 'MEET_GREET_REQUIRED'` entries.
- No structural workflow changes.

## Canonical Approve Behavior (enforced)

| From Status            | APPROVE allowed? | Notes                                |
|------------------------|-----------------|--------------------------------------|
| `NEEDS_REVIEW`         | ✅ if no M&G    | Blocked if M&G required and not done |
| `MEET_GREET_REQUIRED`  | ❌              | Must complete M&G first              |
| `MG_COMPLETED`         | ✅              | M&G done — approve directly          |
| `QUOTE_NEEDED`         | ✅              | No forced quoting step               |
| `QUOTED`               | ✅              | **Now unblocked by this fix**        |
| `APPROVED`             | ✅ idempotent   | Same-status always allowed           |

## UI Feedback & Idempotency Correction (Follow-up)

**Issue:** Successful transitions (like double-clicking Approve, or moving `QUOTED → APPROVED`) would sometimes incorrectly show "Action failed: Meet & Greet must be marked completed". The workflow proceeded correctly in DynamoDB, but the UI showed a stale validation error.

**Root cause:**
1. **Frontend:** `AdminDashboard.jsx` had `fetchAllData()` inside the same `try/catch` block as the action. A momentary network blip during the refresh would trigger the catch block and display the backend's stale error message.
2. **Backend:** Idempotent requests (e.g. `APPROVED → APPROVED`) were evaluated against validation rules. An already-approved request bypassed the `QUOTED` guard and hit the M&G check, which failed if M&G wasn't completed, throwing a 400 error back to the UI.

### Changes
- `AdminDashboard.jsx`: Separated `fetchAllData()` into its own `try/catch` block outside the action submission. Post-action refresh failures now log a non-blocking warning instead of overwriting the success toast.
- `AdminDashboard.jsx`: Added action-specific, user-friendly success messages ("Visit approved successfully", etc.).
- `AdminDashboard.jsx`: explicitly clear `error` state before actions.
- `review_handler.py`: Bypassed validation logic for idempotent status changes (`if current_status != new_status:`). Idempotent submissions now cleanly return 200 without triggering stale validation checks.

## Deployment
- Terraform root: `c:\Users\mattn\OneDrive\Desktop\togs_and_dogs_website\infra\prod`
- 8 Lambda functions updated (all handlers share the same zip).
- Frontend rebuilt (`npm run build`), synced to S3, CloudFront invalidated.
- No Cognito, ClientProfile, StaffProfile, or tenant model changes.
- No bulk production data mutations.
