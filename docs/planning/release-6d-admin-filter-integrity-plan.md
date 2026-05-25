# Release 6D: Admin Filter Integrity & Safe Delete Guardrails — Plan

## Status: ✅ DEPLOYED & PRODUCTION VALIDATED (2026-05-21)

**Commit:** `ee751c14e33e0cbb1dbd833fdc91ce527463ae92`
**Deployment:** Terraform 9 Lambdas updated + Frontend S3/CloudFront
**Tests:** 44/44 backend tests passed
**Validation:** 603 records scanned, 136 Trash (correct), 0 zombie records, DELETE guard confirmed

## Objective
Fix count/filter mismatches in the Admin Dashboard, prevent active records from appearing in Trash, and add guardrails so purge/delete actions can only affect truly DELETED records.

## Confirmed Issues

### Issue 1: Needs Assignment Count/Navigation Mismatch

**Count logic** (`AdminDashboard.jsx` line ~1944):
```javascript
unassigned: allRequests.filter(r => 
  (r.status === 'APPROVED' || r.status === 'JOB_CREATED') && !r.worker_id && !isDataIssue(r)
).length
```

**Click target** (line ~1951):
```javascript
onClick={() => { setView('LIST'); setStatusFilter('READY_FOR_APPROVAL'); }}
```

**`READY_FOR_APPROVAL` filter predicate** includes:
- CUSTOMER_INTAKE: `READY_FOR_APPROVAL`, `NEW_REQUEST`, `MG_COMPLETED`
- VISIT_BOOKING: `READY_FOR_APPROVAL`, `NEW_REQUEST`, `APPROVED`, `BOOKED`

**Problem:** The count shows APPROVED records without workers (a specific subset), but clicking navigates to a filter that shows a broader/different set. User sees "1" in the card but the filtered list shows different records or a different count.

**Fix:** Either create a dedicated `UNASSIGNED` filter predicate that matches the count logic, or change the count to use `getFilterPredicate('READY_FOR_APPROVAL')`.

---

### Issue 2: Trash Ghost-Record Root Cause

**Current `isDeletedRecord` logic:**
```javascript
const isDeletedRecord = (item) => {
    const s = (item.status || "").toUpperCase();
    return s === 'DELETED' || s === 'TRASH' || s === 'DELETE' || !!item.deleted_at;
};
```

**Problem:** The `!!item.deleted_at` clause means any record with a `deleted_at` timestamp — regardless of its current `status` — is classified as deleted. If a record has `status: ASSIGNED` but also has `deleted_at` set (from a partial/failed operation), it appears in BOTH active views AND Trash.

**AG Pre-Check Result (2026-05-21): CONFIRMED.**
- Found: `REQ#69780136-391f-4a10-8e1b-734812696a36`
- Status: `APPROVED` (active)
- `deleted_at`: exists
- Linked JOB record: already `DELETED`
- Origin: Release 4A/R4A test record, no real client impact
- **Root cause confirmed:** Backend delete operation deleted the child JOB and set `deleted_at` on the parent REQ, but did NOT update the parent's `status` to DELETED. This creates a zombie record that appears in both active views and Trash.

**Fix:** 
1. Frontend: Remove `!!item.deleted_at` from `isDeletedRecord`. Status field is the sole source of truth for Trash visibility.
2. Backend: Ensure DELETE action atomically sets BOTH `status = DELETED` AND `deleted_at` on the target record. Never set `deleted_at` without also updating status.
3. Data cleanup: Fix the zombie record (set status to DELETED or remove `deleted_at`).

---

### Issue 3: Backend Delete Atomicity (Elevated from Optional to Required)

**Root cause:** The backend DELETE action (or a prior cascade operation) set `deleted_at` on the parent REQ record without updating its `status` field. The child JOB was correctly set to DELETED, but the parent was left in APPROVED status with a `deleted_at` marker.

**Impact:** This creates zombie records that:
- Appear in active views (status is APPROVED)
- Also appear in Trash (deleted_at exists)
- Show purge button (isDeletedRecord returns true)
- Could be accidentally purged even though they're "active"

