# Release Notes — Release 22Q: Profile Editor Drawer Stability and Overlay Interaction Fix Pre-Deploy

**Release Date:** 2026-07-10
**Type:** Frontend Bug Fix (Pre-Deploy)
**Status:** ✅ **PASS (Pre-Deploy)** — Built successfully. Awaiting deployment.

---

## 🐛 Issue

After Release 22P deployed the Centralized Profile Editor MVP to production, Matthew validated the new UI and found a **critical drawer stability blocker**:

- The Profile Editor drawer flickered, disappeared, or popped in and out while open.
- Moving the mouse over staff cards or the background caused the drawer to become unstable.
- The overlay backdrop area appeared blurred but interactions felt broken.
- Screenshot showed the drawer open for USmissionhero but the background was heavily blurred and the drawer was unstable.

**Release 22P manual validation is NOT PASS pending this fix.**

---

## 🔍 Root Cause Analysis

Three independent bugs combined to cause the instability:

### Bug 1 — Card-Level `onClick` Re-Invoked `handleEditStaff` on Every Card Click

```jsx
// BEFORE (broken)
<div className="staff-profile-card" onClick={() => handleEditStaff(s)}>
  ...
  <button onClick={(e) => { e.stopPropagation(); handleEditStaff(s); }}>Manage</button>
</div>
```

Every click *anywhere* on a staff card (including accidental touches near the overlay edge) re-invoked `handleEditStaff`, which:
1. Reset all drawer state (`editingStaffId`, `staffForm`, `selectedStaffForDrawer`)
2. Set `isStaffDrawerOpen = false` then immediately `true`
3. Caused the drawer to unmount and remount → visible flicker

The Manage button already had its own `stopPropagation` + `handleEditStaff`. The card-level onClick was redundant and destructive.

### Bug 2 — Overlay Backdrop Captured All Pointer Events → Accidental Close

```jsx
// BEFORE (broken)
<div className="profile-editor-drawer-overlay" onClick={closeStaffDrawer}>
```

The overlay was a full-viewport fixed `div` at `z-index: 1000`. It received **all** mouse events over the backdrop. Any accidental click on the blurred area closed the drawer immediately. Since the staff card area was under the overlay, any card click bubbled up to `closeStaffDrawer`.

There was no `pointer-events` isolation — the overlay captured clicks meant for the page.

### Bug 3 — Staff Card Hover CSS Caused Layout Reflow Under Overlay

```css
/* BEFORE (broken) */
.staff-profile-card:hover {
  transform: translateY(-2px); /* causes layout shift under overlay */
  box-shadow: var(--shadow-md);
}
```

With the overlay's `backdrop-filter: blur(4px)` active, the cards underneath still triggered `:hover` effects on mouse movement. The `transform: translateY(-2px)` caused layout reflow that propagated visually through the blur, creating the "flickering background" effect Matthew observed.

---

## ✅ Fixes Applied

### Fix 1 — Remove Card-Level `onClick` from Staff Card Div

**File:** [`AdminDashboard.jsx`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)

```diff
- <div className="staff-profile-card" onClick={() => handleEditStaff(s)} ...>
+ <div className="staff-profile-card" ...>
```

The Manage button retains its own `e.stopPropagation() + handleEditStaff(s)` handler. Cards no longer have a card-level click-to-open, which eliminates state churn and re-render flicker.

When the drawer is open, cards show `cursor: default` (not pointer) to reinforce that they are not clickable.

### Fix 2 — Overlay Backdrop is Now Visual-Only (`pointer-events: none`)

**Files:** [`AdminDashboard.jsx`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx), [`Admin.css`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/Admin.css)

JSX overlay `onClick` changed from `closeStaffDrawer` → `e.stopPropagation()` (no-op).

CSS overlay gets `pointer-events: none` so the backdrop captures **zero** mouse events. Only the drawer panel itself (which has `pointer-events: auto` explicitly) is interactive.

Drawer close now requires the **explicit X button only** — no accidental close from clicking the background.

