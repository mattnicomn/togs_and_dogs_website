# Phase 24A-2C.1B Web Request-Status Display Compatibility Wiring Release Notes

## 1. Executive Summary & Status

- **Status:** **PHASE 24A-2C.1B LOCALLY COMPLETE / WEB REQUEST-STATUS DISPLAY WIRING IMPLEMENTED / CONTEXTUAL & WORKFLOW LABELS PRESERVED / DEDICATED COMPATIBILITY SUITE ADDED / INDEPENDENTLY REVIEWED (KIRO: IMPLEMENTATION_CORRECT) / COMMITTED AND PUSHED / NOT DEPLOYED**
- **Date:** 2026-08-07
- **Implementation Commit SHA:** `2a7959e06367681527cc784f448663521ae030a8` (`feat: wire request status display labels`)
- **Starting Checkpoint:** `a2cce53f7047a871f949bf9f3e645d6f114de47d` (main branch)
- **Base Commit:** `docs: finalize request status continuity state`
- **Scope:** Tightly bounded three-file local web implementation candidate (`ClientPortal.jsx`, `MasterScheduler.jsx`, `RequestStatusDisplayCompatibility.test.jsx`).
- **Kiro Independent Review:** Returned `IMPLEMENTATION_CORRECT` with disposition `READY_FOR_PHASE_24A_2C_1B_COMMIT_DECISION`.
- **Runtime Consumer Boundary:** Wired generated `REQUEST_STATUSES` into customer portal (`ClientPortal.jsx`) for exact-match entries and Intake Queue status pills (`MasterScheduler.jsx`). Preserved client-facing contextual overrides (`MG_SCHEDULED` → `"M&G Scheduled"`, `ASSIGNED` → `"Scheduled"`, `CANCELLATION_REQUESTED` → `"Cancellation Pending"`), MasterScheduler status filter dropdown options, CareCard status transition options, AdminDashboard workflow-sensitive labels, descriptions, colors, backgrounds, and fallbacks.
- **Deployment Boundary:** **NOT DEPLOYED**. Latest validated production baseline remains Phase 1B.5C-D.2.

---

## 2. Three-File Implementation Scope

The local implementation commit contains **exactly three files**:

### Modified Existing Web Component Files (2)
1. `web/src/components/ClientPortal.jsx` (Imported generated `REQUEST_STATUSES` contract adapter; updated `getStatusDisplay(status)` to source canonical request-status labels where visible text is semantically identical while preserving contextual overrides, alias display wording, descriptions, colors, backgrounds, and fallbacks).
2. `web/src/components/MasterScheduler.jsx` (Imported generated `REQUEST_STATUSES` contract adapter; updated Intake Queue status pill text from `req.status.replace(/_/g, ' ')` to `REQUEST_STATUSES.statuses?.[req.status]?.label || req.status.replace(/_/g, ' ')` while leaving the status filter dropdown options completely untouched).

### New Dedicated Test File (1)
3. `web/tests/RequestStatusDisplayCompatibility.test.jsx` [NEW] (Dedicated Vitest test suite verifying exact-match canonical status display, contextual overrides, synonym mappings, unknown status fallbacks, Intake Queue pill text, and MasterScheduler filter dropdown preservation).

---

## 3. Contextual & Local Preservations

The following intentional contextual overrides and local behaviors were strictly preserved:

### ClientPortal Customer Overrides
- `MG_SCHEDULED` → `"M&G Scheduled"` (Abbreviated for tight card layout; canonical is `"Meet & Greet Scheduled"`)
- `ASSIGNED` → `"Scheduled"` (Hides internal staff term `"Assigned"` from customer for visit clarity)
- `CANCELLATION_REQUESTED` → `"Cancellation Pending"` (Customer-facing review phrasing; canonical is `"Cancellation Requested"`)
- `QUOTED` → `"Quoted"` (Synonym display label)
- `SCHEDULED` → `"Scheduled"` (Synonym display label)
- Descriptions (`msg`), colors (`color`), background styles (`bg`), and unknown status fallback (`s.replace(/_/g, ' ')`) were preserved 100%.

### MasterScheduler Filter Dropdown Preservations
- `ALL` → `"All Active"`
- `ASSIGNED` → `"Scheduled"`
- `IN_PROGRESS` → `"In Progress"`
- `COMPLETED` → `"Completed"`
- `CANCELLED` → `"Canceled"` (Single "l" spelling in MasterScheduler UI preserved)
- `RESCHEDULED` → `"Rescheduled"`

### Excluded Web Components
- `CareCard.jsx`: Preserved admin status transition `<optgroup>` options (`"Needs Review"`, `"Approved / Booked"`, `"Trash (Soft)"`).
- `AdminDashboard.jsx`: Preserved dynamic `getStatusLabel` helper discriminating `CUSTOMER_INTAKE` vs `VISIT_BOOKING` workflows (`"New Registration"` vs `"New Request"`, `"Onboarding Ready"` vs `"Booking Ready"`, `"Approved Client"` vs `"Approved / Ready to Schedule"`).

---

## 4. Verification Results

All validation suites passed cleanly prior to commit:

1. **Shared Constants Validator:** `node shared/validate-constants.mjs` → 18/18 passed
2. **Contract Adapters Validator:** `node shared/validate-contract-adapters.mjs` → 9/9 passed
3. **Backend Parity Test:** `py -m pytest tests/backend/test_phase24a_request_status_contract_parity.py -q -p no:cacheprovider` → 13/13 passed
4. **Focused Compatibility Suite:** `RequestStatusDisplayCompatibility.test.jsx` → 7/7 passed
5. **Full Web Vitest Suite:** `npm test --prefix web -- --run` → 238/238 passed across 20 test files
6. **Git Diff Check:** `git diff --check` → Clean (0 formatting errors)

---

## 5. Continuity & Deployment Rules

- **Production Deployment Status:** Phase 24A-2C.1B is committed and pushed to `main` (`origin/main`). It remains **NOT DEPLOYED**.
- **Production Baseline:** Production baseline remains Phase 1B.5C-D.2.
- **Domain Separation:** Request status (`REQUEST_STATUSES`) and Job domain status (`JobStatus`) remain strictly decoupled.
- **Gating:** Next phase (Phase 24A-2C.1C Mobile Request-Status Display Compatibility Wiring or follow-on subphases) remains separately gated.
