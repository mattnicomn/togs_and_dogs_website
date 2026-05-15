# Release 5: Client & Pet Management Operational Polish — Implementation Plan

**Date:** 2026-05-14  
**Status:** Plan Only — No Implementation Yet  
**Prerequisite:** Releases 1–4E committed and production-validated  
**Objective:** Enable multi-pet editing, pet add/remove/archive, client profile detail improvements, and safe admin cleanup tools.

---

## 1. Current-State Findings

### CareCard Multi-Pet (Post-R4B/R4E)

- **Display:** Pet selector tabs show all PET# records for multi-pet requests ✅
- **Editing:** Only the FIRST pet's data is saved via `handleUpdatePet`. The `formData` state is initialized from `pet` (the merged first-pet object). Switching pet tabs changes `activePet` for display but does NOT update `formData`.
- **Gap:** Editing pet 2 or 3 is not possible. The save flow always writes to `pet.pet_id` (first pet).

### Pet Handler (Backend)

- `PUT /admin/pets/{petId}` already supports editing ANY pet by ID
- `POST /admin/pets` with `pet_id: 'NEW'` creates a new pet for a client
- `is_active` field exists and is editable — can be used for soft-delete/archive
- No DELETE endpoint exists (soft-delete via `is_active: false` is the pattern)

### Client Management (Post-R3)

- Client profiles displayed as cards with search (name, email, phone, pet names, breeds)
- Click card → edit form populates
- Create/onboard flow works
- Disable/enable/unlink/delete actions available
- **Gap:** No way to see a client's pets from Client Management. No pet list per client.
- **Gap:** No way to add a new pet to an existing client from Client Management.

### Data Cleanup

- Test records (R4A validation, R4C validation) were archived via admin UI ✅
- Associated PET# records and client profiles remain (harmless but visible)
- No "archive pet" or "remove pet" action exists in the UI
- Direct DynamoDB edits are the only way to clean up orphaned PET# records currently

---

## 2. Recommended Scope

### 2A. Multi-Pet Editing from CareCard

**Goal:** Allow editing any pet in the pet selector tabs, not just the first.

**Approach:**
- Track `formData` per pet (or reinitialize when switching tabs)
- When saving, use `activePet.pet_id` instead of always using `pet.pet_id`
- The backend already supports `PUT /admin/pets/{petId}` for any pet ID

### 2B. Add New Pet from CareCard or Client Management

**Goal:** Admin can add a new pet to an existing client without going through a new intake request.

**Approach:**
- Add "+ Add Pet" button in CareCard Overview (when multi-pet tabs are shown)
- Opens a mini-form for name, species, breed, age
- Calls `POST /admin/pets` with `pet_id: 'NEW'` and the client's `client_id`
- Backend already supports this

### 2C. Archive/Soft-Delete Pet

**Goal:** Admin can mark a pet as inactive (e.g., pet passed away, no longer in household).

**Approach:**
- Add "Archive Pet" action on each pet tab in CareCard
- Sets `is_active: false` via `PUT /admin/pets/{petId}`
- Archived pets hidden from default display (but recoverable)
- Backend already supports `is_active` field

### 2D. Client Profile Detail — Pet List

**Goal:** When viewing a client in Client Management, show their linked pets.

**Approach:**
- When a client card is selected for editing, fetch their PET# records via existing `GET /admin/pets` or a scan
- Display a simple list: pet name, species, breed, status (active/archived)
- Allow quick navigation to CareCard for each pet

### 2E. Safe Cleanup Tools

**Goal:** Admin can archive or remove test/validation records through normal UI without DynamoDB access.

**Approach:**
- Archived PET# records are already hidden from CareCard display (R4B filters `is_active != false`)
- Add "View Archived Pets" toggle in Client Management detail
- Add "Permanently Delete" for archived pets (calls a new `DELETE /admin/pets/{petId}` endpoint or sets a `deleted` flag)
- For client profiles: existing disable/delete actions already work

---

## 3. Out of Scope

| Item | Reason |
|------|--------|
| Cognito user changes | Not related to pet/client data management |
| Portal access changes | Separate concern |
| Calendar/notification changes | Not related |
| Status/workflow changes | Not related |
| Quote/payment changes | Already done in R4D |
| Staff assignment changes | Already done in R4E |
| Multi-pet intake form changes | Already done in R4A |
| Client auto-profile changes | Already done in R3 |
| Spreadsheet/table view for Client Management | Deferred — card layout with search is sufficient |

