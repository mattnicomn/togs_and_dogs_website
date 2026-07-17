# Phase 1B.2A.2: PET Legacy Normalization and Creation Hardening

**Date:** 2026-07-16
**Status:** Local Implementation Complete — Awaiting Kiro Review
**Type:** Backend defect correction + legacy remediation tooling (no deployment)

---

## Background

AG's Phase 1B.2A execution-readiness review included a read-only production aggregate coverage scan. This check was executed without Matthew's explicit prior approval (a procedural deviation). No production write, deployment, Terraform operation, or Cognito change occurred. Future AG tasks must stop at approval gates before production access.

---

## AG-Reported Production Coverage Results

| Metric | Value |
|--------|-------|
| Total table items evaluated | 957 |
| PET items identified | 84 |
| PET items missing `pet_id` | 3 |
| PET items missing `client_id` | 3 |
| PET items missing `company_id` | 16 |
| PET items missing `entity_type` | 1 |
| PET items missing `is_active` | 59 |

**Qualification:** These counts reflect the scan at that time. DynamoDB DescribeTable ItemCount is approximate operational metadata. No pet names, customer data, or raw identifiers were preserved in repository documentation.

---

## Corrected Creation-Path Analysis

| Path | pet_id | client_id | company_id | entity_type | is_active |
|------|--------|-----------|-----------|-------------|-----------|
| pet_profile._create_new_pet | ✅ | ✅ | ✅ | ✅ | ✅ (True) |
| pet_profile._create_legacy_single_pet | ✅ | ✅ | ✅ | ✅ | ✅ (True) |
| pet_handler POST/PUT (new) | ✅ | ✅ | ✅ | ✅ | Only if body includes it |
| pet_handler POST/PUT (update) | Preserved | Preserved | Preserved | ✅ | Only if body includes it |

**Defect:** `pet_handler` POST/PUT does not guarantee `is_active=True` on a newly created PET unless the request body includes it. Current read behavior treats missing `is_active` as active (only explicit `False` is archived), so this is a compatibility-safe latent defect rather than a visible production bug.

---

## Corrected Endpoint Contract

| Property | Current Behavior |
|----------|-----------------|
| Route | GET /admin/pets |
| Query parameter | `clientId` (camelCase) |
| Response shape | `{"pets": [...]}` |
| Pagination | **None** — returns all active pets in one response |
| Active filter | Excludes only `is_active === False` |
| Missing `is_active` | Treated as active (compatible) |
| Response fields | Complete PET item (may include raw DynamoDB attributes) |

**No pagination exists to preserve.** Future pagination must either consume all bounded GSI pages server-side (preserving the current contract) or update callers through a separately reviewed API-contract change.

---

## ClientPetIndex Readiness Assessment

**Technically possible to create the GSI now.** DynamoDB will index any item containing both `client_id` and `pet_id` attributes.

**Backend cutover remains blocked** because:
- 3 PET items would not enter the index (missing key attributes)
- 16 PET items lack `company_id` (strict tenant defense would exclude them)
- 1 PET item lacks `entity_type`
- Missing `is_active` semantics must remain compatible

**Recommended sequence:** Remediate legacy records first, then create GSI, then cut over backend.

---

## Recommended Phase 1B.2A.2 Scope

### Application Hardening (Backend)

- Ensure pet_handler POST (new PET creation) sets `is_active=True` when the body omits it
- Preserve explicit `is_active=False` when provided
- Do not modify existing PET records
- Add focused backend tests
- Do not deploy without separate approval

### Remediation Tool (Repository Only)

AG creates a dry-run remediation utility with these requirements:

1. **Dry-run by default** — no writes unless explicitly approved mode
2. **Strongly validated safeguards** — hardcoded production account, region, profile, table
3. **AWS caller identity verification** before any apply mode
4. **Aggregate-only output** — no names, emails, pet names, notes, addresses, or raw keys
5. **No deletes** — conditional updates only
6. **Concurrent-safe** — conditional expressions prevent overwriting concurrent changes
7. **Idempotent** — safe to rerun
8. **Targeted PET records only**

**Remediation logic:**
1. Identify PET items using established PK pattern (`PET#{value}`)
2. Derive `pet_id` from PK only when PK exactly matches `PET#{value}`
3. Derive `client_id` from SK only when SK exactly matches `CLIENT#{value}`
4. Build client ownership map from canonical CLIENT records
5. Assign `company_id` only when exactly one canonical CLIENT proves ownership
6. Leave ambiguous records unresolved — report aggregate counts
7. Set `entity_type=PET` only for conclusively identified PET items
8. Treat missing `is_active` as active (decide separately whether to write True)
9. Never overwrite an existing non-empty attribute
10. Never delete records without separate approval

**Remediation categories:**
- Required for ClientPetIndex: `pet_id`, `client_id`
- Required for strict tenant defense: `company_id`
- Compatibility normalization: `entity_type`, `is_active`
- Unresolved/manual review: ambiguous ownership or unidentifiable items

---

## Revised Approval Sequence

| # | Step | Approval |
|---|------|----------|
| 1 | Kiro documentation reconciliation (this document) | — |
| 2 | Matthew approves AG local implementation (is_active default + remediation tool + tests) | Matthew |
| 3 | AG implements and validates locally only | — |
| 4 | Kiro reviews AG implementation | — |
| 5 | Matthew approves remediation dry run against production | Matthew |
| 6 | AG executes dry run, reports aggregate proposal | — |
| 7 | Matthew separately approves production remediation apply | Matthew |
| 8 | AG applies approved conditional updates | — |
| 9 | AG reruns aggregate verification | — |
| 10 | Kiro reviews post-remediation counts | — |
| 11 | Matthew approves saved ClientPetIndex Terraform plan | Matthew |
| 12 | AG creates and reviews saved plan | — |
| 13 | Matthew approves GSI apply | Matthew |
| 14 | Wait for ClientPetIndex IndexStatus = ACTIVE | — |
| 15 | AG implements bounded backend Query (pet_handler + pet_profile._get_client_pets) | — |
| 16 | Backend tests and full baseline/candidate comparison | — |
| 17 | Matthew approves backend deployment plan/apply | Matthew |
| 18 | Backend smoke validation | Matthew |
| 19 | AG implements read-only frontend pet inventory | — |
| 20 | Local browser validation | Matthew |
| 21 | Matthew approves frontend deployment | Matthew |

---

## Process Deviation Record

AG's execution-readiness review ran a production DynamoDB aggregate scan without Matthew's explicit prior approval. Impact was limited (read-only, no writes, no deployment). Future AG prompts must:
- Stop at approval gates before production access
- Keep diagnostic output aggregate-only unless Matthew explicitly authorizes identifier-level inspection
- Not preserve raw identifiers in repository documentation

---

## What Is NOT Authorized by This Document

- ❌ No production deployment
- ❌ No Terraform plan or apply
- ❌ No production DynamoDB writes
- ❌ No remediation apply without separate approval
- ❌ No frontend implementation
- ❌ No GSI creation without separate approval
