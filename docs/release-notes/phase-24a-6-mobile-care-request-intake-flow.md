# Phase 24A-6 Mobile Care-Request Intake Flow Release Notes

## 1. Executive Summary & Status

- **Status:** **PHASE 24A-6 LOCALLY COMPLETE / MOBILE CARE-REQUEST INTAKE FLOW IMPLEMENTED / 3-STEP INTAKE WIZARD INTEGRATED / CONTRACT-DERIVED CANONICAL SERVICES / READ-ONLY CLIENT PETS LOADED / INDEPENDENTLY REVIEWED (KIRO: IMPLEMENTATION_CORRECT) / COMMITTED AND PUSHED / NOT DEPLOYED**
- **Date:** 2026-08-09
- **Implementation Commit SHA:** `2831205a092ab94b774ac7bcdaada27bea19976e` (`feat: add mobile care request intake flow`)
- **Starting Checkpoint:** `854562067f565b6acd7bccdfd32e2169c87ac140` (main branch)
- **Scope:** Bounded five-file mobile intake implementation (`client.ts`, `AppNavigator.tsx`, `BookingsScreen.tsx`, `IntakeScreen.tsx`, `IntakeScreen.test.tsx`).
- **Kiro Independent Review:** Returned `IMPLEMENTATION_CORRECT` with disposition `READY_FOR_PHASE_24A_6_COMMIT_DECISION`.
- **Runtime Consumer Boundary:** Implemented complete 3-step mobile care request intake wizard (`IntakeScreen.tsx`), integrated navigation route (`AppNavigator.tsx`), added `+ Book Care` and `+ Book Pet Care` buttons (`BookingsScreen.tsx`), added API helper `submitClientRequest` (`client.ts`), and created a 10-test unit suite (`IntakeScreen.test.tsx`).
- **Deployment Boundary:** **NOT DEPLOYED**. Latest validated production baseline remains Phase 1B.5C-D.2. Zero EAS or Expo distribution builds occurred; TestFlight, App Store, and Google Play configurations remain untouched.

---

## 2. Five-File Implementation Scope

The local implementation commit contains **exactly five files**:

### Modified Existing Mobile Source Files (3)
1. `mobile/src/api/client.ts`: Added and exported `submitClientRequest(data: any)` using `API_PATHS.client.submitRequest` (`POST /client/request`) with Cognito authentication.
2. `mobile/src/navigation/AppNavigator.tsx`: Registered `IntakeScreen` route in `ClientStack` / `ClientNavigator`.
3. `mobile/src/screens/BookingsScreen.tsx`: Added `+ Book Care` header button and empty-state booking CTA button navigating to `IntakeScreen`. Added `useNavigation` hook.

### New Mobile Files (2)
4. `mobile/src/screens/IntakeScreen.tsx` [NEW]: Created complete 3-step mobile care-request intake wizard screen matching the web client intake capability (`IntakeForm.jsx`).
5. `mobile/__tests__/IntakeScreen.test.tsx` [NEW]: Created 10-test unit test suite covering options derivation, validation, pet loading, terms agreement, submission payload, error banner, and navigation.

---

## 3. Key Implementation Details

### A. Dynamic Service Options Derivation
- Derived from `SERVICE_TYPES.services` where `availableInIntake === true`.
- Exactly 6 canonical service options are rendered: `WALK_30MIN`, `WALK_60MIN`, `DROPIN_1HR`, `DROPIN_3HR`, `OVERNIGHT`, and `PET_SITTING`.
- `MEET_GREET` has `availableInIntake: false` and is strictly excluded from customer intake UI.

### B. 3-Step Wizard Architecture
1. **Step 1: Care & Schedule:** Service selection chips, upcoming visit dates chip selector + custom `YYYY-MM-DD` input, visit window selection (`MORNING`, `AFTERNOON`, `EVENING`, `ANYTIME`), optional timing notes, and optional preferred sitter selection from `getStaffOptions()`.
2. **Step 2: Pets & Details:** Read-only client pets loaded from `getClientPets()` (`GET /client/pets`), pet selection chips with fallback pet name input, optional feeding/medication notes, and optional vet/emergency contact fields.
3. **Step 3: Review & Policy Agreement:** Full booking summary card and mandatory policy agreement checkbox (`accepted_terms: true`, `accepted_privacy: true`, `terms_version: "1.0"`, `privacy_version: "1.0"`). Success confirmation screen displays the returned `request_id`.

### C. Backend API Integration & Status Contract
- Calls `submitClientRequest(payload)` via `POST /client/request`.
- Client payload does **NOT** assign request status. The backend automatically initializes request status to `PENDING_REVIEW`.

### D. Phase 24A-5 Preservation
- Client pets are read via `getClientPets()` (`GET /client/pets`, Phase 24A-4 read-only contract).
- No pet modification or pet creation endpoints are called, preserving Phase 24A-5 Pet Editing as deferred and gated on Phase 1B.5C-A deployment.

---

## 4. Minor Follow-Up Note (Non-Blocking Observation)

- **UX Polish:** Kiro observed that if a client leaves `clientName` empty, `client_name` currently falls back to `"Valued Client"`. A future minor UX enhancement may replace the fallback with explicit required-name input validation.

---

## 5. Verification Results

All automated test suites executed cleanly prior to commit:

1. **Mobile TypeScript Typecheck:** `npm run typecheck --prefix mobile` → **0 TypeScript errors**
2. **Shared Constants Validator:** `node shared/validate-constants.mjs` → **18/18 passed**
3. **Shared Adapters Validator:** `node shared/validate-contract-adapters.mjs` → **9/9 passed**
4. **Focused Mobile Tests:** `npx jest __tests__/IntakeScreen.test.tsx __tests__/BookingsScreen.test.tsx` → **14/14 passed**
5. **Full Mobile Jest Test Suite:** `npm test --prefix mobile` → **89/89 passed across 10 test suites**
6. **Git Formatting Check:** `git diff --check` → **Clean (0 whitespace errors)**
7. **Git Status:** **Exactly 5 files modified/created**

---

## 6. Deployment & Guardrails Audit

- **Production Deployment:** **NOT DEPLOYED**. Baseline remains Phase 1B.5C-D.2.
- **Mobile Build / Distribution:** Zero EAS or Expo builds performed; TestFlight, App Store, and Google Play remain unchanged.
- **Production Data:** Zero production database records created or modified.
- **Calendar & Notifications:** Zero Google Calendar or Postmark notification calls initiated.
- **Gated Workstreams:** Phase 24A-5 (Pet Editing) remains deferred; Phase 24A-9 remains distribution-gated.
