# Backlog: CareCard Admin Entry Improvements

## Priority: Low
## Status: Planned

## Problem
CareCard occasionally shows "Pet 1 (loading failed)" when:
- The pet record doesn't exist or has been archived
- The `pet_ids` array on the request references a pet that can't be loaded
- The client_id on the record doesn't match the expected format

## Observed During
- Release 6B Phase 2 validation — test record showed "Pet 1 (loading failed)" with truncated client_id

## Possible Causes
1. Pet record was archived/deleted but still referenced in `pet_ids`
2. Client ID format mismatch (e.g., `test-client-123` vs UUID format)
3. DynamoDB query uses wrong PK/SK combination for pet lookup

## Proposed Fix
1. Add graceful fallback in CareCard when pet loading fails (show pet name from request record instead)
2. Add validation that `pet_ids` entries actually exist before rendering tabs
3. Show a clear "Pet record not found" message instead of generic "loading failed"

## Files Involved
- `web/src/components/CareCard.jsx` — pet loading and tab rendering
- `web/src/components/AdminDashboard.jsx` — pet data fetching

## Effort: 2-4 hours
## Non-Blocking: CareCard still functions for other tabs when pet loading fails