**Fix:** 
- Backend DELETE action must atomically set `status = DELETED` AND `deleted_at = <timestamp>` in a single update expression
- Cascade operations must update parent status when deleting children
- Add validation: if `deleted_at` exists but status is not DELETED/TRASH, treat as data integrity issue (not Trash)

---

### Issue 4: Purge Visibility on Non-DELETED Records

**Current behavior:**
- `PURGE_FOREVER` action is shown when `isDeletedRecord(item)` returns true
- Due to Issue 2, this could show the purge button on active records that have `deleted_at` set
- Backend correctly rejects purge on non-DELETED records, but the UX is confusing and dangerous-looking

**Fix:** Only show PURGE_FOREVER when `item.status` is explicitly `DELETED` or `TRASH`.

---

## Recommended Implementation Phases

### Phase 1: Frontend Filter/Count Alignment
**Scope:** Fix the Needs Assignment stat card to use a consistent predicate for both count and navigation.

**Options:**
- **Option A (Recommended):** Create a dedicated `UNASSIGNED` filter key in `getFilterPredicate` that matches the stat card logic. Update the click handler to navigate to this filter.
- **Option B:** Change the stat card count to use `getFilterPredicate('READY_FOR_APPROVAL')` so count matches what the user sees after clicking.

**Files:** `web/src/components/AdminDashboard.jsx`
**Risk:** Low (frontend-only, no backend changes)
**Effort:** ~1 hour

### Phase 2: Harden Trash/Deleted Record Predicate
**Scope:** Make `isDeletedRecord` use status as the sole source of truth.

**Change:**
```javascript
// Before:
return s === 'DELETED' || s === 'TRASH' || s === 'DELETE' || !!item.deleted_at;

// After:
return s === 'DELETED' || s === 'TRASH' || s === 'DELETE';
```

**Impact:** Records with `deleted_at` but non-DELETED status will no longer appear in Trash. They'll appear in their correct status view instead.

**Files:** `web/src/components/AdminDashboard.jsx`
**Risk:** Low-Medium (may reveal records that were "hidden" in Trash but are actually active)
**Effort:** ~30 minutes + validation

### Phase 3: Frontend Purge Visibility & Bulk Purge Pre-Validation
**Scope:** Ensure purge controls only appear for explicitly DELETED/TRASH records.

**Changes:**
1. In `getWorkflowState`: only include `PURGE_FOREVER` when `status` is explicitly DELETED/TRASH (not relying on `isDeletedRecord` which may change)
2. In `handleBulkPurge`: pre-filter selected items to only include records with explicit DELETED/TRASH status before sending to backend
3. Add a visible warning in the purge confirmation modal showing the record's current status

