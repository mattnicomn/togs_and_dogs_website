# Phase 24A-2C.1 Request-Status Contract & Display Wiring Implementation Plan

## 1. Status and Authorization

**Status:** **PHASE 24A-2C.1A LOCALLY COMPLETE / 17 REQUEST-STATUS LABELS ADDED / REQUEST-STATUS CONTRACT AND ADAPTER PARITY HARDENED / DEDICATED CHARACTERIZATION TESTS ADDED / DOCUMENTED, COMMITTED, AND PUSHED / NO RUNTIME CONSUMER WIRING / NOT DEPLOYED**

- **Planning Date:** 2026-08-05
- **Implementation & Review Date:** 2026-08-05
- **Commit Date:** 2026-08-06
- **Commit SHA:** `5f27b282b1a638ffd641fbef598623351cb9da42` (`feat: add request status labels and parity validation`)
- **Matthew's Approval Boundary:** Phase 2C.1A implementation is locally complete, validated, independently reviewed, committed, and pushed to `origin/main`. No application code, backend handlers, persistence, calendar behavior, notifications, web consumers, mobile consumers, infrastructure, dependencies, production data, or production systems were modified. Future consumer wiring (2C.1B/2C.1C) remains unapproved and undeployed.
- **Latest Validated Production Baseline:** Phase 1B.5C-D.2.
- **Latest Completed Local Closeout:** Phase 24A-2C.2D.4 (Optional Google Calendar Color Metadata Assessment Closeout).

---

## 2. Current Domain Model

The codebase currently maintains two distinct lifecycle status domains connected by a one-directional cascade utility:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        REQUEST STATUS DOMAIN                           │
│   Authority: shared/constants/request-statuses.json (17 statuses)     │
│              src/backend/common/status.py (RequestStatus)              │
│                                                                        │
│   Intake & Onboarding: PENDING_REVIEW, MEET_GREET_REQUIRED,            │
│                         MG_SCHEDULED, MG_COMPLETED, PROFILE_CREATED,   │
│                         READY_FOR_APPROVAL                             │
│   Quoting & Approval:   QUOTE_NEEDED, QUOTE_SENT, APPROVED, DECLINED   │
│   Booking & Execution:  ASSIGNED, CANCELLATION_REQUESTED,              │
│                         CANCELLATION_DENIED, CANCELLED, COMPLETED      │
│   Archival & Removal:   ARCHIVED, DELETED                              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                       REQ → JOB Cascade Utility
                     (src/backend/common/cascade.py)
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          JOB STATUS DOMAIN                             │
│   Authority: src/backend/common/status.py (JobStatus)                 │
│                                                                        │
│   Execution Lifecyle:   JOB_CREATED, ASSIGNED, COMPLETED,              │
│                         CANCELLED, ARCHIVED, DELETED                   │
└────────────────────────────────────────────────────────────────────────┘
```

### Domain Boundary Principles
1. **Request Status Domain (`REQ#` items):** Manages customer intake, meet-and-greet requirements, quoting, customer/admin approval, cancellation requests, and overall booking lifecycle across exactly **17 canonical request statuses**.
2. **Job Status Domain (`JOB#` items):** Manages staff dispatch, worker assignment, visit execution, and job completion.
3. **Domain Separation:** Shared identifier names (such as `ASSIGNED`, `COMPLETED`, `CANCELLED`, `ARCHIVED`, `DELETED`) do not make the domains identical. Request status is not a universal lifecycle enum, and job status is not customer intake state.
4. **Scope Boundary:** Future job-status contract work is separate, unapproved, and out of scope for Phase 24A-2C.1.

---

## 3. Existing Request-Status Contract

The canonical cross-platform request status contract exists in `shared/constants/request-statuses.json`. Inspection confirms it contains **exactly 17 canonical request statuses** in the following exact order:

1. `PENDING_REVIEW`
2. `MEET_GREET_REQUIRED`
3. `MG_SCHEDULED`
4. `MG_COMPLETED`
5. `PROFILE_CREATED`
6. `READY_FOR_APPROVAL`
7. `QUOTE_NEEDED`
8. `QUOTE_SENT`
9. `APPROVED`
10. `ASSIGNED`
11. `DECLINED`
12. `CANCELLATION_REQUESTED`
13. `CANCELLATION_DENIED`
14. `CANCELLED`
15. `COMPLETED`
16. `ARCHIVED`
17. `DELETED`

