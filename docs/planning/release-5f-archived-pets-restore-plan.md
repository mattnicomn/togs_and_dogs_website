# Release 5F: Archived Pets Visibility & Restore

## Goal
Implement a safe operational control to view and restore archived pets directly within the Admin Portal `CareCard`, specifically for Admin and Owner roles. This feature fulfills the need to manage soft-deleted pets without introducing the historical data integrity risks of permanent deletion.

## Proposed Changes

### 1. Backend API (`src/backend/handlers/pet_handler.py`)
- **No Changes Required**: The existing `PUT /admin/pets/{petId}` and `POST /admin/pets/{petId}` methods already accept and process the `is_active` field safely. We will leverage this existing robust pathway to flip `is_active = true`.

### 2. Frontend Implementation (`web/src/components/CareCard.jsx`)
- **State Management**:
  - Add a new local state `showArchivedPets` (default: `false`).
- **Pet Normalization Logic (`_normalizePets`)**:
  - Update the filter logic to include pets with `is_active === false` *only* if `showArchivedPets` is `true`.
  - Maintain the fallback behavior so that if a CareCard *only* has archived pets, they are still accessible.
- **UI Updates**:
  - **Archived Pets Toggle**: Add a "Show Archived Pets" / "Hide Archived Pets" button near the pet selector navigation. This button should only render for `admin` and `owner` roles, and only if the record contains at least one archived pet (`pet._allPets.some(p => p.is_active === false)`).
  - **Visual Distinction**: Style the tabs of archived pets distinctly (e.g., greyed out, italic text, or an `(Archived)` suffix) to prevent confusion with active pets.
  - **Archived Status Display**: Within the "Overview" tab, clearly display an "Archived" status chip or warning banner when viewing an archived pet.
  - **Restore Button**: In the pet selector navigation action area (where the "Archive Pet" button currently lives), render a "Restore Pet" button if the currently selected pet is archived (`activePet.is_active === false`).
  - **Restore Action**: Clicking "Restore Pet" will execute the existing `onUpdate({ pet_id: pid, client_id: cid, is_active: true })` flow.

### 3. Safety Controls
- **Permanent Deletion explicitly omitted**: No code will be written to completely destroy `PET#` records.
- **Role Scoping**: The toggle and restore buttons will be wrapped in the `['owner', 'admin'].includes(userRole)` permission check, mirroring the existing Archive control.

## Verification Plan

### Automated/Manual Testing Checklist
1. **Prerequisite (Archive)**: Open an approved multi-pet CareCard, select a pet, and archive it. Confirm it disappears from the default view.
2. **Toggle Visibility**: Confirm a "Show Archived Pets" toggle appears. Click it and confirm the archived pet tab becomes visible and is visually distinct.
3. **Detail Validation**: Select the archived pet tab. Confirm the pet details display correctly and a clear "Archived" indicator or banner is shown.
4. **Restore Action**: Click the "Restore Pet" button. Confirm the save succeeds and the pet tab reverts to a normal active state.
5. **Role Check**: Log in as a `staff` user. Confirm the "Show Archived Pets" and "Restore Pet" buttons are strictly hidden.
6. **No Hard Delete**: Verify that no "Permanently Delete" button is introduced.

## Rollback Considerations
Since this feature relies entirely on frontend UI additions and existing backend `is_active` boolean support, rolling back simply involves reverting the `CareCard.jsx` modifications. No data migrations or backend deployments will be required for rollback.
