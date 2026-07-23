# Phase 1B.5 — Pet Management and Client–Pet Association

**Date:** 2026-07-23
**Status:** Phase 1B.5A & 1B.5A.1 CLOSED (Validated 2026-07-22); Phase 1B.5B-A Production Plan Prepared; Phase 1B.5C–E Deferred
**Type:** Full-stack (backend API gaps + frontend implementation)

---

## Objective

Provide one authoritative and safe model for managing saved pets and their client
ownership across the admin portal, client portal, and booking workflow. Introduce
pet create/edit/archive capabilities in the client drawer and client portal while
preserving historical booking references and multi-tenant isolation.

---

## Current Pet Data Architecture

### Entity Schema

| Field | Source | Purpose |
|-------|--------|---------|
| `PK` | `PET#<uuid>` | Primary key |
| `SK` | `CLIENT#<client_id>` | Sort key — encodes client ownership |
| `pet_id` | UUID | Stable identifier (GSI range key) |
| `client_id` | UUID | Owning client (GSI partition key) |
| `company_id` | Tenant ID | Tenant isolation |
| `entity_type` | `'PET'` | Record-type discriminator |
| `name` | String | Display name |
| `species` | String | Dog/Cat/etc |
| `breed` | String | Breed |
| `age` | String | Age description |
| `is_active` | Boolean | Active/archived state |
| `care_instructions` | String | General care notes |
| `feeding_notes` | String | Feeding schedule |
| `medication_notes` | String | Medications |
| `behavior_notes` | String | Temperament |
| `vet_notes` | String | Veterinary info |
| `emergency_notes` | String | Emergency contacts |
| `meet_and_greet_completed` | Boolean | Admin gate |
| `internal_pricing_notes` | String | Staff-only |
| `quote_amount` | Decimal | Staff-only |
| `created_from_request_id` | UUID | Originating request |
| `created_at` / `updated_at` | ISO timestamp | Metadata |

### GSI: ClientPetIndex

- **Partition key:** `client_id`
- **Sort key:** `pet_id`
- **Projection:** ALL

### Client-to-Pet Association

| Mechanism | Type | Notes |
|-----------|------|-------|
| PET SK = `CLIENT#<client_id>` | Authoritative | Stored on every PET record |
| PET `client_id` field | Authoritative | Populates ClientPetIndex GSI |
| Client `pet_names_summary` | Derived/cached | Rebuilt by `_rebuild_pet_summary` |
| Client `pet_breeds_summary` | Derived/cached | Same |
| REQ `pet_ids` array | Reference | Links booking to specific PET records |
| REQ `pet_id` (legacy) | Reference | Legacy single-pet link |

### Current API Routes

| Route | Method | Role | Purpose |
|-------|--------|------|---------|
| `/client/pets` | GET | client | List own active pets (sanitized) |
| `/admin/pets?clientId={id}` | GET | owner/admin | List client's active pets |
| `/admin/pets/{petId}?clientId={id}` | GET | owner/admin/staff | Get single pet |
| `/admin/pets` | POST | owner/admin/staff | Create pet |
| `/admin/pets/{petId}` | PUT | owner/admin/staff | Update pet |

### Booking-to-Pet References

- `pet_ids` array on REQ record (populated on approval or admin-created booking)
- `pet_id` legacy single field (backward compat)
- `pet_names` string on REQ (human-readable, populated at intake)
- Admin bookings require `pet_names` OR `pet_ids`
- PET# records created only on request approval (via `create_or_link_pets_from_request`)

---

## Current-State Association Map

