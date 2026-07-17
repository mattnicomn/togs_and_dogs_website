# Release Notes: Phase 1B.2A.2 — Remediation Classifier Correction (Pre-Deploy)

## 1. Executive Summary
This release implements local corrections to the legacy pet attribute remediation classifier utility (`scripts/remediate_pet_legacy_attributes.py`). These corrections address regex limitations identified during the first production dry run, ensure independent safe-field proposal generation, enforce complete mutually exclusive disposition accounting, and harden the safety limit and exception-redaction behaviors.

All changes are local and verified by automated tests. No AWS access or production writes occurred. Remediation apply remains unapproved, and the `ClientPetIndex` remains deferred.

---

## 2. Classifier Corrections & Behavior

### Root Cause of Malformed SK Classification
During the initial production dry run, 35 out of 84 PET records were incorrectly classified as malformed SK. The root cause was a restrictive regular expression (`CLIENT_SK_RE = re.compile(r"^CLIENT#([a-zA-Z0-9-]+)$")`) that rejected valid client IDs containing underscores (e.g., `CLIENT#client_a1b2c3d4`), Cognito usernames containing periods, plus signs, or `@` symbols (e.g., `CLIENT#cognito_user@example.com`).

### Verified Identifier Grammar
We replaced the regex-based validation with a clean, shared, delimiter-based parser helper (`parse_key_value`):
- Exact prefix check (e.g., `PET`, `CLIENT`, `COMPANY`).
- Suffix must contain exactly one `#` delimiter.
- Suffix must be non-empty and may contain any character except `#` (allowing hyphens, underscores, periods, `@` symbols, plus signs, etc.).
- Rejects empty suffixes, extra `#` delimiters, wrong prefixes, non-string keys, and missing keys.

### Corrected Canonical CLIENT Ownership Parsing
- PK must exactly parse as `COMPANY#{company_id}`.
- SK must exactly parse as `CLIENT#{client_id}`.
- Ownership requires that the canonical CLIENT record has either a missing `entity_type` (compatibility-handled historical record) or an `entity_type` exactly equal to `'CLIENT'`. Conflicting non-CLIENT entity types are rejected.
- Maps `client_id` to a set of company IDs. Uniquely resolved if count is exactly 1; otherwise marked unresolved.

### Independent Safe-Field Proposals
The update proposal logic has been decoupled:
- **`pet_id`**: Proposed if missing and PK parses correctly as `PET#...` (independent of company ownership resolution).
- **`client_id`**: Proposed if missing and SK parses correctly as `CLIENT#...` (independent of company ownership resolution).
- **`entity_type`**: Proposed as `'PET'` if missing and both PK and SK parse correctly.
- **`company_id`**: Proposed if missing and the client has exactly one unique canonical company mapped.
- **`is_active`**: Counted when missing, but excluded from proposed changes.

### Complete Disposition Accounting
Every PET record is assigned to exactly one mutually exclusive disposition category:
1. `complete`: No missing fields, no conflicts.
2. `eligible_for_full_remediation`: All missing needed attributes can be safely proposed.
3. `eligible_for_partial_remediation`: Some missing attributes can be proposed, but others (e.g. `company_id`) remain unresolved.
4. `compatibility_handled_missing_is_active_only`: Only `is_active` is missing.
5. `requires_manual_review`: Fundamental conflicts, malformed keys, or unresolved company_id with no other proposed fields.

An invariant check asserts that `sum(dispositions) == total_pets` at runtime, failing closed if it does not hold.

---

## 3. Operations & Safety Polish

### Safety-Limit Failure Behavior
- Checked at page level during paginated scan.
- If cumulative evaluated items exceed the safety limit, the script immediately raises `SafetyLimitExceededError`.
- Results are marked `INCOMPLETE`, zero writes are performed, and the process exits with status `2` (fail closed).

### Exception Redaction
- Redacts sensitive details from STS, Scan, and Update failures.
- Prints generic error codes (e.g., `ClientError: Code`) or general messages without leaking PK, SK, client name, or other trace metadata.

### Privacy-Minimized Projection
- Removed the unused `name` attribute from the DynamoDB scan `ProjectionExpression`.
- Projected fields are minimized to: `PK, SK, pet_id, client_id, company_id, entity_type, is_active`.
- *Note: ProjectionExpression filters returned fields to minimize private data transit; it does not reduce DynamoDB Scan capacity consumed.*

---

## 4. Test Verification
The focused test suite has been expanded to 11 tests covering:
- Valid/invalid identifier grammar (UUIDs, usernames, periods, plus signs, underscores).
- Ownership mapping (historical CLIENT records, entity_type checks).
- Decoupled independent proposals.
- Safety limit aborts on first and later pages.
- Exception redaction (verifying synthetic ClientError with sensitive data has no leakage).
- CLI mode mutual exclusion.

All 11 focused tests pass. Full backend test candidate comparison resulted in 0 regressions.

---

## 5. Next Steps
The next gate is **Kiro review of the corrected implementation**.
No AWS access or production writes have occurred during this task.
