# Phase 1B.2: Client Write Workflows and Pet Lifecycle Audit

**Date:** 2026-07-16
**Status:** Planning Complete
**Type:** Architecture audit and phased implementation planning
**Scope:** All client, pet, contact, account, and request-history write workflows

---

## Executive Summary

The existing client and pet write workflows are functional and production-validated. They support create, edit, archive, disable, Cognito linkage, and pet auto-creation during request approval. The primary gaps are UX consolidation, household-level data modeling (contacts, addresses, clinic), pet lifecycle management within Client Management, and immutable request snapshots.

This document recommends **Option B — Pet Lifecycle Inside Client Management** as the next bounded implementation slice because it delivers immediate user value with minimal migration risk.

---

## Current-State Architecture

### CLIENT Record (DynamoDB)

| Field | Type | Required | Source |
|-------|------|----------|--------|
| PK | `COMPANY#{company_id}` | Yes | System |
| SK | `CLIENT#{client_id}` | Yes | System |
| company_id | String | Yes | Tenant |
| client_id | String | Yes | Generated |
| display_name | String | Yes | Admin/intake |
| email | String | No | Admin/intake |
| phone | String | No | Admin/intake |
| address | String | No | Admin |
| emergency_contact | String | No | Admin/intake |
| notes | String | No | Admin |
| is_active | Boolean | Yes | Admin action |
| portal_enabled | Boolean | Yes | System |
| cognito_sub | String | No | Cognito link |
| cognito_status | String | No | System |
| auto_created | Boolean | No | System |
| request_count | Number | No | System |
| intake_request_ids | List | No | System |
| pet_names_summary | String | No | System (rebuilt) |
| pet_breeds_summary | String | No | System (rebuilt) |
| vet_name, vet_clinic_name, vet_phone, vet_address | String | No | Intake |
| created_at, updated_at | ISO timestamp | Yes | System |

### PET Record (DynamoDB)

| Field | Type | Required | Source |
|-------|------|----------|--------|
| PK | `PET#{pet_id}` | Yes | System |
| SK | `CLIENT#{client_id}` | Yes | System |
| company_id | String | Yes | Tenant |
| entity_type | `PET` | Yes | System |
| pet_id | String | Yes | Generated |
| client_id | String | Yes | Owner |
| name | String | Yes | Intake/admin |
| species, breed, age | String | No | Intake/admin |
| feeding_notes, medication_notes, behavior_notes | String | No | Intake/admin |
| vet_notes, emergency_notes, care_instructions | String | No | Intake/admin |
| is_active | Boolean | Yes | Admin |
| created_from_request_id | String | No | System |
| created_at, updated_at | ISO timestamp | Yes | System |

### Key Relationships

- CLIENT belongs to COMPANY (PK)
- PET belongs to CLIENT (SK) — 1:N pets per client
- REQ references CLIENT (SK) and optionally links pet_ids after approval
- No HOUSEHOLD entity exists; household_id = client_id is a compatibility alias

---

## Workflow Inventory

### Client Create (Profile Only)
- **Frontend:** Client Management form with `creation_mode='profile_only'`
- **Backend:** `POST /admin/clients`
- **Operations:** DynamoDB put_item; no Cognito
- **Tenant:** company_id from caller claims
- **Tests:** Covered by entitlement tests
- **Status:** Production-validated

### Client Onboard (Create Login + Profile)
- **Frontend:** Client Management form with `creation_mode='onboard'`
- **Backend:** `POST /admin/clients/onboard`
- **Operations:** DynamoDB put_item + Cognito admin_create_user + group assignment + branded email
- **Tenant:** build_tenant_user_attribute(company_id) on Cognito user
- **Tests:** Covered by tenant assignment handler integration tests
- **Status:** Production-validated

### Client Edit
- **Frontend:** Click card → populate form → submit
- **Backend:** `PATCH /admin/clients/{id}`
- **Operations:** DynamoDB put_item + optional Cognito attribute sync (name, phone)
- **Editable:** display_name, email, phone, address, emergency_contact, notes, is_active
- **Guards:** Duplicate email check, protected email guard, blank email restriction for Cognito users
- **Status:** Production-validated

### Client Disable/Enable
- **Backend:** `PATCH /admin/clients/{id}` with action='disable' or 'enable'
- **Operations:** DynamoDB is_active+portal_enabled + Cognito admin_disable/enable_user
- **Status:** Production-validated

### Client Unlink
- **Backend:** `PATCH /admin/clients/{id}` with action='unlink'
- **Operations:** Sets cognito_sub='unlinked', cognito_status='unlinked', portal_enabled=False
- **Status:** Production-validated

