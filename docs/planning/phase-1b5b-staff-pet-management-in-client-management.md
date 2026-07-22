# Phase 1B.5B — Staff Pet Management in Client Management

**Date:** 2026-07-22
**Status:** Planning Complete — Awaiting Matthew Implementation Policy Approval
**Type:** Frontend + bounded backend (delete-reference check)

---

## Objective

Allow admin/owner/staff to add, view, edit, archive, and restore pets for a
selected client directly within the client detail drawer. Provide safe hard-delete
only when no historical references exist.

---

## Staff Capabilities

| Action | Behavior |
|--------|----------|
| Add Pet | Create a new PET record under the selected client |
| View Pet | Show pet details in a subview within the drawer |
| Edit Pet | Modify permitted fields for an existing pet |
| Archive Pet | Set `is_active = false` |
| Restore Pet | Set `is_active = true` |
| Delete Pet | Hard-remove only if zero booking/request references exist |
| Duplicate Warning | Non-blocking alert when same-name pet exists for this client |

---

## UX Model

### Entry Point
The existing client detail drawer Pets section.

### Interaction Flow

1. **Client Drawer → Pets section** shows all pets (active + archived with badges)
2. **"Add Pet" button** transitions drawer content to a pet create form
3. **Selecting a pet** transitions drawer to a pet-detail/edit subview
4. **"Back to Client"** returns to the client overview
5. **No stacked drawers or stacked modals** — single-surface transitions

### State Model

The client drawer gains a `petSubview` state:
- `null` — default client overview (current behavior)
- `{ mode: 'view', petId: '...' }` — pet detail
- `{ mode: 'edit', petId: '...' }` — pet edit form
- `{ mode: 'create' }` — new pet form

### Unsaved-Change Protection
Same pattern as client edit: compare form values against initial values, prompt on close/back/switch if dirty.

### Focus Management
- Transitioning to a pet subview moves focus to the subview heading or first input
- Back to Client restores focus to the Pets section or triggering element
- Escape still routes through the close-with-dirty-check path

---

## Lifecycle Policy

| Action | Rule |
|--------|------|
| **Archive** | Default removal. Pet hidden from new bookings, visible in admin with "Archived" badge. |
| **Restore** | Returns to active inventory. Duplicate warning if another active pet shares the name. |
| **Hard Delete** | Permitted ONLY when no REQ record's `pet_ids` array contains this pet_id. |
| **Delete Denied** | If references exist: show message "This pet has booking history and cannot be deleted. Archive instead?" |
| **Client Archive** | Does NOT cascade to pets. Archived client's pets remain intact. |
| **Ownership Reassignment** | Deferred (not in Phase 1B.5B scope). |
| **Duplicate** | Warning only, no auto-merge. |
| **Photos** | Deferred. |

---

## Backend Impact Assessment

### Existing Routes (No Changes Needed)

| Route | Method | Purpose | Status |
|-------|--------|---------|--------|
| `GET /admin/pets?clientId={id}` | GET | List client's pets | ✅ Exists |
| `GET /admin/pets/{petId}?clientId={id}` | GET | Get single pet | ✅ Exists |
| `POST /admin/pets` | POST | Create pet | ✅ Exists |
| `PUT /admin/pets/{petId}` | PUT | Update pet (including is_active toggle) | ✅ Exists |

### New Route Needed

| Route | Method | Purpose | Implementation |
|-------|--------|---------|----------------|
| `GET /admin/pets/{petId}/references?clientId={id}` | GET | Check if any REQ references this pet_id | New endpoint needed |

OR alternatively, the delete-eligibility check can be performed as a pre-delete validation within the existing PUT handler (set a `delete_requested: true` flag and return success/denied).

**Recommended approach:** Add a lightweight reference-check endpoint that queries REQ records containing the pet_id in their `pet_ids` array. Returns `{ "has_references": true/false, "reference_count": N }`. This keeps delete logic explicit and auditable.

**Alternative (simpler, no new route):** The frontend can call `DELETE /admin/pets/{petId}?clientId={id}` and the backend returns 409 Conflict if references exist. This requires adding a DELETE handler to `pet_handler.py`.

**Recommended decision for Matthew:** Add a `DELETE /admin/pets/{petId}` handler that:
1. Validates tenant ownership
2. Checks for booking references (Scan REQ records for pet_id in pet_ids)
3. Returns 409 if references exist
4. Deletes the item if no references
5. Rebuilds `pet_names_summary` on the client profile

---

## Form Fields (Staff)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| name | text | ✅ | Display name |
| species | text | No | Dog, Cat, etc. |
| breed | text | No | Breed description |
| age | text | No | Age description |
| care_instructions | textarea | No | General care notes |
| feeding_notes | textarea | No | Feeding schedule |
| medication_notes | textarea | No | Medications |
| behavior_notes | textarea | No | Temperament |
| vet_notes | textarea | No | Vet info (staff-only) |
| emergency_notes | textarea | No | Emergency contacts (staff-only) |
| is_active | toggle/badge | — | Controlled via Archive/Restore buttons |

