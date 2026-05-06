# Walkthrough - Bulk Data Issues Cleanup Fix

I have implemented a robust and safe cleanup workflow for "Data Issues" records in the Admin Portal. This fix addresses the root cause of previous bulk update failures and introduces a secure two-step deletion process.

## Root Cause Resolution
The previous failures (43/70 failed) were primarily due to:
1.  **Strict ID Matching**: Malformed records with swapped keys or missing identifiers could not be resolved by the backend.
2.  **Lack of Bulk Support**: The backend processed deletions individually, which was inefficient and lacked the "healing" logic used by the permanent purger.

I have implemented `_resolve_admin_record`, a resolution chain that can "heal" malformed records by trying swapped keys and scanning for embedded IDs.

## Key Changes

### 1. Backend: ID Healing & Bulk Support
Modified `src/backend/handlers/admin_handler.py` to:
- Support **Bulk Action** for `DELETE` and `ARCHIVE`.
- Use a **Resolution Chain** to find records even if their identifiers are malformed.
- Provide a `dry_run` mode for `PURGE` to analyze selection before deleting.

### 2. Frontend: Two-Step Purge & Analysis
Updated `web/src/components/AdminDashboard.jsx` to:
- Use a single bulk backend call for moving records to Trash.
- Add an **Analyze Selection** phase in the Purge modal.
- Display a summary of **Purgeable**, **Blocked**, and **Failed** records with specific reasons.

## Verification Results

### Automated Tests
- **Backend**: `py -m py_compile src/backend/handlers/admin_handler.py` -> **PASSED**
- **Frontend**: `npm run build` -> **PASSED**

### New UI Components

````carousel
```javascript
// New Analysis Step in handleBulkPurge
if (!confirm) {
  const response = await purgeRecordsBulk(payload, true); // dry_run
  setPurgeAnalysis(response);
  return;
}
```
<!-- slide -->
```python
# New Resolution Chain in admin_handler.py
def _resolve_admin_record(pk, sk):
    # Try direct -> Try swapped -> Scan for embedded IDs
    ...
```
````

## Safety Confirmation
- **Active Records Unaffected**: The code explicitly checks status before purging and protects records in active states.
- **Strict Sequencing**: Permanent purge is only allowed for records already in the `DELETED` or `TRASH` state.