```json
{
  "_contract": "Togs & Dogs request status identifiers",
  "_version": "24A-2",
  "_authority": "src/backend/common/status.py (RequestStatus enum)",
  "_note": "Machine identifiers only. Display labels are platform-specific due to workflow-context sensitivity on web.",
  "statuses": {
    "PENDING_REVIEW": { "category": "neutral", "terminal": false, "customerVisible": true, "staffSettable": false, "synonyms": ["NEEDS_REVIEW"] },
    "MEET_GREET_REQUIRED": { "category": "informational", "terminal": false, "customerVisible": false, "staffSettable": true, "synonyms": ["NEEDS_MG"] },
    "MG_SCHEDULED": { "category": "informational", "terminal": false, "customerVisible": false, "staffSettable": true, "synonyms": [] },
    "MG_COMPLETED": { "category": "informational", "terminal": false, "customerVisible": false, "staffSettable": true, "synonyms": [] },
    "PROFILE_CREATED": { "category": "informational", "terminal": false, "customerVisible": false, "staffSettable": true, "synonyms": [] },
    "READY_FOR_APPROVAL": { "category": "informational", "terminal": false, "customerVisible": false, "staffSettable": true, "synonyms": ["NEW_REQUEST"] },
    "QUOTE_NEEDED": { "category": "informational", "terminal": false, "customerVisible": false, "staffSettable": true, "synonyms": [] },
    "QUOTE_SENT": { "category": "informational", "terminal": false, "customerVisible": true, "staffSettable": true, "synonyms": ["QUOTED"] },
    "APPROVED": { "category": "success", "terminal": false, "customerVisible": true, "staffSettable": true, "synonyms": ["BOOKED"] },
    "ASSIGNED": { "category": "success", "terminal": false, "customerVisible": true, "staffSettable": true, "synonyms": ["JOB_CREATED", "SCHEDULED"] },
    "DECLINED": { "category": "danger", "terminal": true, "customerVisible": true, "staffSettable": true, "synonyms": [] },
    "CANCELLATION_REQUESTED": { "category": "warning", "terminal": false, "customerVisible": true, "staffSettable": false, "synonyms": [] },
    "CANCELLATION_DENIED": { "category": "warning", "terminal": false, "customerVisible": true, "staffSettable": true, "synonyms": [] },
    "CANCELLED": { "category": "danger", "terminal": true, "customerVisible": true, "staffSettable": true, "synonyms": [] },
    "COMPLETED": { "category": "success", "terminal": true, "customerVisible": true, "staffSettable": true, "synonyms": [] },
    "ARCHIVED": { "category": "neutral", "terminal": true, "customerVisible": false, "staffSettable": true, "synonyms": [] },
    "DELETED": { "category": "neutral", "terminal": true, "customerVisible": false, "staffSettable": true, "synonyms": [] }
  },
  "categories": ["neutral", "informational", "success", "warning", "danger"]
}
```

### Contract Key Inventory & Evidence Confirmation
- **17 Canonical Keys (Confirmed):** Exactly 17 entries exist under `statuses`.
- **Existing Fields:** `category`, `terminal`, `customerVisible`, `staffSettable`, `synonyms`.
- **Current Absence of `label`:** Inspection confirms friendly `label` strings are currently **absent** from all 17 canonical entries in `request-statuses.json`.

---

## 4. Generated Adapters and Generator Behavior

- **Web Adapter:** `web/src/generated/contracts.js` (`export const REQUEST_STATUSES = { ... }`)
- **Mobile Adapter:** `mobile/src/contracts/generatedContracts.ts` (`export const REQUEST_STATUSES = { ... }`)
- **Generator Source Behavior (`shared/generate-contract-adapters.mjs`):**
  Inspection confirms the generator reads `request-statuses.json`, cleans internal `_` metadata keys, and serializes the complete cleaned `REQUEST_STATUSES` object into web and mobile output files using `JSON.stringify(cleanStatuses, null, 2)` (lines 137 & 165).
  Therefore, adding a canonical `label` property to `request-statuses.json` will automatically flow into web and mobile generated adapters upon running `node shared/generate-contract-adapters.mjs`, **without modifying `shared/generate-contract-adapters.mjs`**.
- **Backend Adapter:** No backend generated request-status adapter (`generated_request_statuses.py`) currently exists. Backend adapter generation is a separate future phase.

