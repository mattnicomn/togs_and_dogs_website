# Release 5B: Add New Pet from CareCard

**Deployed:** 2026-05-15  
**Environment:** Production  
**Status:** ✅ Fully Accepted — Production Validated  
**Type:** Frontend + Backend (minor)  
**Committed with:** Release 5C (commit `e837aa8`)

---

## Behavior Changed

### Add Pet Action
- **Before:** New pets could only be created through the intake approval flow or direct API calls. No way to add a pet to an existing client from the admin CareCard.
- **After:** Owner/admin can add a new pet directly from the CareCard pet selector area.

### How It Works
1. Open CareCard for an approved record with a linked client profile
2. Click "+ Add Pet" button (visible in pet selector area or Overview tab for single-pet records)
3. Fill in the inline form: name (required), species, breed, age, feeding/medication/behavior notes
4. Click "Create Pet"
5. Backend creates a new PET# record via `POST /admin/pets`
6. Backend appends the new `pet_id` to the parent REQ record's `pet_ids` array
7. CareCard refreshes and shows the new pet as an additional selectable tab
8. New pet is auto-selected after creation

### Persistence
- New pet persists after closing and reopening the CareCard
- The parent REQ record's `pet_ids` array is durably updated by the backend
- Request List data refreshes to reflect the new pet

### Visibility Rules
- Only shown for owner/admin role
- Only shown when a linked client profile ID or client_id exists
- Hidden during edit mode or while another add-pet form is open
- Not available for pre-approval records without a persistent client profile

---

## Backend Change

`src/backend/handlers/pet_handler.py` — When `request_id` is provided in the create-pet body, the handler now appends the new `pet_id` to the REQ record's `pet_ids` array using `list_append`. This ensures the new pet is persistently linked and appears on future CareCard loads.

---

## Hotfix History

- **Hotfix 1:** Fixed missing `createPet` import in AdminDashboard.jsx
- **Hotfix 2:** Fixed CareCard not refreshing after creation (stale `pet_ids` on origin item)
- **Hotfix 3:** Fixed persistence — backend now appends new pet_id to REQ `pet_ids` array

---

## Rollback

- Revert CareCard.jsx and AdminDashboard.jsx → "+ Add Pet" button removed
- Revert pet_handler.py → `pet_ids` append removed (singular `pet_id` link still works)
- PET# records already created remain valid
