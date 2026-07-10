# Release Notes — Release 22L: Pending Cancellation Request Admin Visibility Fix Pre-Deploy

## Overview
Release 22L addresses a visibility gap in the Admin Portal where clients' pending booking cancellation requests (`CANCELLATION_REQUESTED`) were completely invisible to administrators. This frontend-only fix ensures that cancellation requests are visible, countable, and actionable within the appropriate admin queues without modifying the backend or DynamoDB data.

## Scope of Changes

### 1. Frontend Status Refactoring (`web/src/components/AdminDashboard.jsx`)
* **Cancellation Helper Redefinition:** 
  * Redefined `isCancelledRecord(item)` to only represent final/terminal cancellation states: `CANCELLED`, `DECLINED`, `REJECTED`, `CANCELLATION_DENIED`.
  * Added `isCancellationPendingRecord(item)` specifically for `CANCELLATION_REQUESTED` records.
* **Active List Inclusion:**
  * Updated `isActiveRecord(item)` so it does not exclude `CANCELLATION_REQUESTED`.
  * This automatically enables pending cancellation records to be included in the `'NEEDS_ACTION'` and `'ALL'` active queues.
* **Badge and Labels Update:**
  * Updated `getStatusLabel` to return `"Cancellation Requested"` (instead of `"Cancel Requested"`) for clearer administrative context.
  * Updated `getStatusClass` to assign `"status-chip--urgent"` (red border and text) to pending cancellations.
* **Exposed Action Dropdown Menu Button:**
  * Added `CANCELLATION_REQUESTED` case to `getWorkflowState` contextual actions to return `["PROCESS_CANCELLATION", "ARCHIVE", "DELETE"]`.
  * Added `'PROCESS_CANCELLATION'` label mapping and click handler in the row action dropdown menu. Clicking this calls the pre-existing `handleProcessCancellation` function to Approve/Deny the cancellation request.

## Verification
* **Frontend Compilation:** Compiled successfully using `npm run build` with Vite.
* **Regression Tests:** Standalone pytest suites for orphaned identities, cancellations, and login controls passed successfully.
* **State Check:** Git status is clean, and only modified files are staged.