---

## 5. Backend Authority

Backend transition logic and status definitions are located in `src/backend/common/status.py`:

- **Enums:** `RequestStatus` (21 constants including synonyms) and `JobStatus` (6 constants).
- **Transition Rules:** `REQUEST_TRANSITIONS` and `JOB_TRANSITIONS` dictionaries.
- **Validation Helper:** `is_valid_transition(entity_type, current_status, new_status)` in `src/backend/common/status.py` enforces transitions in `/admin/review` (`review_handler.py`).
- **Workflow Heuristic:** `determine_workflow_type(item)` classifies items into `CUSTOMER_INTAKE` vs `VISIT_BOOKING`.
- **Audit Trail:** Every status change appends a `STATUS_CHANGE` entry to the record's `audit_log` array in DynamoDB.
- **Role Restrictions:** Only `owner` and `admin` roles can perform sensitive transitions (`APPROVED`, `BOOKED`, `DECLINED`, `CANCELLED`, `ARCHIVED`, `DELETED`).

Backend transition authority remains unchanged in Phase 24A-2C.1.

---

## 6. Request-to-Job Cascade

Cascade logic is located in `src/backend/common/cascade.py`:

- **Function:** `cascade_status_to_job(request_item, new_req_status, updated_by, remove_worker)`
- **Direction:** Strictly one-directional (REQ → JOB ONLY) to prevent feedback loops.
- **Mapping:**
  - `APPROVED` / `BOOKED` / `PENDING_REVIEW` → `JOB_CREATED`
  - `ASSIGNED` / `CANCELLATION_DENIED` → `ASSIGNED`
  - `COMPLETED` → `COMPLETED`
  - `CANCELLED` / `CANCELLATION_REQUESTED` → `CANCELLED`
  - `ARCHIVED` → `ARCHIVED`
  - `DELETED` → `DELETED`

Cascade mapping represents runtime workflow execution policy, not display metadata. Cascade logic is excluded from the first implementation slice.

---

## 7. Calendar and Notification Boundaries

### Google Calendar Integration (`src/backend/common/google_calendar.py`)
- Calendar events are created/updated when REQ status is `APPROVED`, `ASSIGNED`, or `COMPLETED`.
- Calendar events are removed when status is changed to `CANCELLED`, `ARCHIVED`, or `DELETED`.

### Notification Service (`src/backend/common/notifications/service.py`)
- `REQUEST_RECEIVED` email sent when public intake request is created (`PENDING_REVIEW`).
- `CUSTOMER_APPROVED` email sent on transition to `APPROVED`.
- `STAFF_ASSIGNED` and `VISIT_SCHEDULED` emails sent on transition to `ASSIGNED`.
- `VISIT_CANCELLED` email sent on transition to `CANCELLED`.

The first implementation slice must not alter calendar triggers, notification routing, notification wording, or event data.

---

## 8. Web Display Duplication

Current status display logic on Web:

1. `web/src/components/ClientPortal.jsx`:
   - Contains local `getStatusDisplay(status)` helper mapping machine keys (`PENDING_REVIEW`, `MEET_GREET_REQUIRED`, `MG_SCHEDULED`, `QUOTE_NEEDED`, `QUOTE_SENT`, `APPROVED`, `ASSIGNED`, `COMPLETED`, `CANCELLED`, `CANCELLATION_REQUESTED`) to display text (`"Pending Review"`, `"Approved"`, `"Scheduled"`, etc.), descriptions, and CSS color tokens.
2. `web/src/components/MasterScheduler.jsx`:
   - Contains status filter dropdown options: `ALL` ("All Active"), `ASSIGNED` ("Scheduled"), `IN_PROGRESS` ("In Progress"), `COMPLETED` ("Completed"), `CANCELLED` ("Canceled"), `RESCHEDULED` ("Rescheduled").
   - Hardcodes active-vs-terminal filter exclusion list (`ARCHIVED`, `DELETED`, `COMPLETED`, `CANCELLED`, `DECLINED`).

### Duplication Separation
- **Display Labels:** Candidates for future canonical metadata consumption (`"Pending Review"`, `"Approved"`, `"Scheduled"`).
- **Workflow Filter Options:** Workflow-specific UI state (`IN_PROGRESS`, `RESCHEDULED`, `ALL`) that remains locally managed.

---

## 9. Mobile Display Duplication

