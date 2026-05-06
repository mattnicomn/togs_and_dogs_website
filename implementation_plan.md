# Implementation Plan - Fix Bulk Update Partial Failure for Data Issues Cleanup

The goal is to resolve the partial failure when performing bulk actions (specifically "Move to Trash") on records labeled as "Data Issues".

## User Review Required

> [!IMPORTANT]
> - The backend `DELETE` (move to trash) and `ARCHIVE` actions will be updated to support bulk processing and "ID healing".
> - A new "Dry Run" analysis phase will be added before permanent deletion (PURGE) to provide a summary of purgeable vs. blocked records.
> - Permanent deletion will be strictly limited to records already in the `DELETED` or `TRASH` state.

## Proposed Changes

### Backend

#### [MODIFY] [admin_handler.py](file:///C:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py)
- Implement `_resolve_admin_record(pk, sk)` helper with "Resolution Chain":
    1. Direct `get_item(pk, sk)`
    2. Swapped `get_item(sk, pk)`
    3. Scan for embedded IDs (e.g., `REQ#...`)
- Update `DELETE` and `ARCHIVE` actions to handle `records` array (bulk) and use the resolver.
- Enhance `PURGE` action to support `dry_run: true` for pre-deletion analysis.
- Ensure `PURGE` returns a summary of: total selected, total purgeable, total blocked, and reasons.

---

### Frontend

#### [MODIFY] [AdminDashboard.jsx](file:///C:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)
- Update `handleBulkUpdate` to send a single bulk request for `DELETE` and `ARCHIVE`.
- Update `handleBulkPurge` to:
    1. Call backend with `dry_run: true` to get the analysis summary.
    2. Show summary to user (Total Selected, Purgeable, Blocked + Reasons).
    3. Only proceed with the actual purge for confirmed purgeable records.
- Improve error reporting to display granular failure reasons.

---

### Documentation

#### [NEW] [admin-data-issues-bulk-cleanup-fix.md](file:///C:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/release-notes/admin-data-issues-bulk-cleanup-fix.md)
- Release notes for the fix.

## Verification Plan

### Automated Tests
- `py -m py_compile src/backend/handlers/admin_handler.py`
- `npm run build` (in `web` directory)

### Manual Verification
1. Open Admin Portal.
2. Select "Data Issues" filter.
3. Perform "Move to Trash" bulk action.
4. Verify success.
5. Go to "Trash" view.
6. Perform "Delete Permanently" bulk action.
7. Verify "Dry Run" summary appears.
8. Confirm purge and verify records are gone.
