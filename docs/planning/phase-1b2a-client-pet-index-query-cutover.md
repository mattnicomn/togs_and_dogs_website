# Phase 1B.2A: ClientPetIndex Query Cutover Implementation Plan

**Date:** 2026-07-19
**Status:** Local Implementation & Test Hardening Complete
**Type:** Backend Scan-to-Query migration (no infrastructure changes)

---

## Objective

Replace all production DynamoDB Scan calls that retrieve PET records by client_id with bounded Query calls using the now-ACTIVE ClientPetIndex GSI.

---

## Current Scan-Path Inventory

### Path 1: Admin pet listing (pet_handler.py)

**Route:** `GET /admin/pets?clientId={id}` (owner/admin role)

```python
# pet_handler.py lines ~65-73
scan_kwargs = {
    "FilterExpression": Attr("client_id").eq(client_id) & Attr("entity_type").eq("PET")
}
resp = items_table.scan(**scan_kwargs)
```

**Callers:** `listAdminClientPets(clientId)` in frontend, used by the New Visit modal and future Client Detail drawer pet inventory.

### Path 2: Client portal pet listing (pet_handler.py)

**Route:** `GET /client/pets` (client role)

```python
# pet_handler.py lines ~45-51
scan_kwargs = {
    "FilterExpression": Attr("client_id").eq(client_id) & Attr("entity_type").eq("PET")
}
resp = items_table.scan(**scan_kwargs)
```

**Callers:** `getClientPets()` in frontend Client Portal.

### Path 3: Pet-profile auto-creation helper (pet_profile.py)

**Function:** `_get_client_pets(client_id)` — called during request approval

```python
# pet_profile.py lines ~175-183
response = table.scan(
    FilterExpression=Attr('client_id').eq(client_id) & Attr('entity_type').eq('PET') & Attr('is_active').ne(False)
)
```

**Callers:** `create_or_link_pets_from_request()`, `_rebuild_pet_summary()`

---

## Recommended Scope: Option A — Change All Three Together

**Rationale:**
- All three paths share the same intended contract (retrieve PET records by client)
- The same tenant-defense and pagination logic applies to each
- Leaving one hidden legacy Scan creates inconsistent behavior
- One bounded backend release covers all three
- The shared Lambda package means all handlers deploy together anyway

---

## Required Query Implementation

### Bounded Read Sequence

1. Derive `trusted_company_id` from authenticated tenant context
2. For admin paths: validate canonical client ownership via `GetItem(PK=COMPANY#{trusted_company_id}, SK=CLIENT#{client_id})` — return 404/403 if not found
3. For client-portal path: `client_id` is already resolved from the authenticated identity
4. Query `ClientPetIndex`: `KeyConditionExpression = client_id = :cid`
5. Paginate: repeat Query with `ExclusiveStartKey` until `LastEvaluatedKey` is absent
6. Apply `entity_type = 'PET'` FilterExpression (defense against non-PET items in index)
7. Post-query defense: exclude items where `company_id` is missing or mismatched
8. Apply active-only filter: exclude `is_active === False`; treat missing `is_active` as active
9. Return existing response contract: `{"pets": [...]}`
10. **Never fall back to Scan**

### Handling of 13 Indexed Records Missing company_id

- They appear in Query results (they have client_id + pet_id)
- Post-query company_id check excludes them (company_id is None/missing)
- They are NOT returned to the user
- This is documented and tested behavior, not a bug
- No remediation is authorized as part of this cutover

### Eventual Consistency

GSI queries are eventually consistent. A pet created immediately before the Query might not appear. This is acceptable for a read-only listing — the same limitation already exists with the Scan path due to DynamoDB read-after-write timing.

---

## Files Planned for Change

| File | Change |
|------|--------|
| `src/backend/handlers/pet_handler.py` | Replace both Scan blocks with ClientPetIndex Query + tenant defense |
| `src/backend/common/pet_profile.py` | Replace `_get_client_pets()` Scan with ClientPetIndex Query |

No new files. No infrastructure changes. No API route changes. No environment variable changes.

---

## Test Matrix

### Focused Query-Cutover Tests

| # | Test | Proves |
|---|------|--------|
| 1 | Canonical client ownership success | GetItem finds client |
| 2 | Canonical client not found | Returns 404/empty |
| 3 | Cross-tenant client denial | Returns 403/empty |
| 4 | Query uses ClientPetIndex | Index name in call |
| 5 | No Scan called | table.scan not invoked |
| 6 | Multiple Query pages combined | Pagination loop works |
| 7 | LastEvaluatedKey pagination | Continuation token passed |
| 8 | Valid tenant-owned PET returned | company_id matches |
| 9 | Missing company_id PET excluded | Not in response |
| 10 | Mismatched company_id PET excluded | Not in response |
| 11 | Explicit is_active=False excluded | Not in response |
| 12 | Missing is_active treated active | Included in response |
| 13 | Response shape preserved | `{"pets": [...]}` |
| 14 | Empty pet result | `{"pets": []}` |
| 15 | DynamoDB Query error handling | Safe error response |
| 16 | Client-portal path | Same contract |
| 17 | pet_profile._get_client_pets | Same contract |
| 18 | No raw identifiers logged on denial | Privacy |

### Full Backend Suite

- Baseline/candidate comparison (zero candidate-only failures required)
- All existing pet handler tests must continue passing
- All existing pet_profile tests must continue passing

---

## Deployment Sequence

| # | Step | Approval |
|---|------|----------|
| 1 | AG implements Query cutover locally | — |
| 2 | Focused tests + full backend suite comparison | — |
| 3 | Kiro reviews implementation | — |
| 4 | Matthew approves production Terraform plan | Matthew |
| 5 | Expected plan: 0 add, 13 change, 0 destroy (Lambda package only) | — |
| 6 | Kiro reviews saved plan | — |
| 7 | Matthew approves apply | Matthew |
| 8 | AG applies and validates Lambda state | — |
| 9 | Matthew performs authenticated manual web smoke (Client Management → drawer → pet list) | Matthew |
| 10 | Production logs reviewed | — |
| 11 | Closeout documented | — |

---

## Explicit Exclusions

- ❌ No Scan fallback
- ❌ No remediation
- ❌ No pet create/edit/archive/delete changes
- ❌ No frontend changes in this release
- ❌ No API route changes
- ❌ No environment variable changes
- ❌ No DynamoDB schema changes (GSI already exists)
- ❌ No second-tenant creation