Current status display logic on Mobile:

1. `mobile/src/components/StatusBadge.tsx`:
   - Normalizes input via `(status || '').toUpperCase()`.
   - Renders badges for `APPROVED`, `ASSIGNED`, `SCHEDULED`, `JOB_CREATED`, `CANCELLED`, `REJECTED`, `DECLINED`, `COMPLETED`, `PENDING REVIEW` using React Native theme color tokens.
2. `mobile/src/screens/BookingsScreen.tsx`:
   - Hardcodes local `STATUS_LABEL` and `STATUS_COLOR` dictionaries.

Framework-specific color tokens (React Native styles) remain local to mobile components.

---

## 10. Legacy and Synonym Behavior

### Classification Matrix

| Status String | Classification | Canonical Target | Notes / Handling |
|---|---|---|---|
| `PENDING_REVIEW` | Canonical Key | `PENDING_REVIEW` | Default initial status for public intake |
| `NEEDS_REVIEW` | Contract Synonym | `PENDING_REVIEW` | Synonym in `request-statuses.json` & `status.py` |
| `MEET_GREET_REQUIRED` | Canonical Key | `MEET_GREET_REQUIRED` | Onboarding prerequisite status |
| `NEEDS_MG` | Contract Synonym | `MEET_GREET_REQUIRED` | Synonym in `request-statuses.json` & `status.py` |
| `MG_SCHEDULED` | Canonical Key | `MG_SCHEDULED` | Meet & Greet scheduled |
| `MG_COMPLETED` | Canonical Key | `MG_COMPLETED` | Meet & Greet completed |
| `PROFILE_CREATED` | Canonical Key | `PROFILE_CREATED` | Profile setup complete |
| `READY_FOR_APPROVAL` | Canonical Key | `READY_FOR_APPROVAL` | Ready for admin review |
| `NEW_REQUEST` | Contract Synonym | `READY_FOR_APPROVAL` | Synonym in `request-statuses.json` & `status.py` |
| `QUOTE_NEEDED` | Canonical Key | `QUOTE_NEEDED` | Pricing quote required |
| `QUOTE_SENT` | Canonical Key | `QUOTE_SENT` | Pricing quote sent |
| `QUOTED` | Contract Synonym | `QUOTE_SENT` | Synonym in `request-statuses.json` & `status.py` |
| `APPROVED` | Canonical Key | `APPROVED` | Request approved |
| `BOOKED` | Contract Synonym | `APPROVED` | Synonym in `request-statuses.json` & `status.py` |
| `ASSIGNED` | Canonical Key | `ASSIGNED` | Sitter assigned; visit scheduled |
| `SCHEDULED` | UI/Contract Synonym | `ASSIGNED` | Synonym in `request-statuses.json` & `status.py` |
| `DECLINED` | Canonical Key | `DECLINED` | Request declined |
| `CANCELLATION_REQUESTED` | Canonical Key | `CANCELLATION_REQUESTED` | Customer requested cancellation |
| `CANCELLATION_DENIED` | Canonical Key | `CANCELLATION_DENIED` | Admin denied cancellation |
| `CANCELLED` | Canonical Key | `CANCELLED` | Request cancelled |
| `COMPLETED` | Canonical Key | `COMPLETED` | Visit completed |
| `ARCHIVED` | Canonical Key | `ARCHIVED` | Record archived |
| `DELETED` | Canonical Key | `DELETED` | Record soft-deleted |
| `VERIFY_MEET_GREET` | Admin Action Pseudo-Status | N/A | Payload action in `review_handler.py` |
| `IN_PROGRESS` | UI Filter Option | N/A | MasterScheduler UI filter option |
| `RESCHEDULED` | UI Filter Option | N/A | MasterScheduler UI filter option |

Aliases and synonyms are not treated as canonical keys; they are preserved as documented synonym mappings.

---

## 11. Unknown Status Behavior

Current fallback behavior:
- **Web:** `ClientPortal.jsx` falls back to `status.replace(/_/g, ' ')`.
- **Mobile:** `StatusBadge.tsx` falls back to `normalizedStatus || 'PENDING REVIEW'`.
- **Backend:** `determine_workflow_type()` in `status.py` handles unmapped status strings safely.

Phase 24A-2C.1 preserves raw-value fallbacks, exact casing behavior, unknown values, and missing values without trimming, normalization, or rejection.

---

## 12. Production-Data Boundary

