# Phase 1B.2A.2: Production Dry-Run Results Review

**Date:** 2026-07-16
**Reviewer:** Kiro
**Status:** NEEDS LOCAL CORRECTION
**Recommendation:** Bounded AG parser and disposition correction required before second dry run

---

## Approved Dry-Run Execution

- Executed with Matthew's explicit approval
- Mode: `--dry-run` (read-only)
- Zero writes confirmed
- No record-level identifiers in output
- Repository remained clean
- Exit status: 0

## Aggregate Results

| Metric | Value |
|--------|-------|
| Total table items evaluated | 957 |
| Total PET items | 84 |
| Complete PET items | 25 |
| Missing pet_id | 3 |
| Missing client_id | 3 |
| Missing company_id | 16 |
| Missing entity_type | 1 |
| Missing is_active | 59 |
| Malformed PK | 0 |
| **Malformed SK** | **35** |
| Ambiguous ownership | 0 |
| Client ownership not found | 16 |
| Eligible for automatic remediation | 0 |
| Requires manual review | 28 |
| Proposed field changes | 0 |

---

## Root Cause: Regex Rejects Valid Underscored Identifiers

### Current regex patterns
```python
PET_PK_RE = re.compile(r"^PET#([a-zA-Z0-9-]+)$")
CLIENT_SK_RE = re.compile(r"^CLIENT#([a-zA-Z0-9-]+)$")
```

### Actual production ID formats
| Entity | Format | Characters | Example |
|--------|--------|-----------|---------|
| pet_id | `str(uuid.uuid4())` | a-f, 0-9, hyphens | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| client_id | `f"client_{uuid4()[:8]}"` | lowercase, digits, underscore, hyphen | `client_a1b2c3d4` |
| Virtual client_id | `f"cognito_{username}"` | any Cognito username chars + underscore | `cognito_user@example.com` |
| company_id | hardcoded slugs | lowercase, underscores | `tog_and_dogs`, `test_tenant_alpha` |

### Impact
The `CLIENT_SK_RE` pattern `[a-zA-Z0-9-]+` does NOT include underscore (`_`), period (`.`), or `@`. Since production client IDs contain underscores (e.g., `CLIENT#client_a1b2c3d4`), **35 of 84 PET records are incorrectly classified as malformed SK**.

This cascading error explains:
- 35 malformed SK → all classified as `requires_manual_review` or silently unaccounted
- 0 eligible for remediation → records with valid data but "malformed" SK cannot be processed
- 16 ownership-not-found → CLIENT records with underscore IDs also fail the ownership map parser

---

## Disposition Accounting Gap

Current totals account for only 53 of 84 PET records:
- Complete: 25
- Manual review: 28
- Eligible: 0
- **Unaccounted: 31 records have no final disposition**

The utility must place every PET record into exactly one mutually exclusive final category.

---

## Correct Identifier Grammar

Based on repository evidence, a safe delimiter-based pattern is:
```
^PET#([^#]+)$       — any non-empty suffix without # delimiter
^CLIENT#([^#]+)$    — any non-empty suffix without # delimiter
^COMPANY#([^#]+)$   — any non-empty suffix without # delimiter
```

This matches:
- UUIDs with hyphens ✅
- `client_a1b2c3d4` with underscores ✅
- `cognito_user@example.com` with @ and periods ✅
- `tog_and_dogs` with underscores ✅

And rejects:
- Empty suffixes ✅
- Double-delimited patterns like `PET#a#b` ✅

---

## Ownership Map Parsing

The ownership map logic uses:
```python
if pk.startswith('COMPANY#') and sk.startswith('CLIENT#'):
    parts_pk = pk.split('#')
    parts_sk = sk.split('#')
```

This `split('#')` approach is safe for company IDs that don't contain `#` (all current ones use underscores). However, the SK parser then applies `CLIENT_SK_RE` for PET items, which rejects the same valid client IDs. The ownership map itself likely builds correctly (it uses `split('#')` not the regex), but PET classification fails downstream.

---

## Recommended Bounded AG Correction

### Parser fixes
- Replace `PET_PK_RE` with `^PET#([^#]+)$`
- Replace `CLIENT_SK_RE` with `^CLIENT#([^#]+)$`
- Add `COMPANY_PK_RE = re.compile(r"^COMPANY#([^#]+)$")` for ownership map

### Disposition accounting
- Add mutually exclusive final-disposition counters that sum to `total_pets`
- Add assertion: `sum(dispositions) == total_pets`
- Recommended categories: complete, eligible_auto, missing_is_active_only, incomplete_excluded, requires_manual_review

### Independent safe-field remediation
- Allow `pet_id` and `client_id` to be proposed independently of `company_id`
- A record with derivable pet_id + client_id but unresolved company_id should get pet_id and client_id proposed while company_id remains in manual review
- Do NOT weaken company_id tenant protections

### Safety-limit hard failure
- Exceeding the limit must produce nonzero exit (sys.exit(2) or raise)
- Must not present partial results as complete
- Add tests for limit-crossed scenarios

### Exception redaction
- Replace `print(f"ERROR: Failed to update item: {e}")` with sanitized output
- Print only error code and operation category
- Add test with synthetic ClientError containing fake key values

### Remove unused projection
- Remove `name` from ProjectionExpression
- Document that this is privacy minimization

### Tests required
- Underscore-containing client_id (e.g., `CLIENT#client_a1b2c3d4`)
- Virtual cognito client_id (e.g., `CLIENT#cognito_user@example.com`)
- Company IDs with underscores
- UUID pet IDs
- Exact disposition sum assertion
- Partial-remediation eligibility (pet_id + client_id without company_id)
- Safety-limit hard abort with nonzero exit
- Exception redaction (no key leakage)
- Full baseline/candidate comparison with zero candidate-only failures

---

## Revised Approval Sequence

1. ✅ Kiro dry-run results review (this document)
2. **Matthew approves bounded local AG correction**
3. AG implements, tests, commits, pushes
4. Kiro reviews corrected utility
5. Matthew approves second production dry run
6. Compare results with first run
7. Kiro reviews proposed remediation plan
8. Matthew separately approves remediation apply (if warranted)
9. ClientPetIndex Terraform planning after remediation

---

## What Was NOT Done

- ❌ No remediation apply
- ❌ No AWS access during this review
- ❌ No code changes
- ❌ No Terraform
- ❌ No deployment
- ❌ No production-data modification
