# Phase 24A-2B — Shared Pet-Field and Validation-Limit Wiring Implementation Plan

**Status:** 🔗 **LOCALLY VALIDATED AND REVIEWED / ALL PLANNED PHASE 24A-2B CUSTOMER PET FIELD AND VALIDATION WIRING COMPLETE / NOT DEPLOYED OR DISTRIBUTED**

**Planning Date:** 2026-07-30  
**Matthew Explicit Approval:** Documentation-only planning was approved on 2026-07-30. The three bounded implementation subphases were subsequently approved, implemented, validated, and independently reviewed.
**Prerequisites:** Phase 24A-2A completed & closed (`863385b`).  

---

## 1. Executive Summary & Purpose

Phase 24A-2B wires the canonical pet field definitions and validation limits exported by `PET_FIELDS` in the generated contract adapters into the web client sanitization helpers and form validation logic.

During Phase 24A-2A, contract adapters (`web/src/generated/contracts.js` and `mobile/src/contracts/generatedContracts.ts`) were generated exporting `PET_FIELDS`. Phase 24A-2B centralizes hardcoded pet property allowlists and field limits in the web client without altering runtime behavior, database schemas, or mobile screens.

---

## 2. Authoritative Project State & Safety Gates

- **Latest Completed Validated Production Release:** Phase 1B.5C-D.2
- **Latest Completed Shared-Contract Phase:** Phase 24A-2A (`863385b`)
- **Phase 1B.5C-A Status:** Deployed and customer-validated.
- **Mobile My Pets Status:** Read-only (`MyPetsScreen.tsx`). Mobile pet editing and creation remain blocked without separate explicit Matthew approval.
- **Phase 24A-2B Status:** Locally validated and independently reviewed. All three planned customer pet-field and validation-wiring subphases are complete; no deployment or distribution occurred.

---

## 3. Contract Semantics & Field Safety Matrix

The canonical contract `shared/constants/pet-fields.json` models client-facing pet properties as follows:

| Field | Customer Read | Customer Write | Staff Read | Staff Create/Update | Shared Contract Export |
|---|---|---|---|---|---|
| `pet_id` | ✅ Yes | ❌ Read-only | ✅ Yes | ❌ Generated | `PET_FIELDS.clientReadFields` |
| `name` | ✅ Yes | ✅ Yes (100) | ✅ Yes | ✅ Yes (100) | `PET_FIELDS.clientReadFields`, `clientWriteFields`, `fieldLimits` |
| `species` | ✅ Yes | ✅ Yes (100) | ✅ Yes | ✅ Yes (100) | `PET_FIELDS.clientReadFields`, `clientWriteFields`, `fieldLimits` |
| `breed` | ✅ Yes | ✅ Yes (100) | ✅ Yes | ✅ Yes (100) | `PET_FIELDS.clientReadFields`, `clientWriteFields`, `fieldLimits` |
| `age` | ✅ Yes | ✅ Yes (100) | ✅ Yes | ✅ Yes (100) | `PET_FIELDS.clientReadFields`, `clientWriteFields`, `fieldLimits` |
| `color` | ❌ Stripped | ❌ Rejected | ✅ Yes | ❌ Unwired | Intentionally Omitted from Client Contract |
| `weight` | ❌ Stripped | ❌ Rejected | ✅ Yes | ❌ Unwired | Intentionally Omitted from Client Contract |
| `care_instructions` | ✅ Yes | ✅ Yes (2000) | ✅ Yes | ✅ Yes (2000) | `PET_FIELDS.clientReadFields`, `clientWriteFields`, `fieldLimits` |
| `feeding_notes` | ✅ Yes | ✅ Yes (2000) | ✅ Yes | ✅ Yes (2000) | `PET_FIELDS.clientReadFields`, `clientWriteFields`, `fieldLimits` |
| `medication_notes` | ✅ Yes | ✅ Yes (2000) | ✅ Yes | ✅ Yes (2000) | `PET_FIELDS.clientReadFields`, `clientWriteFields`, `fieldLimits` |
| `behavior_notes` | ✅ Yes | ✅ Yes (2000) | ✅ Yes | ✅ Yes (2000) | `PET_FIELDS.clientReadFields`, `clientWriteFields`, `fieldLimits` |
| `health.vet_name` | ✅ Yes | ✅ Yes (100) | ✅ Yes | ✅ Yes (100) | `PET_FIELDS.clientWriteHealthSubfields`, `clientWriteHealthFieldLimits` |
| `health.vet_phone` | ✅ Yes | ✅ Yes (100) | ✅ Yes | ✅ Yes (100) | `PET_FIELDS.clientWriteHealthSubfields`, `clientWriteHealthFieldLimits` |
| `vet_notes` | ❌ Stripped | ❌ Rejected | ✅ Yes | ✅ Yes | Staff-Only Field (Unwired) |
| `emergency_notes` | ❌ Stripped | ❌ Rejected | ✅ Yes | ✅ Yes | Staff-Only Field (Unwired) |
| `is_active` | ✅ Yes | ❌ Read-only | ✅ Yes | ✅ Yes | `PET_FIELDS.clientReadFields` |