1. **Phase 2C.1A (Metadata & Parity Hardening):** Production inspection is **not needed**. Can be implemented and verified locally using synthetic tests against canonical JSON.
2. **Backend Status Allowlist Enforcement:** Production data inspection is **required** before enforcing strict allowlists or rejecting unknown statuses.
3. **Production Data Access:** No production data access is authorized.

---

## 13. Contract Field Decision

### Proposed Field Addition
Add a canonical `label` property to each of the 17 entries in `shared/constants/request-statuses.json`:

```json
"PENDING_REVIEW": {
  "label": "Pending Review",
  "category": "neutral",
  "terminal": false,
  "customerVisible": true,
  "staffSettable": false,
  "synonyms": ["NEEDS_REVIEW"]
}
```

### Rejected First-Slice Additions
- `labelLong` (Unnecessary; status labels are concise)
- CSS colors / Hex codes (Keep styling in frontend theme files)
- React Native style tokens (Keep styling in mobile components)
- `allowedNext` / Transition policy (Transition rules belong in backend code)
- Calendar metadata (Calendar logic belongs in `google_calendar.py`)
- Notification text (Notification templates belong in `notifications/`)
- Job-domain statuses (Job status is a separate domain)

---

## 14. First Implementation Slice (Phase 24A-2C.1A)

### Scope Boundary
Phase 24A-2C.1A is strictly defined as a six-file implementation boundary:
1. Adding canonical `label` strings to `shared/constants/request-statuses.json`.
2. Hardening `shared/validate-constants.mjs` to validate `label` string presence.
3. Adding `REQUEST_STATUSES` deep-equality validation to `shared/validate-contract-adapters.mjs`.
4. Deterministically regenerating Web (`web/src/generated/contracts.js`) and Mobile (`mobile/src/contracts/generatedContracts.ts`) adapters via existing unchanged generator command.
5. Adding a dedicated characterization test suite (`tests/backend/test_phase24a_request_status_contract_parity.py`).

No UI component wiring, backend handler changes, generator script modifications, or backend adapter creations are included in Phase 2C.1A.

---

## 15. Dedicated Test Ownership

Characterization tests for request status contract parity will be placed in a new dedicated test file:
`tests/backend/test_phase24a_request_status_contract_parity.py`

### Test Group Coverage
1. Contract JSON structure and parsing.
2. 17 canonical keys and exact UPPER_SNAKE_CASE formatting.
3. Category values matching allowlist (`neutral`, `informational`, `success`, `warning`, `danger`).
4. Boolean properties (`terminal`, `customerVisible`, `staffSettable`).
5. Synonym array completeness and correctness.
6. Friendly `label` property type and non-empty string validation.
7. Web generated adapter (`REQUEST_STATUSES`) parity.
8. Mobile generated adapter (`REQUEST_STATUSES`) parity.
9. Backend `RequestStatus` enum comparison and documented synonym coverage.
10. Characterization of no runtime enforcement and zero backend handler modifications.

---

## 16. Future Phases

```
Phase 2C.1A: Request-Status Label Metadata & Parity Hardening (Contract + Tests)
   │
   ▼
Phase 2C.1B: Backend Generated Request-Status Adapter
   │  (Extend generator to emit `src/backend/common/generated_request_statuses.py`)
   ▼
Phase 2C.1C: Web Status Display Compatibility
   │  (Wire `REQUEST_STATUSES` labels into `ClientPortal.jsx`)
   ▼
Phase 2C.1D: Mobile Status Display Compatibility
   │  (Wire `REQUEST_STATUSES` labels into `StatusBadge.tsx` and `BookingsScreen.tsx`)
   ▼
Phase 2C.1E: Backend Display Lookup Wiring (Optional / Behavior-Preserving)
   │
   ▼
Phase 2C.1F: Separate Job-Status Contract Planning (Not Implementation)
   │
   ▼
Phase 2C.1G: Status Allowlist & Transition Policy Assessment (Requires Production Data Gate)
```

---

## 17. Six-File First-Slice Implementation Matrix

The Phase 2C.1A implementation boundary consists of **exactly six files**:

### Files Modified (3)
1. `shared/constants/request-statuses.json` (Add `label` string to all 17 canonical entries)
2. `shared/validate-constants.mjs` (Add `label` presence, string type, and non-empty checks)
3. `shared/validate-contract-adapters.mjs` (Add `REQUEST_STATUSES` deep-equality test since repository inspection confirmed it is currently missing)

