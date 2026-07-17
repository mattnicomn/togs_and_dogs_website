# Release Notes: Phase 1B.2A.2 — Pet Creation Hardening and Legacy Remediation Tool

## 1. Summary of Changes
This release implements Phase 1B.2A.2 locally, resolving a latent default-attribute defect in the pet creation path and introducing a production-safe administrative utility to classify and conditionally remediate legacy pet records.

All changes are local and verified by automated tests. No AWS deployment or production data modification has occurred.

---

## 2. Defect Corrected: new-PET `is_active` Hardening
- **Path Modified:** `pet_handler.py` POST/PUT handlers.
- **Root Cause:** If the request body did not explicitly include the `is_active` parameter on a newly created pet, the attribute was omitted from the database item.
- **Harden Logic:**
  - **New record creation:** If `is_active` is omitted from the request body, the item is persisted with `is_active = True`.
  - **Explicit overrides:** An explicit request body passing `is_active = False` remains `False`, and `is_active = True` remains `True`.
  - **Existing records:** Updates to existing records preserve their stored status (e.g. `True` or `False`) if `is_active` is omitted.
  - **Legacy records:** Updates to legacy records that lack `is_active` do not silently write `is_active` unless it is explicitly provided.
  - **Read compatibility:** Existing read paths continue to treat missing `is_active` attributes as active.

---

## 3. Remediation Tool
- **Path:** [remediate_pet_legacy_attributes.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/scripts/remediate_pet_legacy_attributes.py)
- **Status:** Local script created and fully tested. **No AWS execution occurred during this task.**

### CLI Safeguards & Verification
- **Default Mode:** Dry-run only (requires explicit `--apply` and multiple confirm parameters to write).
- **Strict Verification Gate:** Before any scan or write, the script resolved the boto3 session and:
  1. Verified the AWS Account ID matches the approved production workload ID (`358604342897`).
  2. Verified the DynamoDB table name matches the approved production table (`togs-and-dogs-prod-data`).
  3. Verified the region matches the approved region (`us-east-1`).
  4. Requires `--confirm-write PET-LEGACY-REMEDIATION` to write.
- **STS Identity Check:** Calls STS `GetCallerIdentity` at runtime to prevent accidental execution in incorrect environments.

### Classification Rules
- Conclusively identifies PET items when `PK` matches `PET#{uuid}` and `SK` matches `CLIENT#{uuid}`.
- Categorizes all items into:
  - `complete`
  - `missing_pet_id`
  - `missing_client_id`
  - `missing_company_id`
  - `missing_entity_type`
  - `missing_is_active`
  - `malformed_pk`
  - `malformed_sk`
  - `ambiguous_client_ownership`
  - `client_ownership_not_found`
  - `eligible_for_remediation`
  - `requires_manual_review`

### Remediation Rules
- **`pet_id`:** Derived from `PK` only when missing. Never overwritten.
- **`client_id`:** Derived from `SK` only when missing. Never overwritten.
- **`company_id`:** Map of canonical CLIENT records is built. If a unique CLIENT record ownership is found, the missing `company_id` is proposed. If ownership is absent or ambiguous, the item is classified for manual review and no write is proposed. Never overwritten.
- **`entity_type`:** Set to `'PET'` only when missing. Conflicting values classify the record for manual review.
- **`is_active`:** **Explicitly excluded from automatic historical normalization.** Any missing `is_active` attribute is reported but not proposed for update. Historical cleanup remains deferred for a separate design decision.
- **No deletion support:** No delete, archive, or purge operations exist.

### Concurrent-Safe Conditional Writes
- Uses conditional update expressions checking `attribute_not_exists` for all proposed fields.
- Prevents overwriting concurrent writes.
- Treats `ConditionalCheckFailedException` as a safe skipped result, returning aggregate statistics without printing private keys.

---

## 4. Test Verification
A comprehensive suite of new focused test cases has been added and verified:
- **Remediation Script Tests:** [test_remediate_pet_legacy_attributes.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_remediate_pet_legacy_attributes.py)
  - Dry-run default safety (zero writes).
  - CLI argument checks (wrong account, table, region, missing confirmation).
  - STS identity check validation.
  - Strict key parsing and classification.
  - Ownership mapping, ambiguous/missing resolution.
  - Conditional updates and `ConditionalCheckFailedException` handling.
  - Redaction of raw keys (aggregate-only stdout).
  - Pagination and safety limit abort checks.
- **Pet Handler Hardening Tests:** Appended to [test_r6f_offline_booking.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r6f_offline_booking.py)
  - New pet is_active default (True).
  - New pet is_active explicitly passed (True/False).
  - Existing pet update is_active preservation (True/False preserved).
  - Legacy pet update is_active preservation (missing remains missing).
  - Tenant cross-tenant isolation enforcement.

### Baseline vs. Candidate Run Comparison
- **Backend Test Suite Command:** `py -m pytest --ignore=scratch --ignore=brain`
- **Baseline (Commit `528aeef`):**
  - Collected: 712 items
  - Passed: 641
  - Failed: 71
- **Candidate (After modifications):**
  - Collected: 721 items
  - Passed: 650 (All 9 new test cases passed successfully)
  - Failed: 71
- **Regressions:** Zero. The exact node IDs of the 71 failing tests match the baseline results 100%. No new candidate-only failures were introduced.
- **Whitespace / Style check:** Passed `git diff --check` cleanly.
- **Compilation check:** Syntax compiles successfully on all changed and new files.

---

## 5. Next Steps
- GSI plan remains deferred.
- The next gate is **Kiro review of AG implementation**.