---

## 4. Files Likely Affected

### Frontend

| File | Changes |
|------|---------|
| `web/src/components/CareCard.jsx` | Multi-pet editing (formData per pet), add pet button, archive pet action |
| `web/src/components/AdminDashboard.jsx` | Client detail pet list, handleUpdatePet for any pet, add pet flow |

### Backend

| File | Changes |
|------|---------|
| `src/backend/handlers/pet_handler.py` | Add DELETE method or permanent-delete action (optional) |
| `src/backend/handlers/admin_handler.py` | Client detail endpoint to return linked pets (optional — could use existing scan) |

### Backend Changes Assessment

- **Multi-pet editing:** No backend change needed — `PUT /admin/pets/{petId}` already works for any pet
- **Add pet:** No backend change needed — `POST /admin/pets` with `pet_id: 'NEW'` already works
- **Archive pet:** No backend change needed — `PUT /admin/pets/{petId}` with `is_active: false` already works
- **Permanent delete:** Requires new backend logic (either a DELETE method or a `PURGE` action). This is the only backend change.
- **Client pet list:** Could use existing frontend scan of PET# records by client_id, or add a lightweight endpoint

**Recommendation:** Release 5 can be mostly frontend-only (5A–5D). Permanent delete (5E) requires a small backend addition.

---

## 5. Implementation Phases

### Phase 5A: Multi-Pet Editing (Frontend-Only)

- Reinitialize `formData` when `activePetIndex` changes
- Save uses `activePet.pet_id` and `activePet.client_id`
- After save, update `_allPets` array in place

### Phase 5B: Add New Pet (Frontend-Only)

- "+ Add Pet" button in CareCard
- Mini-form: name, species, breed, age
- Calls `createPet({ client_id, name, species, breed, age })`
- Refreshes CareCard pet list

### Phase 5C: Archive Pet (Frontend-Only)

- "Archive" button per pet tab
- Calls `updatePet(petId, clientId, { is_active: false })`
- Removes from display (or shows as greyed out)
- Confirmation prompt before archiving

### Phase 5D: Client Detail Pet List (Frontend, possibly lightweight backend)

- When editing a client in Client Management, show their pets
- Fetch via existing `GET /client/pets` pattern or scan by client_id
- Display: name, species, breed, active/archived status

### Phase 5E: Permanent Delete (Backend + Frontend)

- Add `DELETE /admin/pets/{petId}?clientId={clientId}` to pet_handler
- Only allows deletion of `is_active: false` records (must archive first)
- Owner/admin only
- Frontend: "Delete Permanently" button on archived pets

---

## 6. Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| Multi-pet formData state confusion | Medium | Clear formData on tab switch, use activePet.pet_id for save |
| Accidental pet deletion | Low | Require archive-first, confirmation prompt |
| Orphaned PET# records after delete | Low | Only delete archived pets, no cascade needed |
| Client Management pet list performance | Low | Small pet counts per client (1-5 typical) |
| Backend DELETE endpoint security | Low | Owner/admin RBAC, archive-first guard |

---

## 7. Validation Checklist

| # | Test | Expected |
|---|------|----------|
| 1 | Edit pet 2 in CareCard | Saves to correct PET# record |
| 2 | Switch between pet tabs | formData updates correctly |
| 3 | Add new pet from CareCard | New PET# record created |
| 4 | Archive a pet | is_active set to false, hidden from display |
| 5 | View archived pets (toggle) | Shows greyed-out archived pets |
| 6 | Client Management shows pet list | Pets visible when client selected |
| 7 | Permanent delete (archived pet) | Record removed from DynamoDB |
| 8 | Cannot delete active pet | Blocked — must archive first |
| 9 | Legacy records still work | No regression |
| 10 | npm run build | Passes |
| 11 | py -m py_compile | Passes (if backend changed) |
| 12 | No console/API errors | Clean |

---

## 8. Rollback Approach

| Phase | Rollback |
|-------|----------|
| 5A (multi-pet edit) | Revert CareCard.jsx — first-pet-only editing returns |
| 5B (add pet) | Revert CareCard.jsx — button removed |
| 5C (archive pet) | Revert CareCard.jsx — archive button removed. Archived pets remain (harmless) |
| 5D (client pet list) | Revert AdminDashboard.jsx — pet list hidden |
| 5E (permanent delete) | Revert pet_handler.py — DELETE endpoint removed. Archived pets remain. |

No data cleanup needed on rollback for any phase.
