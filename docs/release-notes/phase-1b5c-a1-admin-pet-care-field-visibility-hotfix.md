# Phase 1B.5C-A.1 — Admin Pet Care Field Visibility Hotfix Record

**Status:** LOCAL HOTFIX IMPLEMENTED / NOT DEPLOYED / AWAITING KIRO RE-REVIEW

**Implementation Date:** 2026-07-28

---

## 1. Production Validation Finding

Following Phase 1B.5C-A deployment, Matthew completed authenticated customer self-service validation on production (`/my-pets`), confirming that customer editing and saving passed successfully and persisted to DynamoDB.

However, during administrative regression validation in Client Management, opening the client pet detail drawer for a pet (`TestPet_ScenarioB`) showed:
- `name: TestPet_ScenarioB`
- `species: POM`
- `Medical Notes: stest`
- `breed: blank`
- `vet fields: blank`
- `behavioral notes: blank`

The admin drawer did **not** display:
- `age` (e.g. `56`)
- `care_instructions` (e.g. `test`)
- `feeding_notes` (e.g. `test`)

Additionally, two active pets shared the exact same name `TestPet_ScenarioB`, making list items visually ambiguous without pet identifier labels.

---

## 2. Audit Root Cause Classification

- **Classification:** `UI_RENDERING_GAP`
- **Findings:**
  - Customer `PUT /client/pets/{petId}` persists `name`, `species`, `breed`, `age`, `care_instructions`, `feeding_notes`, `medication_notes`, `behavior_notes`, `health.vet_name`, `health.vet_phone` to the authoritative `PET#` item in DynamoDB.
  - `GET /admin/pets?clientId={clientId}` returns raw, complete `PET` items containing `age`, `care_instructions`, and `feeding_notes`.
  - In `web/src/components/ClientDetailDrawer.jsx`, `BLANK_PET_FORM`, `mapApiToForm()`, `hasPetUnsavedChanges`, `handlePetSave` payload, and `renderPetSubview()` omitted `age`, `care_instructions`, and `feeding_notes`.
  - Admin selection uses `pet_id` (not name matching); duplicate-name pets were selected correctly, but lacked visual ID labels in the drawer list.
  - Database persistence and backend API endpoints are 100% complete and intact.

---

## 3. Backend Contract Confirmation

Inspected `editable_fields` in `src/backend/handlers/pet_handler.py` (lines 424–435):
- `age`: `ALREADY_SUPPORTED_BY_STAFF_UPDATE` (line 425)
- `care_instructions`: `ALREADY_SUPPORTED_BY_STAFF_UPDATE` (line 425)
- `feeding_notes`: `ALREADY_SUPPORTED_BY_STAFF_UPDATE` (line 433)

**Confirmation:** All three fields are already supported by the existing staff update handler contract. No backend, API Gateway, or Terraform changes are required.

---

## 4. Frontend Correction Scope

Modified `web/src/components/ClientDetailDrawer.jsx`:
1. **Form State:** Extended `BLANK_PET_FORM` and `hasPetUnsavedChanges` to track `age`, `care_instructions`, and `feeding_notes`.
2. **API Mapping:** Extended `mapApiToForm(pet)` to extract `pet.age`, `pet.care_instructions`, and `pet.feeding_notes`.
3. **Save Payload:** Included `age`, `care_instructions`, and `feeding_notes` in `handlePetSave` payload sent to `onPetUpdate`. Preserved non-overwrite of `color`, `weight`, `vet_notes`, and internal keys (`pet_id`, `client_id`, `company_id`, `PK`, `SK`).
4. **Read-Only & Edit Form JSX:**
   - Rendered `Age` field under **Pet Information** section.
   - Rendered new **Care & Feeding** section containing `Care Instructions` and `Feeding Notes` textareas/spans.
   - Preserved `medication_notes` -> `medical_notes` form mapping ("Medical Notes").
   - Preserved `health.vet_name` and `health.vet_phone`.
5. **Duplicate-Name Disambiguation:**
   - Displayed abbreviated Pet ID (e.g. `ID: …a1b2c3`) in the client drawer pet list items and pet view header.
   - Rendered full `pet_id` as React item key `p.pet_id`.

---

## 5. Test Results & Validation Summary

- **Focused Component Tests:** `tests/AdminPetCareFieldVisibility.test.jsx` (8 passed, 0 failed, 0 skipped).
- **Complete Legacy Suite:** `npm run test:legacy` (96 passed, 0 failed, 0 skipped).
- **Complete Component Suite:** `vitest run` (121 passed, 0 failed, 0 skipped across 10 test files).
- **Unique Combined Frontend Total:** **217 passed, 0 failed, 0 skipped, 0 errors**.
- **ESLint:** Clean (0 warnings, 0 errors).
- **Vite Build:** Success in 763ms (`dist/assets/index-Co8a8-_Q.js` 1,046 kB, `dist/assets/index-B_Bar5e4.css` 83.7 kB).
- **Deployment Status:** **NOT DEPLOYED**. Build artifacts remain local only.

---

## 6. Files Changed

- `web/src/components/ClientDetailDrawer.jsx` (Modified)
- `web/tests/AdminPetCareFieldVisibility.test.jsx` (New component test suite)
- `docs/release-notes/phase-1b5c-a1-admin-pet-care-field-visibility-hotfix.md` (New documentation record)

---

## 7. Status

**LOCAL HOTFIX IMPLEMENTED / NOT DEPLOYED / AWAITING KIRO RE-REVIEW**
