# Phase 1B.2A: Backend and GSI Deployment Sequencing

**Date:** 2026-07-17
**Status:** Planning — Awaiting Matthew approval for sequencing approach
**Type:** Deployment strategy (no code or infrastructure changes)

---

## Sequencing Problem

The repository currently contains:
- `cda722a` — ClientPetIndex GSI Terraform configuration (committed to `modules/data/main.tf`)
- `ca73d93` — PET is_active creation hardening (committed to `src/backend/handlers/pet_handler.py`)

A normal full Terraform plan from current `main` will always include **both**:
- `module.data.aws_dynamodb_table.main` (GSI addition)
- 13 Lambda `source_code_hash` updates (backend code delta)

These must be deployed in separate, independently reviewed operations. The GSI configuration being already committed prevents generating a clean backend-only plan.

---

## Options Compared

### Option 1 — Temporary GSI Configuration Revert (RECOMMENDED)

| Criterion | Assessment |
|-----------|-----------|
| Normal full-plan behavior | ✅ Preserved |
| Audit clarity | ✅ Clear git history: revert → backend deploy → restore → GSI deploy |
| Operational safety | ✅ Each plan contains exactly the intended scope |
| Rollback boundaries | ✅ Independent for backend and GSI |
| Git-history impact | Minor — revert + restore commits are explicit and documented |
| Risk of losing GSI design | None — `cda722a` remains in history; restore is a cherry-pick or re-apply |
| Complexity | Low — standard git revert workflow |

**Sequence:**
1. Create a bounded commit that removes only the ClientPetIndex configuration from `modules/data/main.tf`
2. Generate a normal full Terraform plan from that commit
3. Verify plan shows only 13 Lambda updates (0 add, 13 change, 0 destroy)
4. Matthew approves backend plan
5. Apply and validate backend deployment
6. Restore ClientPetIndex configuration (re-apply `cda722a` changes or cherry-pick)
7. Generate a new normal full plan
8. Verify plan shows only DynamoDB table (0 add, 1 change, 0 destroy)
9. Matthew approves GSI plan
10. Apply GSI and wait for ACTIVE

### Option 2 — Feature Gate Variable

| Criterion | Assessment |
|-----------|-----------|
| Normal full-plan behavior | ⚠️ Partially — requires variable management |
| Audit clarity | ⚠️ Conditional Terraform less transparent |
| Operational safety | ✅ When gate is off, GSI excluded |
| Complexity | High — conditional `dynamic` blocks for GSI and attributes |
| Justified for one-time problem | ❌ Permanent config complexity for temporary sequencing |
| Validation | Requires testing both gate states |

**Verdict:** Over-engineered for a one-time deployment ordering problem. Not recommended.

### Option 3 — Exceptional Targeted Backend Plan

| Criterion | Assessment |
|-----------|-----------|
| Normal full-plan behavior | ❌ Violates — uses `-target` |
| Terraform warnings | ⚠️ Terraform warns that targeted apply may leave incomplete state |
| Risk | Medium — dependencies between Lambda and DynamoDB could cause drift |
| Post-apply requirement | Full plan needed afterward to reconcile |
| 13 explicit targets | Operationally complex command |

**Verdict:** Exceptional fallback only. Not preferred when a cleaner alternative exists.

### Option 4 — Apply from Pre-GSI Branch/Worktree

| Criterion | Assessment |
|-----------|-----------|
| Audit clarity | ❌ Applies infrastructure from an unmerged/diverged configuration |
| Risk | High — production state diverges from `main` |
| Project conventions | ❌ Violates normal release-from-main workflow |

**Verdict:** Not acceptable.

---

## Recommended Approach: TEMPORARY GSI CONFIGURATION REVERT

### Exact Steps

**Phase A — Backend Deployment (PET is_active hardening)**

| # | Step | Approval |
|---|------|----------|
| 1 | ✅ AG creates a bounded commit removing ClientPetIndex from `modules/data/main.tf` (commit `f3b9a79`) | — |
| 2 | ✅ AG validates: `terraform fmt -check`, `terraform validate` | — |
| 3 | ✅ AG generates a normal full Terraform plan (`phase-1b2a-backend-only.tfplan`) | — |
| 4 | ✅ Kiro reviews: confirms plan shows 0 add, 13 change, 0 destroy (Lambda-only) | — |
| 5 | ✅ Matthew approves backend deployment plan | Matthew |
| 6 | ✅ AG applies the saved plan | — |
| 7 | ✅ AG verifies all 13 Lambda functions Active/Successful | — |
| 8 | Matthew validates PET creation behavior and existing endpoint stability | Matthew |

**Phase B — GSI Deployment (ClientPetIndex)**

| # | Step | Approval |
|---|------|----------|
| 9 | ✅ AG restores ClientPetIndex configuration (re-applied changes in commit `757cabb`) | — |
| 10 | ✅ AG validates: `terraform fmt -check`, `terraform validate` | — |
| 11 | ✅ AG generates a normal full Terraform plan (`phase-1b2a-client-pet-index-gsi-only.tfplan`) | — |
| 12 | Kiro reviews: confirms plan shows 0 add, 1 change, 0 destroy (DynamoDB-only) | — |
| 13 | Matthew approves GSI plan | Matthew |
| 14 | AG applies the saved plan | — |
| 15 | AG monitors GSI IndexStatus until ACTIVE | — |
| 16 | Proceed to bounded backend Query implementation | — |

### Why This Is Safest

- Each Terraform plan contains exactly one concern
- Normal `terraform plan` (no `-target`) is used throughout
- Git history is explicit: revert → deploy backend → restore → deploy GSI
- If either deployment encounters issues, rollback is bounded to that concern
- No conditional configuration complexity remains permanently
- The approved GSI design from `cda722a` is never lost (remains in git history)

---

## Backend Archive Readiness Audit (Complete)

AG has completed the backend archive readiness audit:
- Confirmed the exact production-deployed baseline commit is `234b51d` (confidence: EXACT BASELINE CONFIRMED).
- Confirmed `ca73d93` (pet_handler `is_active` default) is the only application behavior change in `src/backend`.
- Ran full backend test comparison and confirmed zero candidate-only failures (725 collected, 654 passed, 71 failed, matching the baseline).
- Identified archive hygiene issues: untracked caches (`.pytest_cache/` and `__pycache__/` directories) exist under `src/backend/` and would be packaged. Therefore, the package is classified as **NOT READY** until a local cleanup is executed.

---

## Current State Summary

- Existing saved plan (`phase-1b2a-client-pet-index.tfplan`): NOT apply-ready, retained as review evidence
- ClientPetIndex: configured in repository, NOT deployed
- PET is_active hardening: committed, NOT deployed
- Backend archive: deterministic excludes implemented, local caches blocked
- Latest production backend: Phase 1A (`234b51d`)
- Latest production frontend: Phase 1B.1 (`51b78bf`)
- Remediation: deferred
- Frontend pet inventory: deferred

---

## What Is NOT Authorized

- ❌ No production Terraform plan/apply/refresh from `infra/prod`
- ❌ No AWS access or STS calls
- ❌ No temporary ClientPetIndex removal (GSI revert)
- ❌ No Lambda deployment
- ❌ No production-data modification
- ❌ No Cognito or tenant writes