Fields NOT in the form (auto-managed):
- pet_id, client_id, company_id, entity_type, PK, SK
- created_at, updated_at
- created_from_request_id
- meet_and_greet_completed (separate admin toggle)
- internal_pricing_notes, quote_amount (deferred to CareCard workflow)

---

## Duplicate Warning

When creating or saving a pet, check:
1. Same `client_id`
2. Same normalized `name` (case-insensitive, trimmed)
3. Optionally same `species`

If a match exists among active pets:
- Show a non-blocking warning: "A pet named '{name}' already exists for this client. Save anyway?"
- User can proceed or cancel
- No automatic merge or deletion

Implementation: frontend-side check against the already-loaded `clientPets` array (no extra API call needed).

---

## Testing Strategy

### Backend Tests

| # | Test | Validates |
|---|------|-----------|
| 1 | DELETE with zero references succeeds | Happy path |
| 2 | DELETE with booking references returns 409 | Safety guard |
| 3 | DELETE validates tenant ownership | Tenant isolation |
| 4 | DELETE cross-tenant denied | Security |
| 5 | DELETE non-existent pet returns 404 | Edge case |
| 6 | Existing POST/PUT unchanged | No regression |

### Frontend Component Tests

| # | Test | Validates |
|---|------|-----------|
| 1 | Add Pet button shows create form | UX flow |
| 2 | Create form requires name | Validation |
| 3 | Successful create returns to client overview | Lifecycle |
| 4 | Pet click shows detail/edit subview | Navigation |
| 5 | Edit form prepopulates | Data binding |
| 6 | Save updates pet in list | Refresh |
| 7 | Archive toggles is_active | State change |
| 8 | Restore toggles is_active | State change |
| 9 | Delete shows confirmation | Safety |
| 10 | Delete denied shows archive suggestion | Guard |
| 11 | Back to Client returns to overview | Navigation |
| 12 | Dirty form prompts on Back | Unsaved protection |
| 13 | Duplicate warning appears | Duplicate detection |
| 14 | No Client Management regression | Stability |
| 15 | No staff-management regression | Stability |
| 16 | No /my-pets regression | Stability |
| 17 | Tenant isolation in create/edit | Security |
| 18 | Stale drawer request ignored | Race condition |

### Manual Smoke

1. Add pet under a client → appears in list
2. Edit pet → changes persist
3. Archive pet → badge changes
4. Restore pet → returns to active
5. Delete pet (no references) → removed
6. Delete pet (with references) → denied message
7. Mobile drawer behavior during pet editing
8. Keyboard navigation
9. No production data created during smoke (use existing test data)

---

## Implementation Sequence

| Phase | Scope | Files | Gate |
|-------|-------|-------|------|
| 1 | Backend DELETE handler with reference check | `pet_handler.py`, backend tests | Matthew approves this plan |
| 2 | Frontend pet subview state model | `ClientDetailDrawer.jsx`, `AdminDashboard.jsx` | AG implements |
| 3 | Add Pet form and create flow | `ClientDetailDrawer.jsx` | AG implements |
| 4 | Edit Pet form and save flow | `ClientDetailDrawer.jsx` | AG implements |
| 5 | Archive/Restore toggle | `ClientDetailDrawer.jsx` | AG implements |
| 6 | Delete with reference guard | `ClientDetailDrawer.jsx` | AG implements |
| 7 | Duplicate warning | `ClientDetailDrawer.jsx` | AG implements |
| 8 | Component tests | `web/tests/` | AG implements |
| 9 | Kiro review | — | Kiro |
| 10 | Production deployment | Terraform + S3/CF | Matthew approves |

---

## Customer Self-Service (Deferred to Phase 1B.5C)

Client-facing pet editing (/my-pets) is NOT included in Phase 1B.5B.

Recommended client-editable fields (for future reference):
- name, species, breed, age
- care_instructions, feeding_notes, medication_notes, behavior_notes

Client restrictions:
- No ownership reassignment
- No hard delete (request-based only)
- No staff-only notes (vet_notes, emergency_notes, internal_pricing_notes)
- No administrative fields
- Archive/removal should be request-based or separately designed

---

## Explicit Exclusions

- ❌ No customer self-service pet editing (deferred to 1B.5C)
- ❌ No pet ownership reassignment
- ❌ No duplicate auto-merge
- ❌ No pet photos
- ❌ No legacy data migration
- ❌ No global Admin Pet Management tab (deferred to 1B.5D)
- ❌ No booking-integration changes (deferred to 1B.5E)
- ❌ No second-tenant creation
- ❌ No Stripe, Google Calendar, or mobile changes