### Client Delete (Profile)
- **Backend:** `PATCH /admin/clients/{id}` with action='delete_profile'
- **Guards:** Must be inactive; must have no active requests
- **Status:** Production-validated

### Client Delete (Cognito)
- **Backend:** `PATCH /admin/clients/{id}` with action='delete_cognito'
- **Operations:** Cognito admin_disable + admin_delete + profile metadata cleanup
- **Status:** Production-validated

### Link Existing Cognito
- **Backend:** `POST /admin/clients/{id}/link-cognito`
- **Operations:** Validates tenant via ensure_cognito_tenant_attribute, assigns group, sets portal_enabled
- **Status:** Production-validated

### Resend Invite / Reset Password / Set Temp Password
- **Backend:** Respective `/admin/clients/{id}/...` endpoints
- **Operations:** Cognito admin_set_user_password or admin_reset_user_password + notification
- **Status:** Production-validated

### Auto-Create Client on Request Approval
- **Module:** `common/client_profile.py`
- **Trigger:** Request status transition to approved
- **Matching:** Email-only (exact, case-insensitive)
- **Safety:** Multiple matches → needs_review; no auto-link; no Cognito creation
- **Status:** Production-validated

### Pet Auto-Create on Request Approval
- **Module:** `common/pet_profile.py`
- **Trigger:** After client profile linked on approval
- **Matching:** Pet name (exact, case-insensitive)
- **Safety:** Multiple name matches → create new + warning
- **Status:** Production-validated

### Pet CRUD (Admin)
- **Backend:** `pet_handler.py` — POST/PUT /admin/pets
- **Tenant:** Indirect via client ownership check
- **Archive:** is_active=False (soft delete)
- **No hard delete** in current handler
- **Status:** Production-validated

---

## Defects

| # | Issue | Evidence | Risk | Recommended Phase |
|---|-------|----------|------|-------------------|
| 1 | Pet listing uses DynamoDB scan (FilterExpression on client_id) | pet_handler.py line ~40 | Performance degrades with data growth | Future (GSI addition) |
| 2 | Disable action conflates profile archive + Cognito disable in one operation | admin_handler action='disable' | UX confusion between archiving a business relationship vs disabling login | 1B.2 UX |
| 3 | Client form email cannot be changed after Cognito link (frontend only) | AdminDashboard.jsx | UX limitation; backend allows it | Low priority |

---

## UX Improvements

| # | Item | Value | Phase |
|---|------|-------|-------|
| 1 | Pet inventory visible in Client Management without opening edit | High — Ryan feedback | 1B.2 |
| 2 | Create/edit/archive pets directly from Client Detail drawer | High — Ryan feedback | 1B.2 |
| 3 | Separate "Archive Profile" from "Disable Login" actions | Medium | Future |
| 4 | Better empty states and validation messages | Low | 1B.2 (incidental) |

---

## Data-Model Enhancements (Deferred)

| # | Item | Dependencies | Phase |
|---|------|-------------|-------|
| 1 | Multiple contacts (JSON array on CLIENT) | None | Phase 2 per foundation plan |
| 2 | Multiple service addresses | None | Phase 2 |
| 3 | Preferred veterinary clinic entity | None | Phase 2 |
| 4 | Immutable request snapshots | Stable pet/client IDs | Phase 7 per foundation plan |
| 5 | HOUSEHOLD entity (separate from CLIENT) | Migration planning | Phase 1 per foundation plan (when approved) |
| 6 | Multi-user household membership | UserIdentity/TenantMembership | Phase 9 |

---

## Tenant and Identity Constraints

| Constraint | Status |
|------------|--------|
| company_id tenant ownership | ✅ Active on all writes |
| Single-membership Cognito custom:company_id | ✅ Active |
| Cross-tenant client access blocked | ✅ Active |
| Cross-tenant pet access blocked | ✅ Active (indirect via client check) |
| Virtual users (Cognito-only) | ✅ Supported |
| Profile-only clients (no Cognito) | ✅ Supported |
| Orphaned identities detected | ✅ Active (Phase 22H) |
| Multi-membership identity | ❌ Not implemented (Phase 9) |

**Safe before multi-membership:** All proposed Phase 1B.2 work operates within the existing single-tenant ownership model.

---

## Options Considered

### Option A — Client Edit Form Parity
Improve the existing edit form UX without backend schema changes.

- **Value:** Low incremental (form already works)
- **Size:** Small
- **Risk:** Minimal
- **Verdict:** Not high-priority since the edit workflow is already functional

### Option B — Pet Lifecycle Inside Client Management (RECOMMENDED)
Add read-only pet inventory in the Client Detail drawer, followed by safe create/edit/archive within existing data structures.