### Key Safety Observations:
1. `color` and `weight` are NOT included in client read or write allowlists. Backend `sanitize_pet_for_client` strips them.
2. `health` is a nested object containing `vet_name` and `vet_phone`. The helper `sanitizePetDetails` in `web/src/utils/petHelpers.js` sanitizes top-level properties via `clientReadFields` and nested health subfields via `clientWriteHealthSubfields`.
3. Customer write allowlist (`clientWriteFields`) is enforced strictly by backend `PUT /client/pets/{petId}`.

---

## 4. Subphase Breakdown & Bounded Implementation Plan

Phase 24A-2B uses a bounded web read-wiring subphase and two customer validation-limit slices:

### Subphase 24A-2B.1 — Web Customer Pet Read-Allowlist Helper Wiring
- **Status:** Locally validated and reviewed on 2026-07-30.
- **Scope:** Replace hardcoded `CLIENT_SAFE_PET_FIELDS` array in `web/src/utils/petHelpers.js` with `PET_FIELDS.clientReadFields` imported from `web/src/generated/contracts.js`. Update `sanitizePetDetails` to preserve `health` nested subfields (`vet_name`, `vet_phone`).
- **Files Affected:** `web/src/utils/petHelpers.js`, `web/tests/petHelpers.test.jsx`.
- **Targeted Validation:** `npx vitest run tests/petHelpers.test.jsx`, `npx eslint src/utils/petHelpers.js`.
- **Risk:** Extremely Low.

### Subphase 24A-2B.2A — Web Customer Top-Level Validation-Limit Wiring
- **Status:** Locally validated and reviewed on 2026-08-03.
- **Scope:** Wire `PET_FIELDS.fieldLimits` from `web/src/generated/contracts.js` into the eight top-level customer pet controls in `web/src/components/MyPets.jsx`.
- **Files Affected:** `web/src/components/MyPets.jsx`, `web/tests/MyPets.test.jsx`.
- **Targeted Validation:** `npx vitest run tests/MyPets.test.jsx`, `npm run build`.
- **Risk:** Low.

### Subphase 24A-2B.2B — Customer Veterinarian-Field Contract Limits and Web Wiring
- **Status:** Locally validated and reviewed on 2026-08-03.
- **Scope:** Add customer-write-specific `PET_FIELDS.clientWriteHealthFieldLimits` for `vet_name` and `vet_phone`, regenerate existing adapters, validate complete adapter parity, and wire `maxLength` into the two existing MyPets veterinarian controls.
- **Files Affected:** Canonical pet contract, necessary shared validators, generated adapters, focused adapter tests, `web/src/components/MyPets.jsx`, and `web/tests/MyPets.test.jsx`.
- **Non-Goals:** No staff contract or behavior change, mobile application feature change, backend change, payload change, runtime validator, or validation message.
- **Risk:** Low.

---

## 5. Mobile Scope Decision

**Classification:** **`NO_MOBILE_CHANGE_REQUIRED`**

Mobile `MyPetsScreen.tsx` is read-only and displays basic pet properties (`name`, `species`, `breed`, `age`). Mobile pet editing and creation are out of scope and blocked without separate explicit Matthew approval. Zero mobile code changes are required for Phase 24A-2B.

---

## 6. Required Test Strategy & Commands

- **Shared Validators:**
  - `node shared/validate-constants.mjs`
  - `node shared/validate-contract-adapters.mjs`
- **Web Verification:**
  - `npm run test:legacy` (96 tests at Phase 24A-2B.2B independent closeout recount)
  - `npx vitest run` (147 tests at Phase 24A-2B.2B implementation)
  - `npm run build` (Vite production build)
  - `npx eslint src/utils/petHelpers.js`
- **Mobile Regression Checks:**
  - `npm test` (42 tests)
  - `npm run typecheck` (`tsc --noEmit`)

---

## 7. Explicit Exclusions & Rollback Safety

- ❌ **No Mobile Source Changes:** Mobile app source code remains untouched.
- ❌ **No Backend Changes:** Backend handlers (`pet_handler.py`) remain untouched.
- ❌ **No Web Deployment:** Web dist assets will NOT be deployed to S3 or CloudFront.
- ❌ **No EAS Build:** No mobile build or distribution.
- **Rollback Boundary:** Each subphase remains isolated. Phase 24A-2B.2B can be reverted by reverting its canonical contract, validator, regenerated-adapter, focused-test, and MyPets changes together.

## 8. Completion Semantics

Phase 24A-2B consists of exactly Phase 24A-2B.1, Phase 24A-2B.2A, and Phase 24A-2B.2B. All three are locally validated and independently reviewed, so all planned Phase 24A-2B work is complete.

Staff pet-contract work, mobile pet creation or editing, Phase 24A-2C request-status wiring, and Phase 24A-2C service-type wiring are separately scoped work. They are not unfinished Phase 24A-2B subphases. Production deployment, mobile distribution, and Ryan testing also remain separately deferred.
