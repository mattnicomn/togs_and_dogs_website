# Client / Household / Pet Management Foundation Plan

**Status:** Planning (Architecture Audit and Phased Implementation Design)
**Date:** 2026-07-15
**Priority:** High (next major feature after Staff and Intake corrections)
**Scope:** Audit current client/pet model, design household foundation, plan phased delivery

---

## Current System Findings

### Client Profile Model

| Field | Current Storage |
|-------|----------------|
| PK | `COMPANY#{company_id}` |
| SK | `CLIENT#{client_id}` |
| Key fields | display_name, email, phone, address, emergency_contact, notes |
| Account fields | cognito_sub, cognito_status, portal_enabled, is_active |
| Derived fields | pet_names_summary, pet_breeds_summary, vet_name, vet_phone |

**Limitations:** Single email, single phone, single address (string), single emergency contact (string). No multi-contact, no service-address list, no household grouping.

### Pet Model

| Field | Current Storage |
|-------|----------------|
| PK | `PET#{pet_id}` |
| SK | `CLIENT#{client_id}` |
| Key fields | name, species, breed, age, care_instructions, feeding/medication/behavior/vet/emergency notes |
| Status | is_active (archive = false) |

**Ownership:** Pets belong directly to a client_id. No household intermediate. Pet-to-client is 1:1 via SK.

### Request Model

| Field | Current Storage |
|-------|----------------|
| PK | `REQ#{request_id}` |
| SK | `CLIENT#{client_id}` |
| Inline data | client_name, client_email, client_phone, pets[] array, pet_names string |
| Linked references | pet_ids[] (populated on approval), linked_client_profile_id |

**Behavior:** Requests store inline snapshots at submission time. PET# records are created/linked on approval via `pet_profile.py` name-matching logic.

### Current Capabilities

| Capability | Status |
|------------|--------|
| Client CRUD | ✅ Create, update, disable, delete |
| Client onboard (Cognito) | ✅ With custom:company_id |
| Client link existing | ✅ With tenant validation |
| Pet create/edit | ✅ Via pet_handler |
| Pet archive (is_active=false) | ✅ No hard delete |
| Pet auto-create on approval | ✅ Via pet_profile.py |
| Multi-pet per client | ✅ |
| Client search | ✅ |
| Pet listing for client | ✅ |
| Household entity | ❌ Not implemented |
| Multi-contact | ❌ Single email/phone/address |
| Service addresses | ❌ Single address string |
| Saved-pet picker in intake | ❌ Inline data only |
| Immutable request snapshots | ⚠️ Partially (inline data preserved, but no formal snapshot entity) |
| Global pet search | ❌ No index by pet name across clients |

---

## Recommended Target Schema

### Household (New Entity)

```
PK: COMPANY#{company_id}
SK: HOUSEHOLD#{household_id}
Fields: household_id, company_id, display_name, status (active|archived),
        primary_contact_name, primary_email, primary_phone,
        emergency_contact_name, emergency_contact_phone,
        vet_clinic_name, vet_phone, vet_address,
        notes, created_at, updated_at
```

### Household Contact (Embedded or Sub-Item)

Initially embedded as a JSON array on the Household record for simplicity:
```
contacts: [
  {contact_id, name, email, phone, relationship, is_billing, cognito_sub}
]
```

### Service Address (Embedded)

```
addresses: [
  {address_id, label, street, city, state, zip, access_notes}
]
```

### Pet (Reparented to Household)

```
PK: PET#{pet_id}
SK: HOUSEHOLD#{household_id}  (changed from CLIENT#{client_id})
Fields: pet_id, household_id, company_id, entity_type, name, species, breed,
        age, weight, care_instructions, feeding_notes, medication_notes,
        behavior_notes, vet_notes, emergency_notes, health,
        status (active|archived), archived_at, created_at, updated_at
```

### Request (Adds Household Reference + Snapshots)

```
PK: REQ#{request_id}
SK: CLIENT#{client_id}  (preserved for backward compat)
New fields: household_id, request_client_snapshot, request_pet_snapshots[]
```

---

## Migration and Compatibility Strategy

### Phase 1: No Migration Required

The first phase introduces the Household model alongside the existing CLIENT model. Existing clients continue working. A migration script (future phase) will create HOUSEHOLD records from existing CLIENT records.

### Backward Compatibility Rules

- Existing `PET#/CLIENT#` records remain valid during transition
- New pets can use `HOUSEHOLD#` SK when households exist
- Requests continue using `CLIENT#` SK for backward compat
- `household_id` is optional on requests until migration completes

---

## Phased Release Plan

### Phase 1: Client/Household Management Parity and Stable Foundation

**Scope:** Introduce HOUSEHOLD entity alongside existing CLIENT. Admin can create households. Existing clients display as households in the UI.

**Data changes:** New HOUSEHOLD records; CLIENT records gain optional `household_id` reference  
**API changes:** New CRUD endpoints: GET/POST/PATCH/DELETE /admin/households  
**UI changes:** Client Management tab becomes "Clients & Households" with household cards  
**Tests:** Household CRUD, tenant isolation, backward compat with existing clients  
**Migration:** Optional script to create HOUSEHOLD wrappers for existing CLIENTs  
**Rollback:** Remove household UI; existing client paths continue working  
**Approval gate:** Matthew reviews migration dry-run  
**Deferred:** Multi-contact, service addresses, pet reparenting

