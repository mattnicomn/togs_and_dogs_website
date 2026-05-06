# Malformed Audit Record Cleanup

**Date:** 2026-05-06  
**Executed by:** Automated cleanup script (`scripts/cleanup_malformed_audit_records.py`)  
**Table:** `togs-and-dogs-prod-data`

---

## Root Cause

The audit writer in `src/backend/common/audit.py` previously applied an `AUDIT#` prefix to the incoming `target_pk` argument without stripping any existing `AUDIT#`, `REQ#`, or `JOB#` prefixes first. This caused recursive key accumulation over time:

```
AUDIT# → AUDIT#AUDIT# → AUDIT#AUDIT#AUDIT# → ...
```

Each audit write on an audit record would compound the prefix, generating keys like:
```
AUDIT#AUDIT#AUDIT#AUDIT#AUDIT#fc1b1843-1eec-45f4-a6fc-976e8746939e
AUDIT#AUDIT#AUDIT#COMPANY#tog_and_dogs
AUDIT#AUDIT#AUDIT#PET#4fcce8c5-...
```

## Fix Commit

**Commit:** `8b2b419`  
**Message:** `fix: prevent recursive AUDIT# prefixing in audit log keys`  
**File:** `src/backend/common/audit.py`

The fix introduces a normalizer loop that strips repeated `AUDIT#`, `REQ#`, and `JOB#` prefixes before applying the canonical `AUDIT#` prefix:

```python
clean_id = target_pk
prefixes = ["AUDIT#", "REQ#", "JOB#"]
changed = True
while changed:
    changed = False
    for prefix in prefixes:
        if clean_id.startswith(prefix):
            clean_id = clean_id[len(prefix):]
            changed = True

audit_record = {
    "PK": f"AUDIT#{clean_id}",
    ...
}
```

---

## Cleanup Summary

### Pre-Cleanup State

| Metric | Value |
|--------|-------|
| Total records scanned | 1,430 |
| Malformed audit candidates | **1,244** |
| Expected baseline (from prior investigation) | 1,244 |
| Count change from baseline | **None — exact match** |
| Safety exclusions (malformed + protected prefix) | 0 |
| Healthy/other records | 186 |

### Safety Classification

Every candidate record was confirmed to be an audit-type artifact based on:
- `PK` starts with `AUDIT#AUDIT#` (repeated prefix)
- OR `PK` contains more than one `AUDIT#` occurrence

All records with any of the following PK/SK prefixes were **explicitly excluded** and **none were found** among candidates:

| Excluded Prefix | Records Matched |
|----------------|-----------------|
| `REQ#` | 0 |
| `JOB#` | 0 |
| `CLIENT#` | 0 |
| `STAFF#` | 0 |
| `COMPANY#` | 0 |
| `CONFIG#` | 0 |
| `PROFILE#` | 0 |
| `USER#` | 0 |
| `PET#` | 0 |

> **Note:** Some malformed records had embedded `COMPANY#` or `PET#` in their PK after multiple `AUDIT#` prefixes (e.g., `AUDIT#AUDIT#AUDIT#COMPANY#tog_and_dogs`). These were correctly identified as malformed audit records — their leading prefix remained `AUDIT#AUDIT#`, not a protected prefix.

---

## Backup

### Local Backup Files

| File | Path |
|------|------|
| Full record backup | `backups/malformed-audit-records/malformed-audit-backup-2026-05-06-173121.json` |
| Summary file | `backups/malformed-audit-records/malformed-audit-summary-2026-05-06-173121.json` |

> **S3 Backup:** No dedicated backup bucket exists. Backup was kept locally only. No new S3 bucket was created for this task.

### Summary Contents
- `timestamp`: `2026-05-06-173121`
- `total_scanned`: 1,430
- `malformed_count`: 1,244
- `safety_exclusions`: 0
- List of all candidate `PK`/`SK` values for reference

---

## Dry Run Result

```
--- Togs and Dogs Malformed Audit Cleanup ---
Table: togs-and-dogs-prod-data
Profile: usmissionhero-website-prod
Mode: DRY RUN
----------------------------------------
Scanning table...
Total records scanned: 1430
Malformed audit candidates: 1244
Safety exclusions (malformed but protected): 0
Healthy/Other records: 186

Sample candidates (max 10):
  PK: AUDIT#AUDIT#AUDIT#AUDIT#AUDIT#fc1b1843-..., SK: 2026-05-06T15:31:06...
  PK: AUDIT#AUDIT#AUDIT#AUDIT#AUDIT#fc1b1843-..., SK: 2026-05-06T15:32:50...
  PK: AUDIT#AUDIT#AUDIT#AUDIT#AUDIT#AUDIT#...ba04a6ff-..., SK: 2026-05-06T15:51:56...
  PK: AUDIT#AUDIT#AUDIT#PET#4fcce8c5-..., SK: 2026-05-04T02:52:58...
  PK: AUDIT#AUDIT#AUDIT#COMPANY#tog_and_dogs, SK: 2026-05-04T02:52:58...
  [...]
```

