# Request List Filter and Count Hotfix

## Issue
Admins reported that the Request List filters were not isolating records correctly, and sidebar counts were inaccurate. Malformed "Data Issue" records were bleeding into active workflows, and selection logic was inconsistent.

## Fix
- **Unified Predicate Engine**: Implemented a central filtering layer (`getFilterPredicate`) used for both rendering the request list and calculating sidebar counts.
- **Data Issue Isolation**: "Data Issue" records are now strictly isolated. They no longer appear in "All Active," "Intake Queue," "Booking Queue," or other workflow-specific filters.
- **Accurate Sidebar Counts**: Counts are now calculated dynamically from the full loaded dataset using the same predicates as the main list.
- **Lifecycle Logic**: Corrected predicates for "All Active" (now correctly excludes all closed states), "Cancelled," "Archived," and "Trash / Deleted" (now correctly includes `deleted_at` markers).
- **Selection Reliability**: Verified that "Select All" and row selection use the same stable composite keys and visibility logic.

## Technical Changes
- **File**: `AdminDashboard.jsx`
- **Logic**:
    - `isDataIssue(r)`: Now strictly identifies records missing core fields or status, while excluding those already deleted or archived.
    - `isActiveRecord(r)`: Excludes Deleted, Archived, Completed, Cancelled, and Data Issues.
    - `getFilterPredicate(key)`: Provides a consistent boolean check for each UI filter.

## Verification
- Verified that "All Active" excludes the 39 malformed records.
- Verified that "Data Issues" view correctly isolated the malformed records.
- Verified that sidebar counts match the actual number of visible rows in each view.
- Verified that "Select All" correctly targets only visible records in the current view.
