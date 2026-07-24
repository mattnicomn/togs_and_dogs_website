# Phase 1B.5C — Customer Pet Self-Service Editing Design Audit

**Date:** 2026-07-23
**Status:** READY_FOR_BOUNDED_IMPLEMENTATION_PLANNING
**Type:** Design analysis and sequencing

---

## Current State

- Phase 1B.5B-B: DESIGN_ONLY_THEN_DEFER (permanent deletion deferred)
- Customer /my-pets: READ-ONLY (deployed in Phase 1B.3)
- No customer-facing pet mutation route exists
- Archive/Restore: staff/admin only
- Staff email-field issue: RESOLVED (field is visible for new staff, hidden-by-design for existing staff)

---

## Customer Ownership and Identity Model

### Authentication Chain
```
Cognito session → cognito_sub + email + custom:company_id
→ resolve_client_identity(event)
→ Queries COMPANY#{company_id}/CLIENT# partition
→ Matches by cognito_sub (primary) or verified email (fallback)
→ Returns client_id or None
```

### Pet Ownership Proof
```
client_id (from resolve_client_identity) → PET records where:
  - SK = CLIENT#{client_id}
  - client_id field = resolved client_id
  - company_id = caller's company_id
  - entity_type = 'PET'
```

A customer MUST have a resolved client identity AND the pet must belong to that identity AND the same tenant. No caller-supplied clientId should be trusted.

---

## Field-Level Policy

| Field | Classification | Customer Behavior |
|-------|---------------|-------------------|
| name | CUSTOMER_EDITABLE | Edit |
| species | CUSTOMER_EDITABLE | Edit |
| breed | CUSTOMER_EDITABLE | Edit |
| age | CUSTOMER_EDITABLE | Edit |
| care_instructions | CUSTOMER_EDITABLE | Edit |
| feeding_notes | CUSTOMER_EDITABLE | Edit |
| medication_notes | CUSTOMER_EDITABLE | Edit |
| behavior_notes | CUSTOMER_EDITABLE | Edit |
| photo_url | NOT_SUPPORTED | Hidden (no upload UI) |
| vet_notes | STAFF_ADMIN_ONLY | Read-only or hidden |
| emergency_notes | STAFF_ADMIN_ONLY | Read-only or hidden |
| health (vet_name, vet_phone) | CUSTOMER_EDITABLE | Edit vet contact info |
| health (other keys) | STAFF_ADMIN_ONLY | Preserved silently |
| logistics | STAFF_ADMIN_ONLY | Hidden |
| document_links | STAFF_ADMIN_ONLY | Hidden |
| meet_and_greet_* | STAFF_ADMIN_ONLY | Hidden |
| quote_amount | STAFF_ADMIN_ONLY | Hidden |
| internal_pricing_notes | STAFF_ADMIN_ONLY | Hidden |
| is_active | SYSTEM_MANAGED | Not customer-editable |
| color | READ_ONLY_HISTORICAL | Display only (unapproved for write) |
| weight | READ_ONLY_HISTORICAL | Display only (unapproved for write) |
| client_id | SYSTEM_MANAGED | Never exposed or editable |
| company_id | SYSTEM_MANAGED | Never exposed or editable |
| pet_id | SYSTEM_MANAGED | Never exposed or editable |
| PK/SK | SYSTEM_MANAGED | Never exposed |
| created_at | SYSTEM_MANAGED | Display only |
| updated_at | SYSTEM_MANAGED | Display only |
| created_from_request_id | READ_ONLY_HISTORICAL | Hidden |

### Veterinary and Medical Fields
Customers SHOULD be able to edit their own pet's vet contact, medication, feeding, and behavioral notes. This is the information they maintain in real life. Staff review happens during booking approval — not as a gate on profile editing.

---

## Archived-Pet Policy

| Behavior | Customer | Staff/Admin |
|----------|----------|-------------|
| View archived pets | ❌ Hidden | ✅ Visible with badge |
| Edit archived pets | ❌ | ✅ |
| Archive a pet | ❌ | ✅ |
| Restore a pet | ❌ | ✅ |
| Select archived pet for booking | ❌ | ❌ |
| Historical booking shows archived pet name | ✅ (from REQ copy) | ✅ |

Customers see only active pets in /my-pets and cannot archive or restore.

---

## Proposed API Contract

### PUT /client/pets/{petId}
**Authorized roles:** client (with resolved identity matching pet ownership)

**Ownership verification:**
1. `resolve_client_identity(event)` → client_id
2. `get_current_company_id(event)` → company_id
3. `get_item(PET#{petId}, CLIENT#{client_id})` → existing pet
4. Verify `existing.company_id == company_id`
5. If any check fails → 403/404

**Accepted fields (allowlist):**
```python
CUSTOMER_EDITABLE_FIELDS = [
    'name', 'species', 'breed', 'age',
    'care_instructions', 'feeding_notes',
    'medication_notes', 'behavior_notes',
    'health'  # only vet_name and vet_phone subkeys
]
```

**Rejected silently:** All other fields stripped from the payload before write.

