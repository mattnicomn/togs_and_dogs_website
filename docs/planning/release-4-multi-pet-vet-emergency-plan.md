# Release 4: Multi-Pet & Vet/Emergency Enhancements — Refined Implementation Plan

**Date:** 2026-05-12 (refined 2026-05-13)  
**Status:** Plan Only — No Implementation Yet  
**Prerequisite:** Release 3 live E2E validation must be fully accepted first  
**Objective:** Support multiple pets per owner/request with structured per-pet fields and enhanced vet/emergency data.

---

## 1. Current Pet Data Model

### DynamoDB Structure

```
PK: PET#<pet_id>          (UUID)
SK: CLIENT#<client_id>    (submission-time client UUID from REQ record)
```

### Current Fields

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `pet_id` | String (UUID) | System | Random UUID |
| `client_id` | String | From REQ record | Submission-time UUID |
| `company_id` | String | System | Tenant scoping |
| `entity_type` | String | System | Always "PET" |
| `name` | String | From `pet_names` on intake | Full free-text string (e.g., "Joey, Kyle, Kevin") |
| `breed` | String | Admin via CareCard | Optional |
| `age` | Number | Admin via CareCard | Optional |
| `care_instructions` | String | From `pet_info` on intake | Free text |
| `behavior` | String | Admin via CareCard | Free text |
| `logistics` | String | Admin via CareCard | Access codes, keys |
| `health` | Map | Admin via CareCard | `{vet_name, vet_phone, emergency_name, emergency_phone}` |
| `meet_and_greet_completed` | Boolean | Admin action | Gate for approval |
| `quote_amount` | Decimal | Admin via CareCard | |
| `payment_status` | String | Admin via CareCard | |

### Current Idempotency Mechanism (job_handler.py)

```python
pet_id = request_item.get('pet_id')
if not pet_id:
    # Create a new PET record
    ...
    # Link pet_id back to REQ record
    table.update_item(Key=..., UpdateExpression="SET pet_id = :pid", ...)
```

The current system only creates a PET record if `pet_id` is not already set on the REQ. This prevents duplicates on re-approval. **Release 4 must preserve this pattern for multi-pet.**

---

## 2. PET# Creation Idempotency (CRITICAL)

### Problem

If individual PET# records are created from a request on approval, repeated approval (Cancel → Restore to Approved) must NOT create duplicate PET# records.

### Solution: `pet_ids` Array as Idempotency Guard

**Same pattern as current `pet_id` field, extended to an array:**

```python
# In job_handler.py (Release 4):
pet_ids = request_item.get('pet_ids')  # Array of already-created pet IDs
if pet_ids and len(pet_ids) > 0:
    # PET records already exist — skip creation
    print(f"INFO: PET records already exist for REQ#{request_id}: {pet_ids}")
else:
    # Create individual PET records from pets array
    pet_ids = []
    for pet_data in pets_array:
        new_pet_id = str(uuid.uuid4())
        # ... create PET record ...
        pet_ids.append(new_pet_id)
    # Link all pet_ids back to REQ record
    table.update_item(
        Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
        UpdateExpression="SET pet_ids = :pids",
        ExpressionAttributeValues={":pids": pet_ids}
    )
```

### Stable Identifier Strategy

| Approach | Pros | Cons | Decision |
|----------|------|------|----------|
| Random UUID per pet | Simple, unique | No deterministic re-creation | ✅ **Use this** |
| Hash of (client_id + pet_name) | Deterministic | Name collisions (two "Max") | ❌ Reject |
| Request-scoped index (pet_0, pet_1) | Deterministic | Fragile if order changes | ❌ Reject |

**Decision:** Use random UUIDs. Idempotency is enforced by the `pet_ids` guard on the REQ record, not by deterministic IDs. Once created, pet_ids are stored on the REQ and never recreated.

---

## 3. Request Pets vs Client Profile Pets

### Three Distinct Concepts

| Concept | Where | Purpose | Lifecycle |
|---------|-------|---------|-----------|
| **Request Pets** | `pets` array on REQ record | What the client submitted for THIS booking | Tied to request lifecycle |
| **Profile PET# Records** | `PET#<id> / CLIENT#<client_id>` | Persistent pet profiles for the client | Independent, reusable across bookings |
| **CareCard Pets** | Loaded from PET# records via `pet_id`/`pet_ids` on REQ | What the admin sees for a specific booking | References PET# records |

