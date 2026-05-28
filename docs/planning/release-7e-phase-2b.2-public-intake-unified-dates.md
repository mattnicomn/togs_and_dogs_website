# Release 7E Phase 2B.2: Public Intake Unified Visit Dates Selector

## Overview
Following the successful validation of the unified "Visit Dates" selector in the Admin Dashboard, this phase will apply the same streamlined scheduling UX to the public `/book` intake form.

## Objectives
1. **Unify the UX:** Replace the legacy date selection mechanism on the public intake form with the new, unified `DatePickerGrid` component.
2. **Remove Complexity:** Eliminate any separate "Single Day" or "Date Range" modes in favor of the single unified calendar interface.
3. **Payload Parity:** Update the frontend submission logic to send the exact same payload structure as the Admin Dashboard:
   - `selected_dates`: Sorted array of selected dates.
   - `start_date`: The earliest selected date.
   - `end_date`: The latest selected date (only included if multiple dates are selected).
4. **Constraints:** 
   - Enforce the 14-day maximum selection limit.
   - Allow past date selection to be correctly blocked (as it is currently).
5. **No Backend Changes:** The backend (Phase 2A) already supports this payload structure, so no backend modifications will be required.

## Next Steps
This plan should be executed once the Admin Dashboard version of the unified selector has been fully validated and deployed to production.