| Entity | Identifier | Client Association | Tenant Association | Referenced By | Source of Truth | Risk |
|--------|-----------|-------------------|-------------------|---------------|----------------|------|
| PET record | `PET#<uuid>` / `CLIENT#<client_id>` | SK + `client_id` field | `company_id` | REQ `pet_ids`, booking, drawer, /my-pets | DynamoDB item | Legacy records may lack `company_id` |
| CLIENT profile | `COMPANY#<cid>` / `CLIENT#<client_id>` | Self | PK prefix | PET SK, REQ SK | DynamoDB item | Stable |
| REQ record | `REQ#<uuid>` / `CLIENT#<client_id>` | SK | `company_id` | JOB records | DynamoDB item | `pet_ids` populated only after approval |
| JOB record | `JOB#<uuid>` / `REQ#<req_id>` | Via parent REQ | Via parent REQ | Scheduler | DynamoDB item | No direct pet reference |
| Client drawer pet list | Derived | Via request `pet_ids` + individual getPet | Via caller | UI only | Derived from requests | May miss pets not linked to any request |
| MyPets (client portal) | API response | Via `resolve_client_identity` | Via auth context | UI only | `/client/pets` API | Only shows active |
| Admin pet list (New Visit) | API response | Via `listAdminClientPets` | Via auth context | New Visit modal | `/admin/pets?clientId` API | Only shows active |

### Identified Risks

1. **Client drawer loads pets from request-derived pet_ids** — resolved in Phase 1B.5A (uses listAdminClientPets)
2. **Legacy records missing `company_id`** — excluded by query filtering (13 known, documented in Phase 1B.2A)
3. **No archive/restore API route** — is_active is toggled via PUT but no dedicated endpoint
4. **No dedicated client-pet-list admin endpoint in the drawer** — resolved in Phase 1B.5A (cutover to listAdminClientPets complete)
5. **No client-facing pet create/edit** — /my-pets is read-only
6. **No duplicate-detection mechanism** for pets with the same name

---

## Phase 1B.5 Workstreams

### Phase 1B.5A — Association and Data-Integrity Foundation

**Scope:** Audit and correct the client-drawer pet loading to use the authoritative `listAdminClientPets` API instead of request-derived pet_ids. This ensures ALL pets for a client are visible regardless of booking history.

**Decisions required:**
- Confirm `client_id` field on the PET record is the authoritative ownership field
- Confirm `ClientPetIndex` is the authoritative query path
- Confirm legacy records missing `company_id` remain excluded (no backfill in this phase)
- Define orphan handling: pet record exists but owning client was deleted → show warning, no auto-delete

**Backend impact:** None — `listAdminClientPets` already exists and uses ClientPetIndex.

**Frontend impact:** Replace the request-derived `Promise.all(getPet(...))` pattern in AdminDashboard with a single `listAdminClientPets(clientId)` call.

### Phase 1B.5B — Client Drawer Pet Editor

**Scope:** From the client detail drawer, provide admin/owner ability to:
- View all saved pets (already done)
- Add Pet (opens pet editor)
- Edit Pet (opens pet editor for existing pet)
- Archive Pet (set `is_active = false`)
- Restore Pet (set `is_active = true`)

**Recommended UX:** Nested drawer panel (slide-in from right over the client drawer) rather than a modal or separate route. Rationale:
- Maintains spatial context (client → pet is a hierarchical relationship)
- Does not lose client drawer state
- Consistent with the stacked-drawer pattern already familiar to the user
- Back button returns to client drawer

**Hard delete:** Only permitted when no bookings reference the pet (no `pet_ids` array contains this pet_id). Otherwise require Archive.

**Fields editable by admin/owner:**
- name, species, breed, age
- care_instructions, feeding_notes, medication_notes, behavior_notes
- vet_notes, emergency_notes
- meet_and_greet_completed, meet_and_greet_notes
- quote_amount, internal_pricing_notes (staff-only where applicable)
- is_active

**Backend impact:** Existing `POST /admin/pets` and `PUT /admin/pets/{petId}` support all needed operations. No new endpoint required.

### Phase 1B.5C — Global Admin Pet Management (DEFERRED — pending Matthew decision)

**Scope:** A dedicated "Pet Management" admin tab with:
- Search across all pets
- Filter by owning client, active/archived, species
- Open pet details
- Navigate to associated client
- Add pet under selected client
- Identify potential duplicates
- Archive/restore