**Files:** `web/src/components/AdminDashboard.jsx`
**Risk:** Low (adds safety, doesn't remove functionality)
**Effort:** ~1 hour

### Phase 4: Backend Delete Atomicity (REQUIRED — Elevated from Optional)
**Scope:** Ensure DELETE action atomically updates both `status` and `deleted_at`, and add protection against soft-deleting active records.

**Current state:** Backend purge guard is correct — rejects non-DELETED records. But the DELETE (soft-delete) action can set `deleted_at` without updating `status`, creating zombie records.

**AG Evidence:** `REQ#69780136-391f-4a10-8e1b-734812696a36` has `status: APPROVED` + `deleted_at` set. Child JOB is DELETED but parent was left in active status.

**Proposed:**
1. In `admin_handler.py` DELETE action: ensure update expression ALWAYS sets both `status = DELETED` AND `deleted_at = <timestamp>` atomically
2. Reject DELETE action if current status is ASSIGNED, SCHEDULED, or IN_PROGRESS (require CANCEL first)
3. Log a warning when a record is found with `deleted_at` but non-DELETED status
4. Data cleanup: fix the known zombie record

**Files:** `src/backend/handlers/admin_handler.py`
**Risk:** Low (adds safety guard + fixes atomicity gap)
**Effort:** ~1.5 hours

---

## Explicit Guardrails

| Guardrail | Location | Rule |
|-----------|----------|------|
| Trash view exclusivity | Frontend `isDeletedRecord` | Only `status === DELETED/TRASH/DELETE` qualifies — remove `deleted_at` fallback |
| Active record protection | Frontend `isDeletedRecord` | ASSIGNED/SCHEDULED/IN_PROGRESS records must NEVER match `isDeletedRecord` |
| Purge button visibility | Frontend `getWorkflowState` | Only show PURGE_FOREVER when `item.status` is explicitly DELETED or TRASH |
| Bulk purge pre-filter | Frontend `handleBulkPurge` | Filter selected items to explicit DELETED/TRASH status before sending to backend |
| Count/click alignment | Frontend stat cards | Needs Assignment card count and click target must use the same predicate |
| Backend delete atomicity | Backend `admin_handler` | DELETE action must set BOTH `status = DELETED` AND `deleted_at` atomically |
| Backend soft-delete guard | Backend `admin_handler` | Reject DELETE action on ASSIGNED/SCHEDULED/IN_PROGRESS records |
| Zombie detection | Frontend `isDataIssue` | Records with `deleted_at` + non-DELETED status should be flagged as data integrity issues |

---

## AG Validation Plan

### Pre-Implementation (Read-Only)
Scan DynamoDB for records with `deleted_at` set but non-DELETED status:
```cmd
aws dynamodb scan --table-name togs-and-dogs-prod-data --filter-expression "attribute_exists(deleted_at) AND NOT #s IN (:d1, :d2, :d3)" --expression-attribute-names "{\"#s\":\"status\"}" --expression-attribute-values "{\":d1\":{\"S\":\"DELETED\"},\":d2\":{\"S\":\"TRASH\"},\":d3\":{\"S\":\"DELETE\"}}" --projection-expression "PK,SK,#s,deleted_at" --profile usmissionhero-website-prod --region us-east-1 --no-cli-pager
```

This confirms whether ghost-in-Trash records exist and identifies which ones.

### Post-Implementation (Browser Validation)
1. Open Admin Dashboard → Trash filter
   - Count in sidebar must equal number of visible rows
   - No ASSIGNED/SCHEDULED/APPROVED records should appear
2. Open Admin Dashboard → "Needs Assignment" stat card
   - Count must equal number of visible rows after clicking
   - Visible rows must match the card's description ("Approved, no staff")
3. Attempt purge on a record
   - Purge button should only appear for DELETED/TRASH records
   - If somehow triggered on a non-DELETED record, backend should reject
4. Verify no regressions:
   - Active records still appear in correct views
   - Cancelled/Archived records still appear in their sections
   - Scheduler view still excludes terminal statuses

---

## Deferred Items
- Full filter architecture refactor (beyond the specific bugs)
- Server-side pagination alignment with client-side counts
- Real-time WebSocket/polling count sync
- Unrelated UI redesign or layout changes
- Filter predicate unit tests (consider for future CI)

---

## Files Likely Involved

| File | Phase | Change Type |
|------|-------|-------------|
| `web/src/components/AdminDashboard.jsx` | 1, 2, 3 | Filter predicates, count logic, purge visibility |
| `src/backend/handlers/admin_handler.py` | 4 | Optional soft-delete guard |

## Estimated Effort

| Phase | Effort | Risk |
|-------|--------|------|
| Phase 1 | ~1 hour | Low |
| Phase 2 | ~30 min | Low-Medium |
| Phase 3 | ~1 hour | Low |
| Phase 4 | ~1.5 hours | Low |
| Data cleanup | ~15 min | None |
| **Total** | **~4.5 hours** | |

## Deployment
- Phases 1-3: Frontend-only (`npm run build` + S3 sync + CloudFront invalidation)
- Phase 4: Backend (`terraform apply` for Lambda code update)
- Data cleanup: Single DynamoDB update to fix zombie record (AG or Matthew)
- No Terraform infrastructure changes in any phase
