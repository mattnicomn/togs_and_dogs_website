# Release Notes: Admin Soft-Delete & Archive Filtering
**Date**: April 26, 2026
**Commit**: 100db42

## Overview
This update improves the Togs & Dogs admin dashboard by implementing a robust soft-delete mechanism and enhanced list filtering. This ensures that the primary intake and request lists remain clean and focused on active operations without permanently removing historical or test data.

## Key Changes

### 1. Soft-Delete & Archive Logic
- **Backend Implementation**: Updated `admin_handler.py` to filter out records with `DELETED` or `ARCHIVED` status from the default `ALL` scan.
- **Immediate Refresh**: Action handlers now ensure records disappear from active views immediately upon deletion or archiving.
- **No Hard Deletes**: All "Delete" actions now perform a status update to `DELETED` instead of a database removal, preserving audit trails and history.

### 2. Frontend Dashboard Updates
- **New Filter: Trash / Deleted**: A dedicated view for soft-deleted records, preventing them from cluttering the main workspace.
- **Renamed View: All Active**: The "Snapshot (Scan)" view has been renamed to "All Active" to better reflect its purpose as a clean operational list.
- **UI Styling**: Added a distinct style for deleted records (strike-through and neutral color palette) to differentiate them from active or pending items.
- **Restore Functionality**: Verified that "Restore" correctly moves records from Trash or Archive back to the appropriate operational queue.

### 3. Data Remediation
- **Remediation Script**: `scripts/remediate_records.py` was executed against the production environment.
- **Results**: 
    - **44 legacy/test records** were successfully identified and moved to the `DELETED` state.
    - Legacy statuses (e.g., `REQUEST_APPROVED`) were normalized to standard platform values.
    - Verified that no live production customer or service data was affected.

## Deployment & Verification
- **Backend**: 8 Lambda functions updated via Terraform (`infra/prod`).
- **Frontend**: Vite build synced to S3 and CloudFront invalidated.
- **Invalidation ID**: `I10Q2Y7S3CBEAFGZPNVE4013W5` (Status: Completed).
- **Validation**: Full production walkthrough confirmed filtering accuracy and action persistence.

## Repository Status
- **Clean Baseline**: All temporary remediation scripts removed; repo state is clean.
- **Deployment Script**: The remediation tool remains in `scripts/` for future hygiene maintenance.
