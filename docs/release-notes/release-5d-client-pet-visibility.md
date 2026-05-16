# Release 5D: Client Management Pet Visibility

**Deployed:** 2026-05-15  
**Environment:** Production  
**Status:** ✅ Fully Accepted — Production Validated (after Hotfix 1)  
**Type:** Frontend-only

---

## Behavior Changed

### Client Management Cards — Pet Visibility
- **Before:** Client cards showed no pet information. Admin had to open individual CareCards to see which pets belonged to a client.
- **After:** Client cards display:
  - 🐾 Pet names and breeds summary (from `pet_names_summary` / `pet_breeds_summary`)
  - "No pets linked" label for clients without pet data
  - When a client is selected: individual PET# records with name, species, breed, and archived status
  - "Legacy summary only" label when summary exists but no individual PET# records found
  - `client_id` at the bottom of each card for traceability

### CareCard Footer — Client Traceability
- **Before:** Footer showed only `Client ID: [submission UUID]`
- **After:** Footer shows:
  - Client ID (submission UUID)
  - Profile ID (linked_client_profile_id, when different from client_id)
  - Client name (from origin item)

---

## Technical Details

- Uses existing `pet_names_summary` and `pet_breeds_summary` fields on client profiles (populated by Release 4A on approval)
- Fetches individual PET# records via existing `GET /admin/pets/{petId}` when a client card is selected
- No backend changes required
- No new API endpoints

---

## Hotfix History

**Initial deploy:** Only showed `pet_names_summary` text. Did not show individual PET# records, client_id, or handle missing data gracefully.

**Hotfix 1:** Added PET# record fetch on client selection, "No pets linked" / "Legacy summary only" labels, client_id traceability on cards, and enhanced CareCard footer.

---

## Rollback

Revert `AdminDashboard.jsx` and `CareCard.jsx` → pet visibility and traceability removed. No data affected.