### Data Flow

```
Intake Submission:
  → REQ record stores: pets: [{name, species, breed, age, ...}]
  → No PET# records created yet

Approval (CUSTOMER_INTAKE):
  → Client profile auto-created/linked (Release 3)
  → PET# records created from pets array
  → pet_ids linked back to REQ
  → PET# records use the CLIENT_PROFILE's client_id as SK (not the REQ submission client_id)

Repeat Booking (VISIT_BOOKING):
  → Client selects existing pets from their profile
  → REQ stores pet_ids referencing existing PET# records
  → No new PET# records created (unless client adds a new pet)
```

### Key Decision: PET# SK Uses Profile client_id

When Release 3 auto-creates a client profile, the profile has its own `client_id` (e.g., `client_abc123`). PET# records should use THIS profile client_id as their SK, not the REQ submission UUID.

**Why:** This allows the client portal (`/client/pets`) to query pets by the profile client_id, and allows pets to persist across multiple requests.

**Implementation:** After client profile is linked (Release 3), use `linked_client_profile_id` as the SK for new PET# records. If no profile is linked yet, fall back to the REQ `client_id`.

---

## 4. Existing PET# Record Handling

### Scenario Matrix

| Scenario | Detection | Action |
|----------|-----------|--------|
| Client already has pet "Joey" (active PET# record) | Match by name + client_id | Link to existing, do NOT create duplicate |
| Client submits new pet "Luna" | No match | Create new PET# record |
| Client submits "Joey" with updated breed/age | Match by name | Update existing PET# record with new data (merge, don't overwrite) |
| Two pets named "Max" (same client) | Multiple name matches | Create new record (names aren't unique identifiers) |
| Request includes pet that shouldn't overwrite profile | N/A | Request `pets` array is the source for NEW pet creation only. Existing PET# records are only updated if explicitly matched. |

### Name Matching Logic (for existing client re-submissions)

```python
def find_existing_pet(client_profile_id, pet_name, all_client_pets):
    """
    Attempts to find an existing PET# record for this client with the same name.
    Returns the pet_id if found, None otherwise.
    
    Rules:
    - Exact name match (case-insensitive, trimmed)
    - Only matches ACTIVE pets
    - If multiple matches (same name), returns None (ambiguous — create new)
    """
    normalized_name = pet_name.lower().strip()
    matches = [p for p in all_client_pets 
               if (p.get('name') or '').lower().strip() == normalized_name
               and p.get('is_active') != False]
    
    if len(matches) == 1:
        return matches[0].get('pet_id')
    return None  # 0 matches = new pet, 2+ matches = ambiguous, create new
```

### Update vs Create Decision

| Condition | Action |
|-----------|--------|
| Existing pet found by name (single match) | Update with new data from request (merge non-empty fields) |
| No existing pet found | Create new PET# record |
| Multiple pets with same name | Create new PET# record (don't guess which to update) |
| Request pet has empty name | Skip (don't create unnamed pets) |

### Merge Rules (updating existing pet)

Only update fields that are non-empty in the request submission. Do NOT overwrite existing admin-entered data with empty/null values.

```python
# Only update if the new value is non-empty
if pet_data.get('breed'):
    existing_pet['breed'] = pet_data['breed']
if pet_data.get('age'):
    existing_pet['age'] = pet_data['age']
# Never overwrite: care_instructions, behavior, logistics, health, quote fields
# (those are admin-managed via CareCard)
```

---

## 5. Approval Hook: When Are PET# Records Created?

### Decision Matrix

| Event | Create PET# Records? | Rationale |
|-------|----------------------|-----------|
| Public intake submission | ❌ NO | No verified client profile yet |
| CUSTOMER_INTAKE approved | ✅ YES | Client profile exists (Release 3), safe to create persistent pets |
| VISIT_BOOKING approved | ⚠️ ONLY if new pets | Existing client may add new pets to a booking |
| Staff assignment | ❌ NO | Not a creation event |
| Quote/status changes | ❌ NO | Not a creation event |

### Recommended Flow

```
CUSTOMER_INTAKE Approval:
  1. Client profile auto-created/linked (Release 3) ← already deployed
  2. PET# records created from request pets array (Release 4) ← new
  3. JOB record created (existing)
  4. pet_ids linked back to REQ (Release 4) ← new

VISIT_BOOKING Approval:
  1. Client already has profile + existing pets
  2. If request references existing pet_ids → no new PET# records
  3. If request includes NEW pets not in profile → create new PET# records
  4. JOB record created (existing)
```

---

## 6. Backward Compatibility

### Legacy `pet_names` String

| Location | Current Usage | Release 4 Behavior |
|----------|--------------|-------------------|
| Admin Request List | `item.pet_names` displayed in row | Continue displaying. New records auto-generate from `pets[].name.join(', ')` |
| CareCard | `pet.name` (from PET# record) | If PET# has individual name, use it. If legacy concatenated string, display as-is |
| Scheduler | `job.pet_name` | Continue using. New JOBs get first pet name or comma-joined |
| Job creation | `pet_name: request_item.get('pet_names')` | If `pets` array exists, use `pets[0].name` or join. Else fall back to `pet_names` |
| Client Management search | Not currently searched | Release 4 adds `pet_names_summary` to client profile |
| Client portal | `/client/pets` returns PET# records | No change — individual PET# records already work |

### Guaranteed Backward Compat

- `pet_names` field ALWAYS populated on REQ records (auto-generated from `pets[].name` if array exists)
- `pet_info` field preserved (deprecated but not removed)
- Old PET# records with concatenated names continue to display
- `job_handler` checks for `pets` array first, falls back to `pet_names` string

---

## 7. Vet/Emergency Data Model

### Household-Level vs Per-Pet

| Data | Level | Rationale |
|------|-------|-----------|
| Primary vet clinic (name, phone, address) | **Household** (on client profile or request) | Most families use one vet for all pets |
| Emergency contact (name, phone) | **Household** (on client profile or request) | Same emergency contact for all pets |
| Per-pet vet notes | **Per-pet** (on PET# record) | Specific medications, conditions, specialist referrals |
| Per-pet emergency notes | **Per-pet** (on PET# record) | Specific handling instructions in emergency |

### Storage

**On REQ record (submitted by client):**
```json
{
  "vet_info": {
    "vet_name": "Dr. Smith",
    "clinic_name": "Happy Paws",
    "clinic_phone": "555-1234",
    "clinic_address": "123 Main St"
  },
  "emergency_contact": {
    "name": "Jane Doe",
    "phone": "555-5678"
  }
}
```

**On Client Profile (copied on approval):**
```json
{
  "vet_clinic_name": "Happy Paws",
  "vet_name": "Dr. Smith",
  "vet_phone": "555-1234",
  "vet_address": "123 Main St",
  "emergency_contact": "Jane Doe — 555-5678"
}
```

**On PET# record (per-pet, admin-editable):**
```json
{
  "vet_notes": "Allergic to penicillin. See specialist Dr. Jones for hip.",
  "emergency_notes": "If seizure occurs, administer 5mg diazepam from kit in kitchen drawer.",
  // Legacy field preserved:
  "health": { "vet_name": "...", "vet_phone": "...", "emergency_name": "...", "emergency_phone": "..." }
}
```

### Display Priority in CareCard

1. Per-pet `vet_notes` / `emergency_notes` (if set)
2. PET# record `health` map (legacy)
3. Client profile household vet/emergency info (fallback)

---

## 8. Client Search: `pet_names_summary` Idempotency

### Problem

If `pet_names_summary` on the client profile is updated on every approval, repeated approvals could append duplicate pet names.

### Solution: Rebuild from PET# Records

Instead of appending on each approval, **rebuild `pet_names_summary` from the current set of active PET# records** for that client:

```python
def update_pet_names_summary(company_id, client_profile_id):
    """
    Rebuilds pet_names_summary from active PET# records.
    Called after PET# records are created/updated.
    Idempotent — always reflects current state.
    """
    # Query all active PET# records for this client
    pets = table.scan(
        FilterExpression=Attr('client_id').eq(client_profile_id) & Attr('entity_type').eq('PET') & Attr('is_active').ne(False)
    ).get('Items', [])
    
    names = sorted(set(p.get('name', '') for p in pets if p.get('name')))
    breeds = sorted(set(p.get('breed', '') for p in pets if p.get('breed')))
    
    summary = ', '.join(names)
    breed_summary = ', '.join(breeds)
    
    table.update_item(
        Key={'PK': f"COMPANY#{company_id}", 'SK': f"CLIENT#{client_profile_id}"},
        UpdateExpression="SET pet_names_summary = :pns, pet_breeds_summary = :pbs, updated_at = :now",
        ExpressionAttributeValues={
            ":pns": summary,
            ":pbs": breed_summary,
            ":now": datetime.now(timezone.utc).isoformat()
        }
    )
```

This is **fully idempotent** — calling it multiple times produces the same result because it rebuilds from source data rather than appending.

---

## 9. Validation Plan (Expanded)

### TC-01: Single Pet Intake

| Step | Action | Expected |
|------|--------|----------|
| 1 | Submit intake with 1 pet (Joey, Dog, Golden Retriever, 3) | REQ created with `pets: [...]` |
| 2 | Approve | 1 PET# record created, `pet_ids: [id1]` on REQ |
| 3 | Check PET# record | name="Joey", species="DOG", breed="Golden Retriever", age=3 |
| 4 | Check legacy field | `pet_names: "Joey"` on REQ |

### TC-02: Two Pets Intake

| Step | Action | Expected |
|------|--------|----------|
| 1 | Submit with Joey (Dog) + Kyle (Cat) | REQ has `pets: [{...}, {...}]` |
| 2 | Approve | 2 PET# records created, `pet_ids: [id1, id2]` |
| 3 | Check each PET# | Individual records with correct data |
| 4 | Check legacy | `pet_names: "Joey, Kyle"` |

### TC-03: Same Pet Re-Approved (Idempotency)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Request approved, pet_ids set | PET# records exist |
| 2 | Cancel request | Status → CANCELLED |
| 3 | Restore to Approved | Status → APPROVED |
| 4 | Check pet_ids | Same IDs, no new PET# records created |
| 5 | Check PET# record count | Still 2 (not 4) |

### TC-04: Existing Client with Existing Pet

| Step | Action | Expected |
|------|--------|----------|
| 1 | Client profile exists with PET# "Joey" | |
| 2 | Client submits new intake mentioning "Joey" + "Luna" | |
| 3 | Approve | "Joey" matched to existing PET# (updated if new data), "Luna" created as new |
| 4 | Check PET# records | 2 records: existing Joey (updated), new Luna |
| 5 | pet_names_summary | "Joey, Luna" |

### TC-05: Same Pet Name, Different Pet

| Step | Action | Expected |
|------|--------|----------|
| 1 | Client has PET# "Max" (Dog, Labrador) | |
| 2 | Client submits intake with "Max" (Cat, Tabby) — different species | |
| 3 | Name match found but species differs | Ambiguous — create new PET# record |
| 4 | Check PET# records | 2 "Max" records (one Dog, one Cat) |

### TC-06: Legacy Record (pet_names string only)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Old request with `pet_names: "Joey, Kyle"` (no `pets` array) | |
| 2 | View in Admin Request List | Shows "Joey, Kyle" |
| 3 | Approve (if not already) | Falls back to single PET# creation (current behavior) |
| 4 | CareCard | Shows single PET# with name "Joey, Kyle" |

### TC-07: Vet/Emergency Fields

| Step | Action | Expected |
|------|--------|----------|
| 1 | Submit intake with vet_info and emergency_contact | Stored on REQ |
| 2 | Approve | Vet info copied to client profile (household level) |
| 3 | Open CareCard Vet tab | Shows clinic name, address, phone |
| 4 | Edit per-pet vet notes | Saves to PET# record |
| 5 | Old record without new vet fields | Shows "Not specified" |

### TC-08: Client Search by Pet Name

| Step | Action | Expected |
|------|--------|----------|
| 1 | Client has pets "Joey" and "Kyle" | `pet_names_summary: "Joey, Kyle"` |
| 2 | Search "Joey" in Client Management | Finds client |
| 3 | Search "Golden" (breed) | Finds client (via `pet_breeds_summary`) |
| 4 | Repeated approval | Summary unchanged (idempotent rebuild) |

### TC-09: Scheduler and CareCard Display

| Step | Action | Expected |
|------|--------|----------|
| 1 | Multi-pet request in Scheduled with Staff | Shows pet names in row |
| 2 | Open CareCard | Pet selector/tabs visible (if multiple pets) |
| 3 | Single-pet request | No tabs, renders as before |

### TC-10: VISIT_BOOKING with Existing Pets

| Step | Action | Expected |
|------|--------|----------|
| 1 | Existing client with 2 pets submits via portal | References existing pet_ids |
| 2 | Approve | No new PET# records created |
| 3 | Client adds new pet in booking | New PET# record created for new pet only |

---

## 10. Risks and Rollback

### Medium Risk

1. **Multi-pet creation partial failure** — If creating 3 pets and the 2nd fails, 1 exists and 2 don't. Mitigation: create all in a loop, collect successes, store whatever pet_ids were created. Log failures. Don't block approval.

2. **Name matching false positives** — "Max" the dog matched to "Max" the cat. Mitigation: only match if single result. Multiple matches → create new.

3. **pet_names_summary scan cost** — Rebuilding from PET# records requires a scan. Mitigation: only runs on approval (infrequent), and the scan is filtered by client_id.

### Low Risk

4. **Backward compatibility** — All new fields optional. Legacy records render with fallbacks.
5. **No lifecycle changes** — Status transitions unchanged.
6. **No Cognito changes** — No auth modifications.

### Rollback

- Revert intake form → single pet_names field
- Revert job_handler → single PET creation
- Multi-pet PET# records already created remain valid
- No data cleanup needed

---

## 11. Implementation Order

### Step 1: Backend — Enhanced PET Schema

Update `pet_handler.py` editable_fields to include: `species`, `feeding_notes`, `medication_notes`, `behavior_notes`, `vet_notes`, `emergency_notes`, `is_active`.

### Step 2: Backend — Multi-Pet Intake Storage

Update `intake_handler.py` to accept `pets` array, `vet_info`, `emergency_contact`. Auto-generate legacy `pet_names` from array.

### Step 3: Backend — Multi-Pet Job Creation (with idempotency)

Update `job_handler.py`:
- Check `pet_ids` array (idempotency guard)
- If absent, create individual PET# records from `pets` array
- Use `linked_client_profile_id` for PET# SK when available
- Match existing pets by name before creating new
- Store `pet_ids` array back on REQ
- Rebuild `pet_names_summary` on client profile

### Step 4: Frontend — IntakeForm Multi-Pet UI

Replace Step 3 with repeatable pet entry + vet/emergency section.

### Step 5: Frontend — CareCard Multi-Pet Display

Add pet selector/tabs when multiple pets exist. Display new structured fields.

### Step 6: Frontend — Client Search Enhancement

Include `pet_names_summary` and `pet_breeds_summary` in client-side search filter.

### Step 7: Validation

Full test suite (TC-01 through TC-10).

---

## 12. Files to Change

| File | Changes |
|------|---------|
| `src/backend/handlers/pet_handler.py` | Add new editable fields |
| `src/backend/handlers/intake_handler.py` | Accept pets array, vet_info, emergency_contact |
| `src/backend/handlers/job_handler.py` | Multi-pet creation with idempotency + name matching |
| `web/src/components/IntakeForm.jsx` | Multi-pet entry UI + vet/emergency section |
| `web/src/components/CareCard.jsx` | Pet selector/tabs + enhanced vet display |
| `web/src/components/AdminDashboard.jsx` | Pet name/breed in client search |

**Total:** 6 files modified  
**Estimated effort:** ~250 lines backend, ~300 lines frontend  
**Risk level:** Medium (multi-record creation, name matching, UI complexity)

---

## 13. Dependencies

- **Release 3 live E2E validation MUST pass first** — client profile automation must work correctly since multi-pet creation depends on `linked_client_profile_id` for the PET# SK.
- No Terraform changes required.
- No new DynamoDB tables or GSIs required.
