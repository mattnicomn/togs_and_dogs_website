# Release 5E: Permanent Pet Deletion / Cleanup Controls

## Goal
Implement a permanent pet deletion feature for Admin and Owner roles to clean up test or erroneous pet records. The feature must strictly protect active pets and pets associated with active or upcoming visits.

## User Review Required
> [!IMPORTANT]
> **Data Integrity and Traceability Risk**
> Deleting a `PET#` record permanently means historical requests (`REQ#`) that reference this pet's ID will suddenly point to a non-existent record. We must ensure the UI gracefully handles these "ghost" references without crashing.

## Proposed Changes

### 1. Backend Implementation (`src/backend/handlers/pet_handler.py`)
- **Add DELETE Endpoint**: Add a `DELETE` HTTP method handler for `/admin/pets/{petId}` (or handle via generic path).
- **Role Enforcement**: Restrict execution to `owner` and `admin` roles only. `staff` and `client` are forbidden.
- **Archive Prerequisite Check**: 
  - Fetch the existing `PET#{pet_id}` record.
  - Reject the deletion if `is_active` is `True` (or absent/default True). The pet must be explicitly archived first.
- **Active Visit Blocking**: 
  - Query all `REQ#` records for the `client_id`.
  - If any request has a status of `pending`, `approved`, or `in_progress` AND contains the target `pet_id` in its `pet_ids` array (or legacy `pet_id` field), reject the deletion.
- **Action**: Execute `table.delete_item()` to permanently remove the `PET#` record.

### 2. Frontend Implementation (`web/src/components/CareCard.jsx` & `AdminDashboard.jsx`)
- **UI Button**: Add a red "Permanently Delete" button within the `CareCard`'s pet tab, visible ONLY if:
  - The current user is an `admin` or `owner`.
  - The pet is currently archived (`!pet.is_active`).
- **Confirmation Flow**: Clicking the button must trigger a hard confirmation modal/dialog stating: *"Are you sure you want to permanently delete this pet? This action cannot be undone and will affect historical records."*
- **State Update**: After a successful deletion, update the local `AdminDashboard` state to remove the pet from the client's cached pet list and close the CareCard or switch to the primary tab to avoid rendering a dead tab.

### 3. Data Integrity Impacts & Handling
- **PET# Record Deletion**: The DynamoDB record is destroyed.
- **Client Profile Summary**: `client` API calls and UI loops generally scan existing `PET#` records dynamically, so the deleted pet will naturally disappear. If any denormalized pet name strings are stored directly on the `CLIENT#` record, they should ideally be scrubbed, but typically we rely on the relational lookup.
- **Request Record `pet_ids` (Historical)**: 
  - **Safe Handling Option**: We will **NOT** modify historical `REQ#` records. Removing IDs from old requests alters historical truth (e.g., how many pets were walked).
  - Instead, the `CareCard` and `AdminDashboard` must be updated to gracefully handle `null` or missing pet objects when a `pet_id` is found in a request but the pet record no longer exists in the database. The UI should render a fallback tab named "Deleted Pet" or simply ignore it, preventing a blank screen crash.

## Verification Plan

### Automated/Manual Testing
1. **Prerequisite Check**: Attempt to delete an active pet (UI button should be hidden, direct API call should return `400 Bad Request`).
2. **Visit Block Check**: Archive a pet connected to an active booking, attempt deletion, confirm API returns `400` with an explanatory error.
3. **Success Check**: Archive an isolated test pet, execute delete, confirm success.
4. **Historical Ghost Check**: Open a past, completed CareCard that referenced the deleted pet and confirm the UI does not crash.
5. **Role Check**: Confirm Staff cannot see the button or execute the API.

## Status: DEFERRED
> [!WARNING]
> **Implementation Deferred**
> Release 5E has been officially deferred. The feature should not be implemented at this time.

### Rationale for Deferral
- **Sufficient Existing Controls:** The Archive Pet feature introduced in Release 5C (`is_active=false`) already successfully removes pets from active workflows, providing the necessary operational cleanup.
- **Ghost-Reference Risks:** A hard permanent delete introduces significant data integrity risks. Removing a `PET#` record creates ghost references across `REQ#` records, client summaries, CareCard tabs, and historical records, which would require extensive defensive programming to prevent UI crashes.
- **No Immediate Compliance Mandate:** There is currently no identified GDPR or data-erasure requirement dictating the need for permanent deletion capabilities.
- **Revisiting Criteria:** Permanent deletion should only be revisited if strict legal/data-retention requirements or essential production data cleanup tasks explicitly demand it.

## Recommended Future Approach
If permanent pet deletion is revisited in the future, the following phased approach is recommended:
1. **Maintain Current Controls:** Keep archiving as the primary operational control for the foreseeable future.
2. **Archived Pets View:** Implement a dedicated admin-only "Archived Pets" view to audit soft-deleted pets before considering hard deletion.
3. **Restore Support:** Add the ability to restore/unarchive a pet before implementing permanent deletion logic.
4. **Prerequisites for Hard Delete:** Only implement the hard `DELETE` endpoint after backend integrity check barriers and robust frontend "deleted-pet" fallback rendering behaviors are fully built and tested.