```diff
- .profile-editor-drawer-overlay { ... }     /* captured all events */
+ .profile-editor-drawer-overlay {
+   pointer-events: none;                     /* visual-only backdrop */
+ }
+ .profile-editor-drawer {
+   pointer-events: auto;                     /* drawer is fully interactive */
+   z-index: 1001;                            /* above overlay */
+   will-change: transform;                   /* prevent repaint flicker */
+ }
```

### Fix 3 — Suppress Card Hover Transform While Drawer is Open

**File:** [`Admin.css`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/Admin.css)

Added `drawer-open` class to staff-grid container when `isStaffDrawerOpen === true`. CSS rule suppresses hover transform:

```css
/* When drawer is open, suppress staff-card hover transform */
.staff-grid.drawer-open .staff-profile-card:hover,
.staff-grid.drawer-open .client-profile-card:hover {
  transform: none;
  box-shadow: none;
  border-color: inherit !important;
}
```

This eliminates the "flickering background" visual artifact caused by layout reflow under the backdrop-filter blur.

---

## 📋 Files Changed

| File | Change |
|------|--------|
| [`web/src/components/AdminDashboard.jsx`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx) | Removed card-level `onClick`; overlay `onClick` → `stopPropagation`; added `onMouseDown` stopPropagation to drawer; added `drawer-open` class to staff-grid; `cursor: default` on cards when drawer open |
| [`web/src/Admin.css`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/Admin.css) | Added `pointer-events: none` to overlay; `pointer-events: auto` + `z-index: 1001` + `will-change: transform` to drawer; added `.staff-grid.drawer-open` hover suppression rule |

---

## 🧪 Build Results

| Item | Result |
|------|--------|
| Command | `npm run build` |
| Status | ✅ **PASS** |
| Build time | 355ms |
| JS Bundle | `dist/assets/index-CZ9BNQCc.js` (940.90 kB) |
| CSS Bundle | `dist/assets/index-TDqXjha5.css` (72.39 kB) |
| Errors | None |

> [!NOTE]
> No frontend test script exists in this project (Vite does not include a built-in test runner). Build success is the verification gate. Backend tests are unaffected (frontend-only fix).

---

## 🔬 Validation Checklist (For Matthew Post-Deploy)

**Drawer Stability:**
- [ ] Open Staff Management
- [ ] Click Manage on USmissionhero
- [ ] Confirm drawer opens on right side and stays open
- [ ] Move mouse over staff cards / background area behind blur — drawer must NOT flicker or disappear
- [ ] Move mouse from card area into drawer — drawer must remain open and stable
- [ ] Scroll inside drawer — drawer must remain stable
- [ ] Hover buttons/fields in drawer — drawer must remain stable
- [ ] Click X button — drawer closes normally
- [ ] Unsaved changes guard: modify a field, click X → confirm dialog appears, Cancel returns to drawer

**Normal Profile (e.g. Ryan York):**
- [ ] Click Manage → drawer opens, all sections visible
- [ ] Drawer stays open on mouse hover over cards

**Protected Admin:**
- [ ] Click Manage → Protected banner visible, dangerous actions hidden/disabled
- [ ] Drawer stays stable

**USmissionhero Orphaned:**
- [ ] Click Manage → Orphaned Login state, risky actions disabled
- [ ] Drawer stays stable

**Do NOT during validation:**
- Send any invite/password reset/temp password emails
- Unlink, delete, disable, or restore any profile
- Save any profile changes unless using local/non-production

---

## 🛡️ Guardrails Confirmed

| Guardrail | Status |
|-----------|--------|
| Frontend code/docs only | ✅ |
| No production deployment | ✅ |
| No AWS commands | ✅ |
| No Terraform | ✅ |
| No DynamoDB writes | ✅ |
| No Cognito/profile/login mutations | ✅ |
| No cancellation actions | ✅ |
| No invite/password reset emails | ✅ |
| No Stripe changes | ✅ |
| No Google Calendar changes | ✅ |
| No mobile/TestFlight/App Store changes | ✅ |
| No dist committed | ✅ |
| No .tfplan committed | ✅ |
| No logs/screenshots committed | ✅ |

---

## 🔄 Deployment Status

- **Code fixes:** Applied and built ✅
- **Production deployment:** ❌ Not yet — Matthew must validate locally/against dev preview first
- **22P manual validation:** Still PENDING — will be re-run after 22Q is deployed
