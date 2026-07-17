# Phase 1B.2A: Pet Read-Path — AG Execution Handoff

**Date:** 2026-07-16
**From:** Kiro (strategic planning, architecture review)
**To:** AG (implementation, testing, deployment execution)
**Status:** Kiro planning complete — awaiting AG execution-readiness review

---

## Current Production State

- Phase 1A backend compatibility: **production validated**
- Phase 1B.1 Client Management frontend: **production validated**
- Current production client drawer: uses summary pet fields (pet_names_summary, pet_breeds_summary) from the client list response only
- No detailed drawer pet request has been implemented
- Existing `GET /admin/pets?clientId={id}` uses a **table-wide DynamoDB Scan** — blocked from frontend use until replaced

## Repository State and Key Commits

| Commit | Description |
|--------|-------------|
| `4a7817c` | Phase 1B.1 production deployment closeout |
| `616ba75` | Phase 1B.2 workflow and pet-lifecycle audit |
| `6092fae` | Scan blocker identified; initial index proposal |
| `1ee5a97` | Refined ClientPetIndex design with tenant-isolation review |

**Current HEAD:** `1ee5a97` on `main`, pushed to `origin/main`.

---

## Existing Data Model

| Item | Value |
|------|-------|
| DynamoDB resource | `module.data.aws_dynamodb_table.main` |
| Production table | `togs-and-dogs-prod-data` |
| Billing mode | PAY_PER_REQUEST (on-demand) |
| PET key pattern | PK = `PET#{pet_id}`, SK = `CLIENT#{client_id}` |
| Existing GSIs | StatusIndex (status + created_at), WorkerIndex (worker_id + assigned_at) |
| Existing endpoint parameter | `clientId` (camelCase query param) |
| Existing response contract | `{ "pets": [...] }` — must be preserved |
| CLIENT canonical | Yes — `household_id = client_id`, no HOUSEHOLD items |

## PET Attribute Coverage Assessment

All identified current PET creation paths (pet_profile._create_new_pet, pet_profile._create_legacy_single_pet, pet_handler POST/PUT) write: `pet_id`, `client_id`, `company_id`, `entity_type`, and `is_active`.

**Important qualification:** Historical production attribute completeness has NOT been empirically verified. Records predating the Release 4 pet_profile implementation may theoretically exist with different attribute patterns. Before GSI apply or backend cutover, a separately approved read-only aggregate coverage check (returning counts only, no pet/customer data) must confirm that all PET items contain both `client_id` and `pet_id` attributes.

Any PET item missing `client_id` or `pet_id` would not appear in the GSI and would require a separately reviewed remediation plan.

---

## Recommended Index Design

| Property | Value |
|----------|-------|
| Name | ClientPetIndex |
| Partition key | `client_id` (String) |
| Sort key | `pet_id` (String) |
| Projection | Current recommendation is ALL — AG must independently evaluate ALL versus INCLUDE before implementation |

**`client_id` is an access path, not an authorization boundary.** Authorization must be confirmed separately before any GSI query.

---

## Required Tenant-Isolation Flow

1. Resolve trusted `company_id` from authenticated Cognito claims
2. Direct GetItem: `PK = COMPANY#{company_id}`, `SK = CLIENT#{client_id}` — confirms client belongs to tenant
3. If not found → return normal 404/403 (client not owned by this tenant)
4. Query ClientPetIndex by `client_id`
5. Apply `entity_type = 'PET'` FilterExpression as defense against non-PET items
6. Validate returned `company_id` values match trusted context (defense in depth)
7. Apply active/archive filter per existing behavior
8. Return existing compatible response shape with optional pagination token
9. **Never fall back to Scan** — missing index data must fail safely or be reported

---

## Open Verification Items for AG

- [ ] Independently verify every PET creation path
- [ ] Verify whether legacy records may predate those paths
- [ ] Determine exact response fields needed to choose ALL versus INCLUDE projection
- [ ] Verify current pagination-token conventions
- [ ] Verify active/archive parameter behavior
- [ ] Verify the exact API Gateway route and Lambda handler
- [ ] Verify DynamoDB GSI quotas and Terraform definitions
- [ ] Design a sanitized aggregate production coverage check (counts only, no customer data) — do not execute without Matthew's approval
- [ ] Determine whether any missing-key records would require remediation before backend cutover

---

## Expected Implementation Sequence

| # | Step | Approval Required |
|---|------|-------------------|
| 1 | AG repository/document/code review | — |
| 2 | AG execution-readiness report | — |
| 3 | Sanitized production attribute-coverage check | Matthew approval |
| 4 | Kiro reviews AG coverage findings | — |
| 5 | Saved GSI Terraform plan | Matthew approval |
| 6 | Review saved plan | — |
| 7 | GSI Terraform apply | Matthew approval |
| 8 | Wait for GSI IndexStatus = ACTIVE | — |
| 9 | Backend bounded Query implementation + tests | — |
| 10 | Full baseline/candidate comparison | — |
| 11 | Backend deployment plan/apply | Matthew approval |
| 12 | Production backend smoke validation | Matthew |
| 13 | Frontend read-only pet inventory implementation | — |
| 14 | Local browser validation | Matthew |
| 15 | Frontend deployment | Matthew approval |

---

## Explicit Exclusions

- ❌ No Scan fallback in the new implementation
- ❌ No PET write changes
- ❌ No pet create/edit/archive/delete UI
- ❌ No HOUSEHOLD item creation
- ❌ No CLIENT migration
- ❌ No email auto-merge
- ❌ No Cognito auto-link
- ❌ No second tenant creation
- ❌ No TENANT_RESOLUTION_MODE change
- ❌ No Google Play publication
- ❌ No production deployment without explicit Matthew approval at each gate

---

## Acceptance Criteria for AG's Initial Review

AG should report:
- Exact files likely to change
- Exact Terraform resource expected to change
- Legacy attribute risk assessment
- Projection recommendation (ALL vs INCLUDE with justification)
- Endpoint compatibility findings
- Testing plan
- Production coverage-check proposal (counts-only, no data)
- Approval gates identified
- **READY FOR EXECUTION** or **NOT READY**

---

## Role Boundaries After Handoff

| Role | Kiro | AG |
|------|------|-----|
| Strategic planning | ✅ | |
| Architecture review | ✅ | |
| Backlog and continuity | ✅ | |
| Implementation | | ✅ |
| Automated testing | | ✅ |
| Baseline/candidate validation | | ✅ |
| Terraform planning (after approval) | | ✅ |
| Deployment (after approval) | | ✅ |
| Operational/smoke validation | | ✅ |
| Review of AG output | ✅ | |
| Approval gate recommendations | ✅ | |
