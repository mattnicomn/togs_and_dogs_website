# Phase 1B.2A: Pet Read-Path Audit and Design Recommendation

**Date:** 2026-07-16
**Status:** ⚠️ BLOCKED — GSI Required Before Frontend Implementation
**Type:** Architecture audit and design recommendation

---

## Finding: Unbounded Table Scan

The current GET /admin/pets endpoint uses a **full DynamoDB table Scan** with a client-side FilterExpression. This reads every item in the entire single-table database to find pets matching a specific client_id.

### Current PET Key Schema

```
PK: PET#{pet_id}       (globally unique)
SK: CLIENT#{client_id}  (owner association)
```

### Current Query Behavior

```python
# pet_handler.py — GET /admin/pets?clientId={id}
scan_kwargs = {
    "FilterExpression": Attr("client_id").eq(client_id) & Attr("entity_type").eq("PET")
}
resp = items_table.scan(**scan_kwargs)
```

This Scan:
- Reads every item in the table (all tenants, all entity types)
- Applies FilterExpression after reading (consumes full read capacity)
- Returns only matching items but charges for all items evaluated
- Has no natural pagination boundary per client
- Performance degrades linearly with total table size
- Is not safe to trigger on every Client Detail drawer open

### Why a Bounded Query Is Not Possible Without Changes

- PET items use `PK = PET#{pet_id}` — no partition groups pets by client or tenant
- No GSI exists on `client_id` or `entity_type`
- The existing StatusIndex and WorkerIndex GSIs do not help
- DynamoDB requires a partition key for bounded Query operations

---

## Proposed Solution: Client-Entity GSI

### Option 1 — GSI on client_id (Recommended)

Add a GSI that enables direct Query by client_id:

```
GSI Name: ClientEntityIndex
Partition Key: client_id (String)
Sort Key: entity_type (String) — or PK for uniqueness
Projection: ALL (or KEYS_ONLY + needed fields)
```

**Query pattern:**
```python
response = table.query(
    IndexName='ClientEntityIndex',
    KeyConditionExpression=Key('client_id').eq(client_id) & Key('entity_type').eq('PET')
)
```

**Advantages:**
- Bounded read — only items with matching client_id are evaluated
- Sort key can distinguish PET from other entity types
- Supports pagination via LastEvaluatedKey
- No migration needed — DynamoDB backfills the GSI automatically
- Existing items with `client_id` attribute are indexed immediately

**Considerations:**
- GSI applies to ALL items with a `client_id` attribute (not just PETs)
- Request items also have `client_id` — they would appear in this index too
- Using `entity_type` as sort key provides clean filtering
- Additional read capacity consumed for index maintenance

### Option 2 — Restructure PET Keys (Not Recommended Now)

Move PET items under a tenant-partitioned key:
```
PK: COMPANY#{company_id}
SK: PET#{pet_id}#CLIENT#{client_id}
```

**Rejected because:**
- Requires data migration of all existing PET records
- Breaks existing pet_handler and pet_profile code
- Higher risk for a read-path improvement

### Option 3 — SK-Based Sparse GSI

```
GSI: PetClientIndex
Partition Key: SK (CLIENT#{client_id})
Sort Key: PK (PET#{pet_id})
Projection: ALL
Condition: entity_type = 'PET'
```

**Note:** DynamoDB GSIs cannot have conditions — all items with SK matching the pattern would be indexed. Since many item types use `CLIENT#` sort keys (REQ items use `SK = CLIENT#{id}` too), this GSI would include non-PET items.

**Mitigation:** Filter `entity_type = 'PET'` at query time. Still bounded to the `SK = CLIENT#{client_id}` partition.

---

## Recommended Path Forward

1. **Add ClientEntityIndex GSI** via Terraform (Option 1)
2. **Update pet_handler** to use Query with the GSI when client_id is provided
3. **Preserve Scan fallback** for any existing call path that doesn't provide client_id
4. **Add pagination support** using LastEvaluatedKey
5. **Apply tenant filtering** post-query (verify company_id matches caller)
6. **Frontend implementation** proceeds only after the bounded query is deployed

### Terraform Scope

- Add one `attribute` definition for `entity_type` (if not already declared)
- Add one `global_secondary_index` block
- Expected plan: 1 resource changed in-place (DynamoDB table update)
- GSI backfill is automatic and non-blocking
- No downtime during GSI creation
- Existing reads/writes are unaffected

### Migration/Backfill

- **None required** — existing PET items already have `client_id` and `entity_type` attributes
- DynamoDB automatically populates the GSI with existing items
- Backfill time depends on table size (typically minutes for small tables)

### Rollout Sequence

1. Terraform plan (adds GSI) — requires Matthew approval
2. Terraform apply — GSI begins backfilling
3. Wait for GSI status = ACTIVE
4. Deploy backend update (pet_handler uses Query when GSI is ready)
5. Deploy frontend (drawer uses the bounded endpoint)
6. Each step requires separate approval

---

## Workflow Validation Status Correction

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

- ❌ No frontend pet inventory added (blocked on Scan replacement)
- ❌ No GSI created (requires Terraform approval)
- ❌ No backend code changed
- ❌ No deployment
- ❌ No production-data modification

## Next Steps (Require Separate Approvals)

1. Matthew reviews and approves the GSI design
2. Terraform plan for ClientEntityIndex GSI addition
3. Terraform apply
4. Backend pet_handler update to use Query
5. Frontend pet inventory in drawer
6. Frontend deployment
