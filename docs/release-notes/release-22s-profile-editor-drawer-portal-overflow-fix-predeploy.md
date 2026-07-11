# Release Notes — Release 22S: Profile Editor Drawer Portal and Viewport Overflow Fix Pre-Deploy

**Release Date:** 2026-07-11
**Type:** Frontend Bug Fix (Pre-Deploy)
**Status:** ✅ **PASS (Pre-Deploy, deployed via 22V)** — Built successfully and deployed to production.

---

## 🌟 Overview

Release 22S fixes the persistent Profile Editor drawer stability, flicker, and viewport overflow scrollbar issues observed by Matthew during Release 22R manual validation.

It renders the Profile Editor drawer using a React Portal to `document.body` to completely isolate it from parent layout stacking contexts, locks the body scroll to prevent layout reflows/shifts, and resolves CSS overflow behaviors.

---

## 🔍 Root Cause Analysis

Even after Release 22Q/22R, the drawer remained unstable and created vertical/horizontal scrollbars because:

1. **Stacking Context & Layout Nesting:** The drawer overlay was rendered deep inside the `.staff-management-container` and `.staff-grid` element tree. Parent transforms, offsets, or flex configurations caused the fixed overlay and drawer to inherit clipping boundaries, resulting in horizontal/vertical page scrollbars when layout widths exceeded viewports.
2. **Backdrop Fallthrough:** Clicks/mousedowns on the backdrop area were not fully blocked, causing interactions with the page elements underneath.
3. **GPU Paint Flickering:** The `backdrop-filter: blur(4px)` property caused re-layout rendering artifacts/flickering in certain browsers during mousemove events over the staff cards.

---

## ✅ Changes Implemented

### 1. Portaling the Drawer to the Document Root
**File:** [`AdminDashboard.jsx`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)

Imported `createPortal` from `react-dom` and wrapped the drawer overlay rendering:
```javascript
{isStaffDrawerOpen && createPortal(
  <div className="profile-editor-drawer-overlay" onClick={(e) => e.stopPropagation()} onMouseDown={(e) => e.stopPropagation()}>
    <div className="profile-editor-drawer" onClick={(e) => e.stopPropagation()} onMouseDown={(e) => e.stopPropagation()}>
      ...
    </div>
  </div>,
  document.body
)}
```
This detaches the drawer overlay from the parent layout and renders it directly under `document.body`, avoiding any clipping constraints and stabilizing z-index.

### 2. Body Scroll and Viewport Overflow Lock
**File:** [`AdminDashboard.jsx`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)

Added a dedicated `useEffect` to lock page scroll dynamically when the drawer is open and restore it upon closure/unmounting:
```javascript
useEffect(() => {
  if (isStaffDrawerOpen) {
    const originalOverflow = document.body.style.overflow;
    const originalOverflowX = document.body.style.overflowX;
    document.body.style.overflow = 'hidden';
    document.body.style.overflowX = 'hidden';
    return () => {
      document.body.style.overflow = originalOverflow;
      document.body.style.overflowX = originalOverflowX;
    };
  }
}, [isStaffDrawerOpen]);
```

### 3. CSS Layout Fixes
**File:** [`Admin.css`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/Admin.css)

- **Overlay:** Set to `position: fixed`, `inset: 0` (equivalent to top/left/right/bottom: 0), `width: 100vw`, `height: 100dvh` (dynamic viewport height), `overflow: hidden`, and a stable high `z-index: 9999`. Removed `backdrop-filter: blur(...)` to eliminate GPU repaint flickers. Set `pointer-events: auto` to block all clicks to underlying elements.
- **Drawer:** Set to `position: fixed`, `top: 0`, `right: 0`, `height: 100dvh`, `width: min(560px, 100vw)`, `box-sizing: border-box`, `overflow-y: auto`, `overflow-x: hidden`, and a higher `z-index: 10000`.
- Added CSS supports check for a `100vh` fallback for older browsers.

---

## 🧪 Build Results

| Item | Value |
|------|-------|
| Command | `npm run build` |
| Status | ✅ **PASS** |
| JS Bundle | `dist/assets/index-Elsc2HUX.js` (941.20 kB) |
| CSS Bundle | `dist/assets/index-BHyXIxXF.css` (72.52 kB) |
| Errors | None |

---

## 🛡️ Guardrails Confirmed

- Frontend code/docs only. No Terraform applied. No backend deployment.
- No DynamoDB writes. No Cognito/profile/login mutations.
- No cancellation actions. No emails sent. No Stripe/calendar/mobile changes.
- `web/dist` and scratch files not committed.
