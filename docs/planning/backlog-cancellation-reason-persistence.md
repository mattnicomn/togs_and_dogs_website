# Backlog: Cancellation Reason Persistence in Review Handler

## Priority: Low
## Status: Planned (not started)
## Discovered During: Release 6B Phase 2 validation

## Problem Statement

When an admin cancels a request via the Admin Dashboard "Status & Lifecycle Actions" dropdown, the cancellation goes through the **review handler** (`POST /admin/review` with `status: CANCELLED`). The review handler accepts a `reason` field in the request body and stores it in the audit log entry, but does NOT persist it as `cancellation_reason` on the request record.

This means the `VISIT_CANCELLED` notification template cannot display the cancellation reason for admin-initiated cancellations via the review path.

## Current Behavior

| Cancellation Path | Persists `cancellation_reason`? | Notification shows reason? |
|-------------------|-------------------------------|---------------------------|
| Client requests → Admin approves (`PUT /admin/cancel/decision`) | ✅ Yes | ✅ Yes |
| Admin direct cancel via review handler (`POST /admin/review`) | ❌ No | ❌ No (template correctly hides section) |
| Admin bulk status change | ❌ No | ❌ No |

## Proposed Fix

In `src/backend/handlers/review_handler.py`, when `new_status == 'CANCELLED'`:
- Add `cancellation_reason` to the update expression
- Source from `body.get('reason')` (already available in the request body)

```python
# In the update expression section, add:
if new_status == 'CANCELLED' and body.get('reason'):
    update_expr += ", cancellation_reason = :cr"
    expr_attr_vals[":cr"] = body.get('reason')
```

## Impact
- Small (2-3 lines in review_handler.py)
- No infrastructure changes
- No frontend changes needed (reason field is already sent in the body)
- Notification template already handles the field when present

## Files Involved
- `src/backend/handlers/review_handler.py` — persist reason on CANCELLED transition

## Dependencies
- None (standalone enhancement)
- Should NOT be bundled with notification template releases