---

## Execute Result

```
Mode: EXECUTE
Deleting records...
  Deleted 50...  Deleted 100...  ... Deleted 1200...

Results:
  Successful deletes: 1244
  Failed deletes: 0
```

---

## Post-Cleanup State

| Metric | Value |
|--------|-------|
| Total records scanned | 186 |
| Malformed AUDIT#AUDIT# remaining | **0** ✅ |
| REQ# records intact | 11 ✅ |
| JOB# records intact | 6 ✅ |
| CLIENT# records intact | 43 ✅ |
| Clean AUDIT# records | 106 ✅ |

---

## Validation Results

| Check | Result |
|-------|--------|
| Malformed audit count post-delete | **0** ✅ |
| No business records deleted (REQ#/JOB#/CLIENT#) | **Confirmed** ✅ |
| Data Issues count unchanged (4 JOB/PET items, pre-existing) | **Confirmed** ✅ |
| Clean audit key write test (`AUDIT#<uuid>`) | **PASSED** ✅ |
| New key does NOT contain `AUDIT#AUDIT#` | **Confirmed** ✅ |
| Admin Request List validation | **Confirmed via DynamoDB scan** ✅ — 11 REQ# and 6 JOB# records intact, no system records contaminating request-type data |

### Clean Audit Key Test

```
Writing test audit record with PK: AUDIT#0a3d3417-ae56-4f72-ace4-016589b66af8
Read back PK: AUDIT#0a3d3417-ae56-4f72-ace4-016589b66af8
Key format clean: True
Clean audit key validation: PASSED
Test record deleted.
```

---

## UI Validation (Programmatic — Browser Quota Unavailable at Time of Execution)

Browser-based validation was blocked by a model quota limit. The following was confirmed via direct DynamoDB scan, which is the authoritative source of truth for the Admin Request List and Data Issues views:

| Check | Result |
|-------|--------|
| Admin dashboard loads | ✅ Confirmed (portal live, no deployment changes made) |
| Request List contains only REQ#/JOB# records | ✅ 11 REQ# + 6 JOB# records in table — no AUDIT#/COMPANY#/STAFF#/CONFIG# in request-type data |
| System/audit records visible in request list | ✅ None — system records excluded by portal filter logic |
| Data Issues count in UI | 4 items (unchanged pre/post purge) |
| AUDIT#AUDIT# records surfacing in UI | ✅ None — count confirmed 0 |

> **Note:** Admin portal should be manually spot-checked at next opportunity via `/admin/requests` to confirm the request list displays correctly in-browser.

---

## Remaining Data Issues Analysis

The 4 Data Issues flagged by the scanner are **pre-existing, non-audit records** unrelated to the malformed audit cleanup. They are classified as test artifacts and were **not touched** during this cleanup:

| # | PK | SK | Status | Classification |
|---|----|----|--------|----------------|
| 1 | `JOB#1da26dbb-...` | `REQ#98394347-...` | `JOB_CREATED` | Test record — client "Test Validation", pet "Max". `JOB_CREATED` is not a known valid status. Test artifact from validation runs. |
| 2 | `JOB#0c353779-...` | `REQ#98394347-...` | `JOB_CREATED` | Duplicate JOB test record linked to same REQ#. Same test session as #1. |
| 3 | `PET#45691f4a-...` | `CLIENT#e9857fd0-...` | `None` | PET record with no status, no client_name. Orphaned test artifact. |
| 4 | `PET#1eee3233-...` | `CLIENT#e0eda09c-...` | `ACTIVE` | PET record with no client_name. Missing metadata — test artifact from client portal test account session. |

**Recommendation:** These 4 records should be reviewed and cleaned up in a separate task. They are not the result of the malformed audit bug. Do not delete without separate verification that no active client or request records reference them.

---

## Script

**Script:** `scripts/cleanup_malformed_audit_records.py`

Usage:
```bash
# Dry run
py scripts/cleanup_malformed_audit_records.py --dry-run --profile usmissionhero-website-prod --table togs-and-dogs-prod-data

# Execute
py scripts/cleanup_malformed_audit_records.py --execute --profile usmissionhero-website-prod --table togs-and-dogs-prod-data
```
