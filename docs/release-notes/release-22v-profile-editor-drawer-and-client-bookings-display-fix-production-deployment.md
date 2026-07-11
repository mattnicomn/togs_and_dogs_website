# Release Notes — Release 22V: Profile Editor Drawer and Client Bookings Display Fix Production Deployment

**Release Date:** 2026-07-11
**Type:** Production Deployment
**Status:** ✅ **PASS** — Deployed & validated in production.

---

## 🌟 Overview

Release 22V deploys the combined fixes from **Release 22S** (Admin Profile Editor drawer stability, overlay, and scrollbar overflow fixes) and **Release 22U** (Client Portal `/my-bookings` date timezone parse offset, range formatting, plural visit windows, and progress badges) to the production environment.

Both features have been successfully built, synced to S3, cache invalidated, and verified live via automated browser validation.

---

## 🚀 Deployment Operations

### 1. Build Verification
- Command: `npm run build` inside `web/`
- Production Bundles Compiled:
  - JS: `dist/assets/index-CZXrWtrt.js` (944.46 kB)
  - CSS: `dist/assets/index-BHyXIxXF.css` (72.52 kB)

### 2. S3 Sync
- Bucket: `s3://togs-and-dogs-prod-toganddogs-hosting`
- Clean Deployment: Deleted obsolete assets from previous builds (`index-CZ9BNQCc.js` and `index-TDqXjha5.css`), and uploaded the new 22V assets.

### 3. CloudFront Invalidation
- Distribution ID: `E35L00QPA2IRCY`
- Invalidation ID: `I7CAY1196DA62J897U29B4NM0S`
- Status: ✅ **Completed**

### 4. Production Resource Check
- Fetched live index.html from `https://toganddogs.usmissionhero.com/` and verified it references the correct new assets:
  ```html
  <script type="module" crossorigin src="/assets/index-CZXrWtrt.js"></script>
  <link rel="stylesheet" crossorigin href="/assets/index-BHyXIxXF.css">
  ```

---

## 🔬 Production Validation Results

### 1. Admin Profile Editor Drawer (Release 22S Validation)
- **Stability & Interaction:** Clicking `Manage` on staff members successfully renders the drawer as an app-level overlay via React Portal on `document.body`. Stacking context bugs and visual flickering have been completely resolved. 
- **Scroll Containment:** Body scrolling is locked when the drawer is open (`document.body.style.overflow = 'hidden'`), eliminating horizontal/vertical page-level scrollbars. The drawer correctly scrolls internally when its content overflows.
- **Mouse Hover Behavior:** Moving the cursor over staff cards behind the drawer and interactive elements inside the drawer causes zero flickering or unexpected drawer dismissals.
- **Orphaned Identity Guardrails:** Validated that `USmissionhero` displays the correct "Orphaned Login" warning banner and disables Cognito/auth management action buttons.
- **Protected Profile Guardrails:** Validated that protected admin profiles show the appropriate guardrail indicators.

### 2. Client Portal /my-bookings (Release 22U Validation)
- **Timezone Offsets Resolved:** Verified that Joey Rockwell's overnight bookings display their correct dates:
  - **Dec 10–13, 2026** (no longer showing Dec 9).
  - **Sep 15–23, 2026** (no longer showing Sep 14).
- **Multi-Day Ranges & Badges:** Confirmed that the `Multi-Day` badge is rendered on all multi-day booking cards.
- **Plural Visit Windows & Friendly Labels:** Verified that booking cards correctly show all preferred time slots with clean labels (**"Morning (7–10 AM), Midday (10 AM–2 PM), Evening (5–8 PM)"**), rather than defaulting only to the first raw string value.
- **Progress Badges:** Confirmed the display of visit progress badges (**"0/4 visits done"** and **"0/9 visits done"**).
- **Intake Form Check:** Verified that the `/book` care request intake form loads successfully.

---

## 📋 Files Changed

| Component | Files |
|-----------|-------|
| **Frontend** | [`web/src/components/ClientPortal.jsx`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/ClientPortal.jsx) (Date & window fix) |

---

## 🛡️ Guardrails Checked & Confirmed
- No backend deployment or database writes.
- No Terraform applied.
- No client, pet, request, worker, or Stripe records modified during validation.
- No email invitations sent or Cognito passwords reset.
- `web/dist` and other prohibited files remained untracked/uncommitted.
