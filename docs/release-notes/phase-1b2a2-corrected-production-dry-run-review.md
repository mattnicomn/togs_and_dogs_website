# Phase 1B.2A.2: Corrected Production Dry-Run Results Review

**Date:** 2026-07-17
**Reviewer:** Kiro
**Status:** DEFER PARTIAL REMEDIATION

---

## Dry-Run Comparison

| Metric | First Run | Corrected Run | Change |
|--------|-----------|---------------|--------|
| Total PET items | 84 | 84 | — |
| Complete | 25 | 25 | — |
| Malformed SK | 35 | **0** | ✅ Fixed |
| Eligible full remediation | 0 | 0 | — |
| Eligible partial remediation | 0 | **3** | ✅ Detected |
| Missing-is_active-only | — | **43** | New category |
| Manual review | 28 | **13** | ✅ Reduced |
| Disposition invariant | Failed | **84 = 84** | ✅ Passes |

**Classifier correction validated.** The parser fix resolved all 35 false malformed-SK classifications.

---

## Disposition Invariant: CONFIRMED

25 + 0 + 3 + 43 + 13 = 84 ✅

---

## Relationship: 16 Ownership-Not-Found = 3 Partial + 13 Manual-Review

Code logic confirmed:
- **3 partial-remediation records:** Missing company_id (unresolved) AND missing other derivable fields (pet_id/client_id/entity_type). The utility proposes pet_id + client_id + entity_type but cannot propose company_id.
- **13 manual-review records:** Missing company_id (unresolved) but all other structural fields (pet_id, client_id, entity_type) already present. Nothing can be safely proposed → manual review.

These 16 records reference client IDs for which no canonical `COMPANY#{x}/CLIENT#{y}` record exists in the table. This may represent:
- Deleted client profiles
- Historical test data
- Intake-linked clients that were never formally created
- Records from before the canonical client model was enforced

The root cause cannot be determined without record-level inspection, which requires separate approval.

---

## Partial-Remediation Assessment: Option B — DEFER

### Why Option A (apply now) is NOT recommended:

The 3 partial-remediation records would receive `pet_id`, `client_id`, and `entity_type`. This makes them eligible for **ClientPetIndex participation**. However:

1. **They still lack `company_id`.** The planned bounded backend flow requires `company_id` validation as defense-in-depth after the GSI query.
2. **Indexed-but-tenant-unreachable state:** These records would appear in the GSI but would be excluded by the post-query `company_id` check. This creates an intermediate state that is neither useful nor harmful — merely cosmetic index participation with no operational benefit.
3. **The backend cutover is already blocked** on the 16 ownership-not-found records regardless of whether these 3 get partial attributes. The blocking issue is company_id, not pet_id/client_id/entity_type.
4. **Risk/reward ratio:** 3 production conditional writes for zero user-facing improvement until ownership is resolved.

### Why Option B (defer) IS recommended:

- The 3 records are structurally valid but tenant-unresolvable
- Adding pet_id/client_id/entity_type without company_id provides no operational benefit under the planned backend
- A coherent remediation of all 16 ownership-not-found records (after manual review) would include these 3 naturally
- Zero production writes means zero production risk

---

## Tenant-Defense Under the Planned Backend Flow

### Records with company_id (68 of 84):
1. Admin requests GET /admin/pets?clientId=X
2. Backend resolves trusted company_id from claims
3. GetItem: `COMPANY#{company_id}/CLIENT#{X}` → confirms ownership
4. Query ClientPetIndex by client_id
5. Post-query: validate each pet's company_id matches
6. Return matching pets ✅

### 3 Partial-remediation records (missing company_id):
Even if partially remediated with pet_id/client_id/entity_type:
- They enter the ClientPetIndex (have client_id + pet_id)
- Backend queries by client_id → they appear in results
- Post-query company_id check → **they are excluded** (company_id is None/missing)
- Not returned to the user
- Operationally invisible

### 13 Manual-review records (missing company_id, all other fields present):
- Already have pet_id and client_id → already eligible for ClientPetIndex
- Same post-query exclusion applies → operationally invisible

**Conclusion:** The GSI can be created now. The 16 ownership-unresolved records will enter the index but be safely excluded by the tenant defense-in-depth check. No user-facing data leakage.

---

## Revised GSI Readiness Assessment

The ClientPetIndex can proceed **without remediation apply** because:
- 68 of 84 PET records have all required attributes including company_id
- The 16 without company_id will be safely excluded by post-query defense
- The 3 without pet_id/client_id won't enter the GSI at all (GSI requires both key attributes)
- No data corruption or tenant leakage is possible

**The blocking issue was never the remediation — it was the Scan.** The GSI eliminates the Scan. Tenant defense handles the incomplete records.

---

## is_active Historical Normalization: DEFER

- 59 records missing is_active (43 compatibility-handled + 16 with other issues)
- Current reads treat missing as active — compatible and correct
- New creation hardened — no new records will lack is_active
- Historical normalization provides no operational benefit
- **Recommend: leave compatibility-handled indefinitely.** Normalize only if a future query or index requires is_active as a partition/sort key.

---

## Handling Recommendation for 16 Ownership-Not-Found

**Recommend: Leave unresolved for now. Proceed with GSI creation.**

These records are operationally invisible under the tenant-defense backend flow. A future manual-review workflow can be designed separately if there is business value in recovering orphaned pet data. No current user or workflow depends on accessing tenant-unresolvable PET records.

If Matthew later wants to investigate, a separately approved privacy-minimized reconciliation utility (showing only aggregate categories, not names/data) would be appropriate.

---

## Recommended Next Approval Gate

### DEFER PARTIAL REMEDIATION

The partial remediation provides no operational benefit. Proceed directly to:

1. **Matthew approves saved ClientPetIndex Terraform plan** — adds the GSI to the production DynamoDB table
2. AG creates the Terraform plan (add GSI attribute + global_secondary_index)
3. Review the saved plan
4. Matthew approves apply
5. Wait for GSI IndexStatus = ACTIVE
6. AG implements bounded backend Query (replace Scan with GSI Query + tenant defense)
7. Backend tests and full baseline/candidate comparison
8. Separate backend deployment approval

The 3 records lacking pet_id/client_id simply won't appear in the GSI (DynamoDB only indexes items with both key attributes present). This is correct behavior — they remain accessible only via the legacy Scan path, which will be deprecated.

---

## What Was NOT Done

- ❌ No remediation apply
- ❌ No AWS access during this review
- ❌ No code changes
- ❌ No Terraform
- ❌ No deployment
- ❌ No production-data modification
- ❌ No record-level inspection
