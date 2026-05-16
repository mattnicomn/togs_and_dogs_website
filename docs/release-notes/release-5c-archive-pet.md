# Release 5C: Archive Pet from CareCard

**Deployed:** 2026-05-15  
**Environment:** Production  
**Status:** ✅ Fully Accepted — Production Validated  
**Type:** Frontend-only

---

## Behavior Changed

### Archive Pet Action
- **Before:** No way to remove/hide a pet from the CareCard without direct DynamoDB access.
- **After:** Owner/admin can archive any individual pet from the multi-pet selector in CareCard.

### How It Works
1. Open a multi-pet CareCard (2+ active pets)
2. "Archive Pet" button appears at the end of the pet selector row
3. Click → inline confirmation: `Archive "[name]"? [Yes] [No]`
4. Click "Yes" → sets `is_active: false` on the PET# record via existing `updatePet` API
5. Pet disappears from active tabs immediately
6. Next available pet is auto-selected
7. Reopening CareCard keeps archived pet hidden

### Visibility Rules
- Only shown for owner/admin role
- Only shown when 2+ active pets exist (can't archive the only pet)
- Only shown for real PET# records (not legacy/request-level pets)
- Hidden during edit mode or add-pet mode

### Technical Details
- Uses existing `PUT /admin/pets/{petId}` with `is_active: false`
- No backend changes needed
- `_normalizePets()` filters `is_active !== false` from the active pet list
- Inline confirmation replaces `window.confirm` (which was blocked by scroll-lock CSS)

---

## Hotfix History

**Initial deploy:** `window.confirm()` was blocked by CareCard's scroll-lock CSS (`body { position: fixed }`). Clicking "Archive Pet" did nothing.

**Hotfix:** Replaced with inline two-step confirmation UI. No browser dialog needed.

---

## Rollback

Revert `CareCard.jsx` → Archive Pet button removed. Archived pets remain with `is_active: false` (harmless, can be restored via API).
