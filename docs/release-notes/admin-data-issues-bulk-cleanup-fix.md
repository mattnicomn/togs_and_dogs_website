# Release Notes: Admin Data Issues Bulk Cleanup Fix

## Overview
This update resolves the root cause of partial failures when performing bulk actions on "Data Issues" records in the Admin Portal. It introduces robust record resolution (ID healing) and a safe, two-step permanent deletion workflow.

## Key Changes

### Backend Logic Updates (`admin_handler.py`)
- **ID Healing Resolution**: Added a multi-stage resolution chain to find records even with swapped PK/SK or malformed identifiers.
- **Bulk Lifecycle Support**: Added true bulk support for `DELETE` (Move to Trash) and `ARCHIVE` actions.
- **Pre-Purge Dry Run**: Implemented a `dry_run` flag for the `PURGE` action to allow analysis and summarization before permanent deletion.
- **Strict Guardrails**: Enforced that permanent `PURGE` only affects records already in the `DELETED` or `TRASH` state.
- **Granular Error Reporting**: The backend now returns specific failure reasons for every record that cannot be processed.

### Frontend UI Updates (`AdminDashboard.jsx`)
- **Bulk Optimization**: Updated move-to-trash/archive to use single-request bulk backend calls instead of dozens of parallel requests.
- **Analysis Step**: Added a new "Analyze Selection" phase before permanent deletion.
- **Summary Display**: The UI now shows a clear summary of Purgeable vs. Blocked records, including reasons (e.g., "Already in terminal state" or "Move to Trash first").

## Safety Controls
- **No Direct Purge**: Records must be moved to the Trash (`DELETED` status) before they can be permanently purged.
- **Active Record Protection**: The new logic explicitly prevents accidentally moving `COMPLETED`, `ARCHIVED`, or already `DELETED` records into the Trash again, and protects all active workflows.

## Verification Summary
- **Backend Build**: Verified via `py -m py_compile`.
- **Frontend Build**: Verified via `npm run build`.
- **Status Transitions**: Confirmed compliant with `is_valid_transition` logic.

## Usage Instructions
1. Navigate to **Admin Portal** -> **Data Issues**.
2. Select target records and use **Bulk Action** -> **Move to Trash**.
3. Navigate to **Trash** view.
4. Select records and click **Delete Permanently**.
5. Click **Analyze Selection** to view the summary.
6. Click **Confirm & Purge Permanently** to finish.
