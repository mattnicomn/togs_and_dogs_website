# Admin Permanent Delete Records

**Date:** 2026-04-27
**Status:** Pending Deployment

## Issue

The deleted appointment section could accumulate records with no admin-controlled way to permanently remove records when operational cleanup was required.

## Change

Validated and strengthened the protected admin-only permanent delete workflow for records already in the deleted/archive section.

### Backend (`src/backend/handlers/admin_handler.py`)
- PURGE action handler: authenticates admin, fetches record, validates status is DELETED, performs `delete_item`, logs action with timestamp and admin email.
- Returns 400 if record is not in DELETED status.
- Returns 404 if record not found.
- Returns 500 with clear message on DynamoDB failure.

### Frontend (`web/src/components/AdminDashboard.jsx`)
- "Delete Permanently" button only appears for records with status DELETED (via `PURGE_FOREVER` action in `getWorkflowState`).
- Single-record purge requires typing "DELETE" in a confirmation modal before the button enables.
- Bulk purge button only appears when viewing the Trash/Deleted filter.
- Bulk purge skips non-DELETED records and reports skip count.
- On success: record removed from local state, success notification shown.
- On failure: error notification with message from backend.

### API Client (`web/src/api/client.js`)
- `purgeRecord(pk, sk)` sends `{ PK, SK, action: 'PURGE' }` to `/admin/requests` (protected endpoint).

## Safeguards

- Soft delete remains the default behavior.
- Permanent delete is only available from the deleted/archive section.
- Single-record confirmation requires typing DELETE.
- Active records are protected from accidental permanent deletion (backend rejects if status ≠ DELETED).
- The admin UI refreshes after successful deletion.
- Bulk purge only processes records currently in DELETED status; others are skipped.
- Backend logs all purge operations with admin identity and timestamp.

## Scope

- Admin dashboard only.
- Appointment records only.
- No authentication model changes.
- No infrastructure resource renaming.

## Validation

- Frontend build: PASS (Vite production build, 88 modules, 0 errors).
- Backend syntax validation: PASS (py_compile on all handler and common modules).
- Deleted records remain isolated from active lists (backend `ALL` query excludes DELETED/ARCHIVED).
- Permanent delete removes only eligible deleted records (backend guard enforces status check).
- PURGE_FOREVER action only rendered for items where `isDeletedRecord(item)` is true.
