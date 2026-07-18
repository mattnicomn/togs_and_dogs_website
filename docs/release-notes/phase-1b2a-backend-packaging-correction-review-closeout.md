# Phase 1B.2A: Backend Packaging Correction Review Closeout

**Date:** 2026-07-18
**Reviewer:** Kiro
**Status:** ✅ READY FOR TEMPORARY GSI REVERT AND BACKEND PLAN APPROVAL

---

## Commits Reviewed

| Commit | Description |
|--------|-------------|
| `2386a93` | fix(infra): exclude local caches from backend archive |
| `a513ac5` | docs: prepare deterministic backend packaging |

## Exact Excludes Configuration

```terraform
excludes = [
  "**/.pytest_cache/**",
  "**/__pycache__/**",
  "**/*.pyc",
  "**/*.pyo",
  "**/*.log",
  "**/*.tmp"
]
```

**Assessment:** Acceptable. The first four patterns address the proven 42-entry contamination. The `*.log` and `*.tmp` patterns are a reasonable defensive addition for a deployment package — no current backend files use these extensions, and if they did, they would not be intended Lambda runtime code.

## Provider Schema: CONFIRMED

- Provider: `hashicorp/archive` v2.7.1
- `excludes`: present, type `set(string)`, optional
- Supports globstar (`**`) patterns per documented schema description

## Contaminated Archive (Before): CONFIRMED

- 81 ZIP entries total
- 42 cache/bytecode entries (.pytest_cache: 4, __pycache__: 38)
- Note: .pyc count (38) overlaps with __pycache__ count — they are the same files, not additive

## Clean Archive (After): CONFIRMED

- 39 ZIP entries
- 0 cache/bytecode entries
- 39 matches `git ls-files src/backend` count exactly
- All tracked files present, no unexpected files

## Determinism Wording: CORRECTED ASSESSMENT

AG's documentation claims "input-selection determinism" — this is **partially accurate but overstated**:

**What IS guaranteed:**
- The 42 known cache/bytecode artifacts are excluded
- Running tests locally cannot pollute the archive
- All 39 current tracked backend files are included

**What is NOT guaranteed:**
- An arbitrary future untracked file with a non-excluded extension (e.g., `scratch.py`) could still enter the archive
- ZIP binary checksums may vary across platforms due to metadata, timestamps, and file ordering
- This is a **denylist**, not an allowlist

Accurate characterization: "Deterministic exclusion of known local cache and bytecode artifacts from the Lambda deployment archive."

## Evidence Reproducibility: ADEQUATE

AG documented specific commands (terraform providers schema, py zipfile inspection, terraform plan fixtures). The methodology is reproducible by another engineer with the same local environment.

## Terraform Validation: CONFIRMED

- `terraform fmt` and `terraform fmt -check` passed
- `terraform validate` passed
- No AWS access or state refresh occurred (validate uses local schema only)

## Rollback Guidance: CORRECTED

Documentation now correctly states:
- Do NOT apply from old commit `234b51d`
- Revert only application delta within current mainline
- Regenerate plan with current infrastructure config
- Obtain separate approval before apply

## Log/Tmp Exclusion Decision: ACCEPTABLE

No current `.log` or `.tmp` files exist in `src/backend/`. These patterns are a defensive measure against accidental inclusion of local debugging output. They do not exclude any intended Lambda runtime files. Acceptable as-is.

---

## Next Approval Gate

**Matthew approves the temporary ClientPetIndex configuration removal and backend-only Terraform plan generation.**

Exact AG task:
1. Create a bounded commit removing ONLY the ClientPetIndex GSI config from `modules/data/main.tf` (the `client_id` attribute, `pet_id` attribute, and `global_secondary_index` block added by `cda722a`)
2. Run `terraform fmt -check` and `terraform validate`
3. Generate a normal full Terraform plan
4. Expected plan: 0 add, 13 change, 0 destroy (Lambda package updates only — no DynamoDB change)
5. Save the plan with a clear name (e.g., `phase-1b2a-backend-only.tfplan`)
6. Kiro reviews the saved plan
7. Matthew separately approves apply

---

## What Was NOT Done

- ❌ No AWS access
- ❌ No production Terraform plan
- ❌ No Terraform apply
- ❌ No ClientPetIndex removal
- ❌ No Lambda deployment
- ❌ No production-data modification