### Files Regenerated (2)
4. `web/src/generated/contracts.js` (Regenerated adapter carrying new `label` fields)
5. `mobile/src/contracts/generatedContracts.ts` (Regenerated adapter carrying new `label` fields)

### New Dedicated Test File Created (1)
6. `tests/backend/test_phase24a_request_status_contract_parity.py` [NEW] (Parity characterization tests)

### Unchanged Generator Command
- `node shared/generate-contract-adapters.mjs` (Generates web and mobile adapters without generator script edits)

### Explicit Excluded Files
- `shared/generate-contract-adapters.mjs` (Generator source requires no changes)
- `src/backend/handlers/*` (No handler edits)
- `src/backend/common/status.py` (No backend enum or transition edits)
- `src/backend/common/cascade.py` (No cascade edits)
- `src/backend/common/google_calendar.py` (No calendar edits)
- `src/backend/common/notifications/*` (No notification edits)
- `web/src/components/*` (No UI edits in 2C.1A)
- `mobile/src/components/*` (No Mobile UI edits in 2C.1A)

---

## 18. Validation Plan

Verification steps for Phase 24A-2C.1A:

1. **Shared Constants Validator:**
   `node shared/validate-constants.mjs` (All 18 existing checks + new `label` checks pass)
2. **Generator Execution (Unchanged Command):**
   `node shared/generate-contract-adapters.mjs` (Runs cleanly)
3. **Shared Contract Adapters Validator:**
   `node shared/validate-contract-adapters.mjs` (All adapter checks pass including new `REQUEST_STATUSES` deep equality, with zero second diff)
4. **Dedicated Backend Parity Test Suite:**
   `py -m pytest tests/backend/test_phase24a_request_status_contract_parity.py -q -p no:cacheprovider`
5. **Combined Affected Backend Test Suite:**
   `py -m pytest tests/backend/test_phase24a_request_status_contract_parity.py tests/backend/test_phase24a_generated_service_types.py tests/backend/test_phase24a_service_duration_contract_parity.py tests/backend/test_r7e_cancellation.py tests/backend/test_r7g_assignment_multiday.py tests/backend/test_r7d_calendar_hardening.py tests/backend/test_r6g_calendar_all_day.py tests/backend/test_r7e_multi_day_jobs.py -q -p no:cacheprovider`
6. **Zero Code & Test Diff:**
   `git diff --exit-code -- src/backend` (0 changes)
7. **Formatting Check:**
   `git diff --check` (Clean)

---

## 19. Deployment Implications

- **Deployment Impact:** **Zero.** All Phase 24A work remains local-only, unbuilt, and undeployed.
- **Production Safety:** Local validation and documentation closeout do not authorize deployment.

---

## 20. Migration and Record Implications

- **Database Writes:** Zero.
- **Schema Changes:** Zero.
- **Record Normalization / Migration:** Zero.

---

## 21. Risks

1. **Risk:** Conflating Request and Job domains.
   - *Mitigation:* Explicitly document domain separation and limit Phase 2C.1 to Request statuses.
2. **Risk:** Treating synonyms as canonical keys.
   - *Mitigation:* Parity tests characterize exact 17 canonical keys vs documented synonyms.
3. **Risk:** Accidental UI display regression.
   - *Mitigation:* Phase 2C.1A includes zero UI component changes.

---

## 22. Rollback

- **Implementation Rollback:** Standard local `git revert` or `git checkout` restoring prior contract and generated adapters.

---

## 23. Approval Gates

- Planning closeout (This document).
- Phase 2C.1A implementation (Requires explicit Matthew approval).
- Phase 2C.1B backend adapter generation.
- Phase 2C.1C web display compatibility.
- Phase 2C.1D mobile display compatibility.
- Production data assessment & allowlist enforcement (Separate future gate).

---

## 24. Explicit Non-Goals

Phase 24A-2C.1 planning does NOT authorize:
- Modifying backend handler logic, status validation, or transitions.
- Modifying calendar synchronization logic or notification templates.
- Creating a Job status contract or combined status contract.
- Normalizing or rewriting historical DynamoDB status values.
- Enforcing strict status allowlists on API requests.
- Deploying website or backend changes.
- Enabling `TENANT_RESOLUTION_MODE=multi` or creating a second tenant.
