# Follow-up: Malformed Audit Records Investigation

## Issue Summary
There are **1,244 records** in the `togs-and-dogs-prod-data` table with malformed PK identifiers starting with multiple `AUDIT#` prefixes (e.g., `AUDIT#AUDIT#AUDIT#...`).

## Current Status
- **Visibility**: These records have been successfully hidden from the Admin Portal Request List via backend and frontend filtering.
- **Safety**: None of these records have been deleted to ensure no loss of audit/compliance history before a formal decision is made.

## Investigation Points
1. **Root Cause**: Determine why the audit log writer is prepending multiple prefixes. This is likely a recursive bug in the audit middleware or a retry logic error.
2. **Duplication**: Check if these 1,244 records are duplicates of "healthy" audit logs or if they contain unique data.
3. **Compliance Impact**: Verify if deleting these records impacts any regulatory or history-tracking requirements.

## Recommendations
- **Option A (Archive)**: Move these records to a separate `togs-and-dogs-audit-archive` table.
- **Option B (Repair)**: Run a script to "flatten" the keys (remove extra `AUDIT#` prefixes) and keep them in the main table.
- **Option C (Purge)**: Permanently delete them using the `malformed-audit` scope in `scripts/cleanup_zombie_data_issues.py` once they are confirmed as junk.