**Health-map handling:** Merge customer-supplied `vet_name`/`vet_phone` into existing health map. Do NOT allow customer to overwrite other health keys.

**Responses:**
- 200: Updated pet record (sanitized for client role)
- 400: Missing required field (name)
- 403: Unlinked identity or ownership mismatch
- 404: Pet not found under this client
- 500: Internal error (no detail exposed)

### POST /client/pets (Optional — deferred if not prioritized)
Creates a new pet under the resolved client identity.

**Accepted fields:** Same allowlist as PUT.
**Auto-populated:** pet_id, client_id, company_id, entity_type, is_active=true, created_at, updated_at.
**Duplicate warning:** Frontend-only (compare against loaded pet list by normalized name).

---

## Frontend UX Design

### /my-pets Page Enhancement
1. Each pet card gains an "Edit" button (pencil icon or text)
2. Clicking Edit opens an inline edit form OR navigates to a pet-detail/edit view
3. Editable fields grouped: Basic Info (name, species, breed, age) → Care Notes (feeding, medication, behavior, care instructions) → Vet Info (vet_name, vet_phone)
4. Save and Cancel buttons
5. Unsaved-change warning on navigation
6. Validation: name required
7. Duplicate warning (non-blocking)
8. Success toast after save
9. Authoritative reload after save

### Mobile / Expo Parity
The /my-pets page is a web route. The mobile app currently shows booking details with pet info from the request record. Customer pet editing should be web-first; mobile parity deferred unless Matthew prioritizes it.

### Accessibility
- Form labels associated with inputs
- Error messages linked via aria-describedby
- Focus management on edit/save transitions
- Keyboard-navigable

---

## Booking Dependency Analysis

### 1B.5C vs 1B.5E Independence
- **1B.5C (customer pet editing)** does NOT depend on 1B.5E
- **1B.5E (booking saved-pet selection)** does NOT require 1B.5C — it uses existing admin-managed pets
- They are independent and can be sequenced in either order
- Customer edits to pet profiles do NOT retroactively change historical bookings (REQ stores pet_names copy)
- Future bookings should reference the pet_id (stable identifier) — the display name is looked up at render time

### Recommended: 1B.5C before 1B.5E
Customers editing their own pets first establishes the customer-facing mutation contract. Booking integration then builds on authoritative, customer-maintained profiles.

---

## Backlog Sequencing

| # | Item | Priority | Dependency | Recommendation |
|---|------|----------|-----------|----------------|
| 1 | Staff Email-field | RESOLVED | — | No action needed |
| 2 | Phase 1B.5C customer pet editing | **NEXT** | None | Highest customer value |
| 3 | Phase 1B.5E booking saved-pet selection | After 1B.5C | 1B.5C recommended first | Medium priority |
| 4 | Client Management redesign | Low | None | Deferred |
| 5 | Phase 1B.5B-B permanent deletion | Deferred | Design complete | Not needed |
| 6 | Mobile parity | Low | After web stabilizes | Deferred |

### Staff Email-Field Status: RESOLVED
The fix documented in `fix-staff-email-field-predeploy.md` (2026-07-13) has been deployed. Current code shows the email field for new staff creation (`{!editingStaffId && ...}`). Email is intentionally hidden when editing existing staff (cannot change login identity). No correction needed.

---

## Testing Strategy

### Backend Tests
1. Client can update own pet (200)
2. Client cannot update another client's pet (403/404)
3. Client cannot update cross-tenant pet (403)
4. Disallowed fields silently stripped (staff-only fields ignored)
5. company_id/client_id cannot be changed
6. is_active cannot be changed by client
7. color/weight not accepted
8. Health-map merge preserves existing non-vet keys
9. Archived pet cannot be updated by client (404 — excluded from client query)
10. Name required validation
11. Unlinked identity returns 403
12. Repeated update is safe (idempotent)
13. Sanitized response (no internal fields returned)

### Frontend Tests
1. Edit button visible for each pet
2. Edit form shows allowed fields only
3. Staff-only fields hidden
4. Save calls PUT /client/pets/{petId}
5. Successful save shows toast and reloads
6. Failed save preserves form state
7. Unsaved changes prompt on navigation
8. Name required validation
9. Duplicate warning (non-blocking)
10. Loading and error states
11. No admin/internal fields in request payload

---

## Recommendation: **READY_FOR_BOUNDED_IMPLEMENTATION_PLANNING**

Phase 1B.5C is the highest-value next item:
- Customers can maintain their own pet profiles (name, breed, care notes, vet info)
- No dependency on other pending work
- Staff email-field issue is resolved
- No blocking security or stability concern
- Clear field-level policy and ownership model defined
- Single new backend route (PUT /client/pets/{petId}) with strict allowlist

---

## Next Approval Gate

**Matthew approves the Phase 1B.5C field policy and implementation scope:**
1. Customer-editable fields as listed above
2. PUT /client/pets/{petId} with ownership verification
3. Optional: POST /client/pets for customer pet creation (can be deferred)
4. Web-first, mobile deferred
5. No archive/restore for customers
6. No color/weight write access

Once approved, AG begins bounded implementation.