### Phase 2: Contacts, Addresses, Emergency Contacts, and Clinics

**Scope:** Add structured contacts, service addresses, and clinic info to households  
**Data changes:** Embedded JSON arrays on HOUSEHOLD records  
**API changes:** Sub-resource CRUD within household endpoints  
**UI changes:** Household detail view with contact/address/clinic sections  
**Tests:** Contact CRUD, address management, tenant isolation  
**Rollback:** Revert to single-field client data  
**Deferred:** Pet management

### Phase 3: Pet Lifecycle Inside Client Management

**Scope:** Pet CRUD within household context; archive/restore  
**Data changes:** New pets use `HOUSEHOLD#` SK; existing pets retain `CLIENT#` SK during transition  
**API changes:** Pet endpoints accept household_id; backward compat with client_id  
**UI changes:** Pet management section within household detail  
**Tests:** Pet CRUD, archive/restore, tenant isolation, backward compat  
**Rollback:** Revert to existing pet_handler behavior  
**Deferred:** Global pet search

### Phase 4: Global Pet Search and Household Navigation

**Scope:** Search pets by name/species across all households; link back to household  
**Data changes:** GSI on pet name or scan optimization  
**API changes:** GET /admin/pets/search endpoint  
**UI changes:** Global pet search bar with household navigation  
**Tests:** Search functionality, tenant-scoped results  
**Rollback:** Remove search endpoint and UI  
**Deferred:** Inline pet removal

### Phase 5: Pet Archive/Restore and Inline Removal

**Scope:** Formal archive/restore workflow; inline request pets removable before save  
**Data changes:** `status` field with `archived_at` timestamp; `archived_by`  
**API changes:** Archive/restore actions on pet endpoints  
**UI changes:** Archive/restore buttons; "Remove" on unsaved inline pets  
**Tests:** Archive preserves history references; restore reactivates  
**Rollback:** Standard  
**Deferred:** Repeat-client intake

### Phase 6: Repeat-Client Intake Using Saved Household and Pets

**Scope:** Authenticated clients select saved pets from their household for new requests  
**Data changes:** None (uses existing household/pet data)  
**API changes:** Client portal pet-picker endpoint  
**UI changes:** Client portal request form shows saved pets with checkboxes  
**Tests:** Saved-pet selection, snapshot creation, no auto-merge  
**Rollback:** Revert to inline-only pet data  
**Deferred:** Immutable snapshots

### Phase 7: Immutable Request Snapshots and Approved Profile Updates

**Scope:** Formal snapshot entities preserving request-time data; profile updates don't alter history  
**Data changes:** `request_client_snapshot` and `request_pet_snapshots[]` on REQ records  
**API changes:** Snapshot captured at submission time  
**UI changes:** Request detail shows snapshot data, not current profile  
**Tests:** Snapshot immutability, profile edits don't affect historical requests  
**Rollback:** Revert to inline data behavior  
**Deferred:** Account workflows

### Phase 8: Account Invite/Link/Status Workflows

**Scope:** Formalize client account lifecycle: profile-only → invited → linked → active → disabled  
**Data changes:** Status field standardization  
**API changes:** Standardized account action endpoints  
**UI changes:** Account status indicators and action buttons in household detail  
**Tests:** Lifecycle transitions, Cognito integration, tenant assignment  
**Rollback:** Existing invite/link paths continue  
**Deferred:** Multi-membership

### Phase 9: Multi-Membership Identity Before Second Tenant

**Scope:** TenantMembership records; tenant selector; server validation  
**Data changes:** MEMBERSHIP records; migration from custom:company_id  
**API changes:** Membership CRUD, tenant-switch validation  
**UI changes:** Tenant selector  
**Tests:** Multi-membership, cross-tenant isolation  
**Security:** Identity confusion between tenants  
**Approval gate:** Security review, Matthew approval  
**Deferred:** Second real tenant onboarding

---

## Recommended First Implementation Release

**Phase 1A: Client/Household Backend Compatibility Layer** ✅ (Validation Complete)

Phase 1A was implemented as a smaller predecessor to the full Phase 1 plan. It introduces a backend compatibility layer that normalizes existing CLIENT records into household-compatible responses without creating HOUSEHOLD records or requiring migration.

**Status:** Pre-deploy validation complete (commits `77a273a`, `3c2efb9`, `ed0ca34`). Awaiting deployment approval.

**What was delivered:**
- `household_id = client_id` on every GET /admin/clients response
- Derived `account_status` field (profile_only, invite_available, invitation_sent, linked_active, linked_disabled, orphaned_identity, unlinked)
- Profile state (`is_active`) and Cognito identity state (`cognito_enabled`) kept separate
- All existing response fields preserved for frontend backward compatibility
- No HOUSEHOLD records, migrations, dual writes, or new endpoints
- 44 focused tests + full-suite comparison with zero candidate-only failures

**Next after deployment:** Phase 1B (Frontend Client Management parity using normalized response)

---

## What This Document Does NOT Authorize

- ❌ Implementation of any phase
- ❌ DynamoDB schema changes
- ❌ Data migrations
- ❌ API endpoint creation
- ❌ Frontend implementation
- ❌ Terraform changes
- ❌ Second tenant creation
- ❌ Cognito changes
- ❌ Mobile changes

Each phase requires separate planning, implementation, testing, and deployment approval.
