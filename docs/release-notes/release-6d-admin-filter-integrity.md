# Release 6D: Admin Filter Integrity & Safe Delete Guardrails

## Overview
Fixes count/filter mismatches in the Admin Dashboard, prevents active records from appearing in Trash, and adds guardrails so purge/delete actions can only affect truly DELETED records.

## Status: ✅ Deployed & Production Validated (2026-05-21)

## Deployment
- **Commit:** `ee751c14e33e0cbb1dbd833fdc91ce527463ae92`
- **Terraform:** 0 added, 9 changed, 0 destroyed (Lambda code hash updates only)
- **Frontend:** Built, synced to S3 (`togs-and-dogs-prod-toganddogs-hosting`)
- **CloudFront:** Invalidation `IE01TIC3F1XE2AEB8OQD950OGX` on distribution `E35L00QPA2IRCY`
- **Backend tests:** 44/44 passed

## Changes

### Frontend (`web/src/components/AdminDashboard.jsx`)

**1. Needs Assignment count/click alignment**
- Created dedicated `UNASSIGNED` filter predicate
- Stat card navigates to `UNASSIGNED` filter (not `READY_FOR_APPROVAL`)
- Count and visible rows now use identical logic: `(APPROVED || BOOKED || JOB_CREATED) && !worker_id`

**2. Hardened `isDeletedRecord`**
- Removed `!!item.deleted_at` fallback
- Status is now the sole source of truth: only `DELETED`, `TRASH`, `DELETE` qualify
- Active records with `deleted_at` can no longer appear in Trash

**3. Zombie record detection**
- Records with `deleted_at` + active status are flagged as data integrity issues
- Protected statuses: APPROVED, ASSIGNED, SCHEDULED, BOOKED, JOB_CREATED, IN_PROGRESS, PENDING_REVIEW, NEEDS_REVIEW

**4. Purge button visibility**
- `PURGE_FOREVER` only shows when `status` is explicitly DELETED/TRASH/DELETE
- Zombie records get `DELETE` action instead of `PURGE_FOREVER`

**5. Bulk purge pre-validation**
- Pre-filters selected items to only include explicit DELETED/TRASH/DELETE records
- Shows warning if no purgeable records are selected
- Shows info notification if some records were skipped

### Backend (`src/backend/handlers/admin_handler.py`)

**6. Active record DELETE guard**
- Rejects DELETE action on records with status ASSIGNED, SCHEDULED, IN_PROGRESS, or BOOKED
- Returns: "Cannot delete active record (status: X). Cancel or archive first."
- Logs warning for rejected operations

### Tests (`tests/backend/test_rbac_and_purge_safety.py`)

- Updated 3 existing tests to match bulk-compatible API contract
- Added 2 new tests: `test_delete_rejects_active_assigned_record`, `test_delete_allows_cancelled_record`
- Total: 9 tests, all passing

## Production Validation Results

| Check | Result |
|-------|--------|
| Total scanned records | 603 |
| Trash count (explicit DELETED/TRASH/DELETE only) | 136 |
| Needs Assignment count | 0 |
| Active records with `deleted_at` in Trash | 0 (none — guardrail working) |
| Backend DELETE guard on ASSIGNED record | ✅ Skipped with correct reason |
| Temporary validation record cleaned up | ✅ |
| Frontend build | ✅ Passed |
| Backend tests | ✅ 44/44 passed |

## Guardrails Enforced

| Guardrail | Status |
|-----------|--------|
| Trash view only shows explicit deleted statuses | ✅ Enforced |
| Active/scheduled records never appear in Trash | ✅ Enforced |
| Purge button only for explicit DELETED/TRASH | ✅ Enforced |
| Bulk purge pre-filters non-DELETED records | ✅ Enforced |
| Needs Assignment count matches click target | ✅ Aligned |
| Backend rejects DELETE on active records | ✅ Enforced |
| Zombie records flagged as data integrity issues | ✅ Enforced |

## Files Changed
- `web/src/components/AdminDashboard.jsx`
- `src/backend/handlers/admin_handler.py`
- `tests/backend/test_rbac_and_purge_safety.py`
