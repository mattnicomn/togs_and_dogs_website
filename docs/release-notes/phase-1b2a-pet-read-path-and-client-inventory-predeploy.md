# Phase 1B.2A: Pet Read-Path Audit and Design Recommendation

**Date:** 2026-07-16
**Status:** ⚠️ BLOCKED — GSI Required Before Frontend Implementation
**Type:** Architecture audit and design recommendation
**Updated:** 2026-07-16 (Phase 1B.2A.1 — refined index design and tenant-isolation review)

---

## Production Table Details

| Item | Value |
|------|-------|
| Terraform resource | `module.data.aws_dynamodb_table.main` |
| Table name | `togs-and-dogs-prod-data` |
| Billing mode | PAY_PER_REQUEST (on-demand) |
| Primary key | PK (String) + SK (String) |
| Existing GSIs | StatusIndex (status + created_at), WorkerIndex (worker_id + assigned_at) |

## PET Item Key Schema

```
PK: PET#{pet_id}        (globally unique UUID)
SK: CLIENT#{client_id}   (owner association)
```

## PET Attribute Coverage (All Creation Paths)

| Field | pet_profile._create_new_pet | pet_profile._create_legacy | pet_handler POST/PUT | Always Present? |
|-------|---------------------------|---------------------------|---------------------|-----------------|
| pet_id | ✅ | ✅ | ✅ | Yes (also in PK) |
| client_id | ✅ | ✅ | ✅ | Yes (also in SK) |
| company_id | ✅ | ✅ | ✅ | Yes |
| entity_type = 'PET' | ✅ | ✅ | ✅ | Yes |
| is_active | ✅ (True) | ✅ (True) | Set from body or existing | Yes on new creates |

**Assessment:** All identified PET creation paths write `client_id`, `pet_id`, `company_id`, and `entity_type`. Historical pre-Release-4 pets cannot be verified without production inspection, but the code audit shows no path that omits these fields.

---

## Current GET /admin/pets Endpoint

### Parameters
- `clientId` (camelCase query parameter) — frontend: `listAdminClientPets(clientId)`
- Response: `{ "pets": [...] }`
- Active/archive filter: excludes `is_active === false` from list results
- Pagination: None (returns all matching items in one response)

### Current Implementation (Scan)
```python
scan_kwargs = {
    "FilterExpression": Attr("client_id").eq(client_id) & Attr("entity_type").eq("PET")
}
resp = items_table.scan(**scan_kwargs)
items = resp.get('Items', [])
items = [p for p in items if not p.get('company_id') or p.get('company_id') == company_id]
items = [p for p in items if p.get('is_active') is not False]
```

**Problems:**
- Full table Scan reads every item across all entity types and tenants
- FilterExpression is applied AFTER reading (consumes full capacity)
- Post-scan tenant filter is defense-in-depth but data is already read
- No pagination token exposed to callers
- Performance degrades with total table size

---

## Index Options Comparison

### Option 1 — Minimal Compatibility GSI (RECOMMENDED)

```
GSI Name: ClientPetIndex
Partition Key: client_id (String)
Sort Key: pet_id (String)
Projection: ALL
```

**Advantages:**
- Both `client_id` and `pet_id` exist on ALL PET items (guaranteed by key structure)
- Unique sort key (pet_id is UUID) — no duplicate-key issues
- Bounded query: reads only items matching the specific client_id
- Natural result ordering by pet_id (stable, if not meaningful)
- Supports LastEvaluatedKey pagination
- Non-PET items with client_id (e.g., REQ items stored with `SK = CLIENT#{id}`) will NOT appear because their PK doesn't match `PET#` pattern — **however**, the GSI indexes by `client_id` attribute, not PK. Items with a `client_id` attribute that are NOT pets will enter the index.
- Post-query `entity_type = 'PET'` FilterExpression needed as defense

**Tenant-isolation approach:**
1. Resolve `company_id` from trusted authenticated claims
2. Direct GetItem: `PK = COMPANY#{company_id}, SK = CLIENT#{client_id}` — confirms client belongs to tenant
3. If not found → 404/403 (client not owned by this tenant)
4. Query GSI: `client_id = {verified_client_id}`
5. FilterExpression: `entity_type = 'PET'`
6. Post-query defense: verify each item's `company_id` matches trusted context
7. Apply is_active filter per existing behavior

**Why client_id alone is NOT tenant authorization:**
A client_id is a UUID that could theoretically be guessed or leaked. Authorization requires proving the CLIENT belongs to the authenticated tenant BEFORE querying pet data. The GSI itself provides no tenant boundary.

**Migration requirement:** None — DynamoDB auto-backfills existing items that have both `client_id` and `pet_id` attributes.

### Option 2 — Original ClientEntityIndex Proposal

```
Partition Key: client_id
Sort Key: entity_type
```

**Problems:**
- `entity_type = 'PET'` is identical for all PET items → sort key provides no ordering benefit
- All PET items for a client would have the same sort-key value → DynamoDB allows this but pagination behavior is less predictable
- Non-unique sort key makes individual item retrieval impossible via the index alone
- Other entity types with `client_id` + `entity_type` attributes (e.g., REQUEST items) also enter the index

**Verdict:** Inferior to Option 1.

### Option 3 — Tenant-Scoped Synthetic Key