**Backend impact:** May require a new `GET /admin/pets` (all pets, paginated, filterable) endpoint. Current API only supports per-client queries.

**Decision required:** Whether this is included before or after booking integration.

### Phase 1B.5D — Client Portal /my-pets Editing

**Scope:** Allow clients to:
- View their pets (already done)
- Add a new pet
- Edit basic fields (name, species, breed, age, care notes)
- Request archive/deletion (soft request, admin confirms)

**Restricted from clients:**
- internal_pricing_notes, quote_amount, meet_and_greet_notes
- direct is_active toggling (request-only)
- ownership reassignment
- accessing other clients' pets

**Backend impact:** Need a new `POST /client/pets` route (or repurpose existing with role check). Need a `PUT /client/pets/{petId}` route. Backend sanitization must strip staff-only fields from client requests.

### Phase 1B.5E — Booking Integration

**Scope:** When creating a booking (admin or client):
- Select from existing active saved pets
- Allow adding a new pet inline (creates PET# record immediately)
- Reference stable pet_ids in the booking record
- Avoid creating duplicates on repeat requests
- Handle archived pets (show warning, don't include in new bookings)
- Handle multi-pet bookings
- Preserve historical booking references (never remove pet_ids from old bookings)

**Backend impact:** Existing `pet_ids` array on REQ supports this. The `create_or_link_pets_from_request` name-matching logic handles duplicate prevention on approval. May need minor frontend changes to the intake form and New Visit modal.

---

## Lifecycle Policies (Require Matthew Approval)

### Create
- Owning client required
- Tenant (company_id) required
- Stable pet_id assigned (UUID)
- Duplicate warning: if a pet with the same name exists for the same client, show a warning but allow creation

### Edit
- **Admin/owner editable:** all fields
- **Staff editable:** all except `internal_pricing_notes`, `quote_amount`, `meet_and_greet_notes`
- **Client editable:** name, species, breed, age, care notes, feeding, medication, behavior notes
- Booking history must NOT be rewritten (pet_ids on old REQ records remain)
- `updated_at` tracked on every edit

### Archive
- Preferred default for pets with historical bookings
- Archived pets hidden from new booking selection
- Historical booking records remain readable
- Archived pets still visible in admin pet list (with "Archived" badge)
- Archived pets hidden from client /my-pets

### Restore
- Return to active client inventory
- Duplicate warning if another active pet has the same name

### Delete (Hard)
- Allowed ONLY when no REQ record references the pet_id in its `pet_ids` array
- Requires owner/admin role
- Requires explicit confirmation
- Otherwise: forced to Archive

### Reassignment
- Moving a pet to another client requires:
  - Owner role (not admin, not staff)
  - Explicit confirmation dialog
  - Both source and target clients must belong to the same tenant
  - Audit event logged
  - Historical booking references preserved (old REQ records keep the original pet_id)
  - `pet_names_summary` rebuilt on both source and target client profiles
- **Recommendation: DEFER reassignment to a later phase unless Matthew prioritizes it**

---

## Backend Impact Assessment

| Capability | Status | Phase |
|-----------|--------|-------|
| List client pets (admin) | ✅ Existing | — |
| List client pets (client) | ✅ Existing | — |
| Get single pet | ✅ Existing | — |
| Create pet (admin) | ✅ Existing | — |
| Update pet (admin) | ✅ Existing | — |
| Archive pet (admin) | ✅ Existing (PUT with is_active=false) | — |
| Create pet (client) | ❌ Missing route | 1B.5D |
| Update pet (client) | ❌ Missing route | 1B.5D |
| List all pets (admin global) | ❌ Missing route | 1B.5C |
| Check booking references before delete | ❌ Missing | 1B.5B |
| Reassign pet ownership | ❌ Missing | Deferred |
| Drawer pet loading fix | Frontend-only | 1B.5A |

---

## Security and Multi-Tenant Requirements

- ✅ Tenant-scoped reads via ClientPetIndex + company_id filter (already implemented)
- ✅ Tenant-scoped writes via GetItem client ownership check (already implemented)
- ✅ Cross-tenant client assignment prevented (existing validation)
- ✅ Role-based authorization (owner/admin/staff for admin routes, client for client routes)
- ✅ Staff cannot write sensitive fields (existing sanitization)
- ✅ No raw identifiers logged on denial (existing pattern)
- ✅ TENANT_RESOLUTION_MODE remains unchanged
- ⬜ Client-facing pet routes need same tenant validation (new in 1B.5D)
- ⬜ Audit events for ownership changes (new in reassignment, deferred)

---

## Testing Strategy

### Backend Tests
- Client-to-pet query returns only owned pets
- Tenant isolation (cross-company rejected)
- Archive sets is_active=false
- Restore sets is_active=true
- Delete blocked when bookings reference pet
- Client create/edit route validation (1B.5D)
- Staff field sanitization

### Component Tests
- Client drawer pet list loads via listAdminClientPets
- Add Pet opens nested editor
- Edit Pet populates form
- Save creates/updates correctly
- Archive/restore toggle
- Delete confirmation + booking-reference guard
- Back returns to client drawer
- Loading and error states
- Client /my-pets add and edit (1B.5D)
- Booking pet selection (1B.5E)

### Manual Smoke
- Desktop nested pet drawer
- Mobile pet editor behavior
- Keyboard navigation
- Real client with real pets
- No unintended production mutations

---

## Implementation Sequence

| Phase | Scope | Type | Likely Files | Gate |
|-------|-------|------|-------------|------|
| 1B.5A | Drawer pet loading → use listAdminClientPets | Frontend | AdminDashboard.jsx | Matthew approves plan |
| 1B.5B | Client drawer Add/Edit/Archive pet | Frontend + minor backend (delete guard) | ClientDetailDrawer.jsx, PetEditor.jsx (new), pet_handler.py | AG implements → Kiro reviews |
| 1B.5C | Global Admin Pet Management | Frontend + backend (list-all endpoint) | AdminDashboard.jsx, pet_handler.py | Matthew decides scope |
| 1B.5D | Client /my-pets editing | Frontend + backend (client pet routes) | MyPets.jsx, pet_handler.py | Separate backend approval |
| 1B.5E | Booking pet selection | Frontend | IntakeForm.jsx, AdminDashboard.jsx (New Visit) | After 1B.5B |
| 1B.5F | Test hardening | Tests | tests/*.test.jsx, tests/backend/ | After implementation |
| 1B.5G | Kiro review | Review | — | After tests pass |
| 1B.5H | Production deployment | Deploy | — | Matthew approval |

---

## Decisions Requiring Matthew Approval

| # | Decision | Recommended Default | Notes |
|---|----------|-------------------|-------|
| 1 | Archive vs hard-delete default | Archive unless zero booking references | Preserves history |
| 2 | Admins may reassign pet ownership | Defer to later phase | Complexity vs value |
| 3 | Clients may create and edit pets | Yes, with field restrictions | 1B.5D scope |
| 4 | Which fields clients may edit | name, species, breed, age, care notes | Staff-only fields excluded |
| 5 | Global Pet Management before booking integration | Defer 1B.5C after 1B.5B | Keeps scope bounded |
| 6 | Duplicate merging in scope | No — warn only, don't auto-merge | Safety |
| 7 | Legacy pets require migration/backfill | No — 13 records remain excluded | Documented, low risk |
| 8 | Pet photos included | Defer — current photo_url exists but no upload UI | Can add later |
| 9 | Nested drawer vs modal for pet editor | Nested drawer (slides over client drawer) | Consistent with context |

---

## Explicit Exclusions

- ❌ No production data scan or modification during planning
- ❌ No pet-photo upload implementation
- ❌ No pet reassignment (deferred)
- ❌ No duplicate-merge automation
- ❌ No legacy data migration/backfill
- ❌ No second-tenant creation
- ❌ No Stripe, Google Calendar, or mobile changes
