# Backlog: Admin Dashboard Filter Integrity

## Priority: Low
## Status: Planned

## Problem
Sidebar filter counts and the visible record list can become misaligned when:
- Filter predicates are updated in one place but not the other
- Terminal status records appear in active views
- Data issue classification changes without updating counts

## Known Issues
- Count logic and filter logic must use the same `getFilterPredicate()` function
- Active/scheduled records must never appear in Trash or Cancelled views
- JOB# records are excluded from the request list (Release 1 fix) but may still affect counts

## Proposed Fix
- Audit all `getFilterPredicate()` cases for consistency
- Add a dev-mode assertion that `visibleRecords.length === filterCounts[currentFilter]`
- Review edge cases: records with missing status, records with unknown workflow_type

## Files Involved
- `web/src/components/AdminDashboard.jsx` — `getFilterPredicate()`, `filterCounts`, `visibleRecords`

## Effort: 2-4 hours
