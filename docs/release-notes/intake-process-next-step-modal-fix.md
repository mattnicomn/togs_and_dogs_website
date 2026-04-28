# Release Notes: Intake Process Next Step Modal & Dynamic Staff Assignment

## Issue 1: Intake Process Modal Displayed Unsafe Actions
**Issue:** 
The Process Workflow modal displayed every possible action related to a record's status, which crowded the UI and allowed users to click actions out of sequence (e.g., attempting to Approve a record while simultaneously being offered the option to Require a Meet & Greet). It also contained duplicate Cancel buttons.

**Fix:** 
- The modal was updated to dynamically filter and present only the **primary next valid workflow action(s)** based on the exact status.
- Duplicate "Cancel" buttons were removed in favor of a single, neutral Cancel action that closes the modal safely.
- **`PROFILE_CREATED`** now exclusively shows "Require Meet & Greet".
- **`MEET_GREET_REQUIRED`** now exclusively shows "Mark M&G Complete".

## Issue 2: Hardcoded and Broken Staff Assignment Selector
**Issue:** 
When assigning staff to an approved visit, the staff dropdown selector was not reliably selectable, was populated with hardcoded values rather than dynamic staff records from the backend, and incorrectly sent staff display names instead of unique identifiers to the backend API.

**Fix:** 
- **Dynamic Loading:** The staff assignment dropdown now correctly maps to the live `staffList` retrieved from the Staff Management API.
- **Safe Filtering:** The list is automatically filtered to only show staff members who are `ACTIVE` and have `is_assignable !== false`. Disabled or deleted staff members are safely hidden from new assignments.
- **Backend Identifier Synchronization:** The frontend now securely passes the `staff_id` (UUID) to the backend for data consistency, alongside the `worker_name` to ensure that Google Calendar sync continues to present human-readable staff names to clients.
- **Historical Consistency:** Previously assigned records will gracefully fall back to displaying the historical `worker_id` string if the original staff member was removed or changed.

## Deployment Details
- **Production URL:** [https://toganddogs.usmissionhero.com/admin](https://toganddogs.usmissionhero.com/admin)
- **Commit Hash:** [to be populated]
- **CloudFront Invalidation ID:** `I5FBKYG5RPJASE0WX4F0HYQLVC`

## Validation Matrix
- [x] Process modal safely filters down to a single/primary path per status.
- [x] Process modal contains exactly one neutral Cancel button.
- [x] Assignment selector dynamically loads staff from the backend list.
- [x] Disabled staff members do not appear in the assignment dropdown.
- [x] Backend assignment payload safely uses Staff UUIDs.
- [x] Existing calendar integration seamlessly receives the Staff Display Name for rendering.