```
Attribute: client_pet_pk = COMPANY#{company_id}#CLIENT#{client_id}
Sort Key: PET#{pet_id}
```

**Advantages:** Strongest tenant isolation at the index level.

**Problems:**
- Requires adding a new synthetic attribute to ALL existing PET items (backfill)
- Requires modifying every PET write path to populate the synthetic key
- Migration and rollback complexity
- Higher implementation risk for what is currently a read-optimization

**Verdict:** Deferred. The tenant-validation-first approach (Option 1 + GetItem check) provides equivalent security without migration.

---

## Recommended Design: Option 1 — ClientPetIndex

### GSI Specification

```
Name: ClientPetIndex
Partition Key: client_id (String)
Sort Key: pet_id (String)
Projection: ALL
```

### Projection Choice: ALL

**Reasoning:** The current endpoint returns all PET fields in the response. A KEYS_ONLY or INCLUDE projection would require a follow-up GetItem for every returned pet to populate the full response — creating the N+1 pattern we're avoiding. Since PET items are small (typically <1 KB each) and per-client counts are low (typically 1-5 pets), the storage cost of ALL projection is negligible.

### Bounded Backend Flow

1. **Authenticate** — resolve `company_id` from trusted Cognito claims
2. **Authorize client** — `GetItem(PK=COMPANY#{company_id}, SK=CLIENT#{client_id})`
   - Not found → return 404 or 403
3. **Query GSI** — `ClientPetIndex` with `KeyConditionExpression: client_id = :cid`
   - FilterExpression: `entity_type = :pet` (defense against non-PET items with client_id)
4. **Post-query defense** — verify `company_id` on each returned item matches trusted context
5. **Apply active/archive filter** — exclude `is_active === false` unless explicitly requested
6. **Return** — existing response shape `{ "pets": [...] }` with optional `lastKey` for pagination

**DynamoDB requests per call:** 1 GetItem + 1 Query = 2 (bounded)

**Empty filtered page handling:** If FilterExpression removes all items from a page but LastEvaluatedKey exists, the handler must continue querying until results are found or the index is exhausted. This prevents premature termination.

**Archived pets:** Controlled by `is_active` filter (same as current behavior). Future explicit archive-view parameter can override.

**Cross-tenant client_id:** Step 2 rejects it before any pet data is accessed.

**Legacy pets missing company_id:** Treated as belonging to the default tenant (existing behavior). Defense-in-depth filter retains them only if the caller is the default tenant.

### Pagination

- Expose `LastEvaluatedKey` as an opaque `nextToken` in the response
- Accept `nextToken` query parameter for continuation
- Preserve existing behavior (no pagination) when result set fits in one page

### Endpoint Compatibility

| Parameter | Current | After Change |
|-----------|---------|-------------|
| `clientId` (query) | ✅ | ✅ (unchanged) |
| Response `{ "pets": [...] }` | ✅ | ✅ (unchanged) |
| Active-only filter | ✅ | ✅ (unchanged) |
| Pagination token | Not supported | Optional `nextToken` (additive) |

---

## Terraform Implications

- **Resource changed:** `module.data.aws_dynamodb_table.main` (in-place update)
- **Change:** Add one `attribute` definition + one `global_secondary_index` block
- **Backfill:** Automatic, non-blocking. Table remains fully available during index creation.
- **Expected plan:** 0 add, 1 change, 0 destroy
- **GSI status monitoring:** Check `IndexStatus = ACTIVE` before deploying backend code
- **Rollback:** Remove the GSI (non-destructive to data)
- **Backend archive refresh:** Required (all 13 Lambdas share backend package)

## Approval Gates (Sequential)

1. Matthew reviews this GSI design
2. Saved Terraform plan for the GSI addition
3. Reviewed Terraform apply (GSI begins backfilling)
4. Wait for GSI IndexStatus = ACTIVE
5. Backend pet_handler update (replace Scan with Query) + tests
6. Saved backend Terraform plan (13 Lambda refresh)
7. Backend apply + smoke validation
8. Frontend pet inventory implementation
9. Frontend deployment approval

---

## Workflow Validation Status (Corrected)

| Workflow | Status |
|----------|--------|
| Create client (profile only) | Implemented, automated-test covered |
| Create client (onboard + Cognito) | Implemented, automated-test covered |
| Edit client | Implemented, automated-test covered |
| Disable/enable client | Implemented, automated-test covered |
| Link Cognito | Implemented, automated-test covered |
| Unlink | Implemented |
| Delete profile | Implemented |
| Delete Cognito | Implemented |
| Resend invite | Implemented, automated-test covered |
| Reset password | Implemented |
| Set temp password | Implemented |
| Auto-create client on approval | Implemented, automated-test covered |
| Pet CRUD | Implemented, automated-test covered (uses Scan) |
| Pet auto-create on approval | Implemented, automated-test covered |
| GET /admin/clients | **Production validated** (Phase 1A) |
| Client Management frontend | **Production validated** (Phase 1B.1) |

---

## What Was NOT Done

- ❌ No GSI created (requires Terraform approval)
- ❌ No backend code changed
- ❌ No frontend pet inventory added
- ❌ No deployment
- ❌ No production-data modification or inspection

## Next Step

Matthew reviews this GSI design. If approved, proceed to a saved Terraform plan for the ClientPetIndex addition.