- **Value:** High (direct Ryan feedback; existing PET records exist but are hard to manage)
- **Size:** Medium (frontend + minor backend expansion of GET response)
- **Migration risk:** None (uses existing PET records and CLIENT ownership)
- **Tenant risk:** None (existing company_id isolation applies)
- **Cognito risk:** None
- **Production-data risk:** None (no CLIENT schema change)
- **Testability:** High (PET CRUD has existing backend tests)
- **Reversibility:** High (frontend-only changes + existing pet_handler)

### Option C — Contacts/Clinic/Address Backend Foundation
Design new embedded JSON arrays on CLIENT records.

- **Value:** Medium (important for multi-pet households and scheduling)
- **Size:** Large (backend schema extension + frontend + migration planning)
- **Risk:** Medium (changes CLIENT item size, requires compatibility planning)
- **Verdict:** Better addressed after pet management is stable

### Option D — Request Snapshots and Repeat Intake
Define stable references and immutable snapshots.

- **Value:** High long-term (prevents data corruption on profile edits)
- **Size:** Large (requires REQ schema extension + frontend + migration)
- **Risk:** Medium
- **Verdict:** Important but not the smallest next step

---

## Recommended Next Slice: Option B — Pet Lifecycle Inside Client Management

### Exact Scope

**Phase 1B.2A — Pet inventory in Client Detail drawer (read-only):**
- Display existing PET records within the drawer's Pets section
- Use existing `GET /admin/pets?clientId={id}` endpoint (already exists)
- Show: name, species, breed, age, active/archived status
- Fetch pets only when the drawer opens (not on every list render)
- Single request per drawer open (not N+1 per client)

**Phase 1B.2B — Pet create/edit/archive from Client Management:**
- Create new pet for a client using existing `POST /admin/pets`
- Edit pet details using existing `PUT /admin/pets/{id}`
- Archive pet (set is_active=false) using existing endpoint
- All within the Client Detail drawer or a sub-view
- Rebuild pet_names_summary after changes (existing backend behavior)

### Explicit Exclusions

- ❌ No CLIENT schema changes
- ❌ No HOUSEHOLD record creation
- ❌ No migration or backfill
- ❌ No auto-merge of clients by email
- ❌ No auto-link of Cognito accounts by email
- ❌ No unbounded scans or N+1 queries on the client list
- ❌ No multiple-contact, address, or clinic structures
- ❌ No request-history queries per client
- ❌ No immutable snapshot implementation
- ❌ No multi-membership identity work
- ❌ No new tenant creation
- ❌ No Terraform changes for Phase 1B.2A (frontend only)
- ❌ No production deployment without separate approval

### Acceptance Criteria

1. Client Detail drawer shows existing pets for the selected client
2. Pet fetch occurs only on drawer open (one GET request)
3. No pet fetch during list rendering
4. Pet create form creates PET records with correct client_id and company_id
5. Pet edit updates existing PET records
6. Pet archive sets is_active=false
7. Tenant isolation is preserved (client ownership check)
8. Empty state is clear when no pets exist
9. Build passes, lint matches baseline, no new dependency
10. Local browser validation passes before deployment

### Testing Strategy

- Extend Node utility tests for any pure formatting functions
- Backend pet_handler already has existing test coverage
- New integration behavior provable via local browser validation
- No React component test framework required for this slice

### Rollback

- Remove pet-inventory rendering from the drawer (frontend-only change)
- Existing PET records and backend behavior remain unchanged

---

## Phased Roadmap (Updated)

| Phase | Scope | Status |
|-------|-------|--------|
| 1A | Backend compatibility (household_id, account_status) | ✅ Deployed |
| 1B.1 | Frontend list/search/filter/drawer | ✅ Deployed |
| **1B.2A** | **Pet inventory in drawer (read-only)** | **Next** |
| 1B.2B | Pet create/edit/archive from Client Management | After 1B.2A |
| 2 | Contacts, addresses, clinic structures | Future |
| 3 | Pet lifecycle metadata (reparent to household when created) | Future |
| 7 | Immutable request snapshots | Future |
| 8 | Account lifecycle formalization | Future |
| 9 | Multi-membership identity | Future |

---

## Approval Gates

- Phase 1B.2A implementation: Matthew reviews scope
- Phase 1B.2A deployment: Matthew approves S3 sync + CloudFront invalidation
- Phase 1B.2B implementation: Separate review
- Any backend change: Terraform plan/apply with separate approval
- Any CLIENT schema change: Separate planning and approval
- HOUSEHOLD entity creation: Separate planning, migration dry-run, and approval
