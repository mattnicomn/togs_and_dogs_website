# Release 5F: Archived Pets Visibility & Restore

**Deployed:** 2026-05-15  
**Environment:** Production  
**Status:** ✅ Fully Accepted — Production Validated After Hotfix  
**Type:** Frontend-only

---

## Behavior Changed

### Show Archived Toggle
- **Before:** Archived pets disappeared permanently from CareCard with no way to see or restore them without direct API calls.
- **After:** A "Show Archived" checkbox appears whenever archived pets exist for the record. Checking it reveals archived pet tabs with a ⊘ marker.

### Restore Pet
- **Before:** No restore capability in the UI.
- **After:** Selecting an archived pet shows a "Restore Pet" button. Clicking it sets `is_active: true` and returns the pet to the active tab list.

### Visibility Rules
- Archived pets hidden by default
- "Show Archived" toggle appears for owner/admin when `hasArchivedPets` is true
- Toggle works even when only 1 active pet remains (hotfix)
- Archived pets display with ⊘ marker in tab chips
- "Restore Pet" replaces "Archive Pet" for archived pets

---

## Hotfix History

**Initial deploy:** "Show Archived" toggle was inside the `hasMultiplePets` gate. When archiving left only 1 active pet, the toggle disappeared because the entire pet selector block was hidden.

**Hotfix:** Moved "Show Archived" toggle to also render in the single-pet view area, gated only by `petInfo.hasArchivedPets` — not by `hasMultiplePets`.

---

## Technical Details

- `_normalizePets()` returns `hasArchivedPets: true` when any pet has `is_active === false`
- When `showArchived` is true, all pets (including archived) are included in the visible list
- Restore uses existing `onUpdate({ pet_id, client_id, is_active: true })` → `PUT /admin/pets/{petId}`
- No backend changes required
- No permanent delete implemented (deferred due to ghost-reference risk)

---

## Rollback

Revert `CareCard.jsx` → toggle and restore button removed. Archived pets remain with `is_active: false` (restorable via API).
