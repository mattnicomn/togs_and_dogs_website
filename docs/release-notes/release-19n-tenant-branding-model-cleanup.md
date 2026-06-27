# Release 19N — Tenant Branding Model Cleanup

Release **19N** implements the frontend-only brand separation and operator attribution updates in the operations portal. This ensures that when secondary business tenants are logged in, the UI displays their business name and isolates all product-level branding to platform operator attributions (`usmissionhero`), avoiding any Togs & Dogs branding confusion.

---

## Accomplishments

### 1. Dynamic Shell Logo (`App.jsx`)
- Replaced the hardcoded top-left logo `Tog&Dogs` in `App.jsx` with a dynamic version.
- When on an administrative route (`/admin` or `/platform-admin`), the logo displays `<Tenant Business Name>: A Pet Business Platform` (retrieved from the backend via `/admin/tenant-info`).
- On public/client routes, it safely displays the default brand name `Tog&Dogs`.

### 2. Header & Dropdown Alignment
- Replaced the subtitle `Powered by Tog&Dogs` in `AdminDashboard.jsx` with `Powered by usmissionhero` to represent the operator.
- Updated the `UserProfile` call within the admin dashboard to pass `tenantInfo` as a React prop, ensuring consistency across components.
- Modified `UserProfile.jsx` to receive `tenantInfo` as a prop and removed the duplicate local state and `useEffect` fetch call (which was causing duplicate API requests).

### 3. Conditional Clean Footer (`App.jsx`)
- Created a conditional footer in `App.jsx` based on the path.
- For admin/platform routes, the large client-marketing footer (badges, description, and marketing links) is hidden, and a clean, minimal footer bottom is rendered:
  `© 2026 <Tenant Business Name>. Powered by usmissionhero.`
- For public client-facing routes, the default Togs & Dogs marketing footer continues to render normally.

### 4. Build Validation
- Compiled the frontend locally with Vite (`npm run build`)
- **Status:** SUCCESSFUL
- **JS Bundle Produced:** `dist/assets/index-z7VYqP25.js`

---

## Production Deployment

| Step | Detail | Status |
|------|--------|--------|
| S3 Sync | `s3://togs-and-dogs-prod-toganddogs-hosting` | Complete |
| Old bundle deleted | `assets/index-612JB2x1.js` removed | Done |
| New bundle uploaded | `assets/index-z7VYqP25.js` uploaded | Done |
| CloudFront Invalidation | ID: `I7OEVMLKTLFX37G0NZOTYWK20N` on `E35L00QPA2IRCY` | Completed |
| Commit | `b6d5749` | Pushed to `origin/main` |

---

## Smoke Validation

| Check | Result |
|-------|--------|
| `https://toganddogs.usmissionhero.com` loads | HTTP 200 |
| Production HTML references 19N JS bundle | `src="/assets/index-z7VYqP25.js"` confirmed |
| CloudFront invalidation status | `Completed` |

---

## Guardrails & Safety Confirmed
- Zero backend Lambda code changes occurred.
- Zero Terraform resource changes were evaluated.
- No Cognito attributes, users, or schemas were altered.
- No tenant metadata changes occurred.
- No production database or Stripe writes occurred.

---

## Manual Validation Results — PASS (2026-06-27)

Matthew performed manual validation in a fresh incognito/private browser session.

### Checklist A — `test_tenant_alpha` Owner: PASS

| Item | Result |
|------|--------|
| Top-left/admin shell displays `Test Tenant Alpha: A Pet Business Platform` | PASS |
| Admin subtitle displays `Powered by usmissionhero` | PASS |
| Profile dropdown Company displays `Test Tenant Alpha` | PASS |
| Footer displays `© 2026 Test Tenant Alpha. Powered by usmissionhero.` | PASS |
| Google Calendar NOT CONNECTED (no Togs & Dogs calendar leak) | PASS |
| No Togs & Dogs tenant-owned data visible | PASS |
| No 401/403/auth/session errors observed | PASS |

### Checklist B — `tog_and_dogs` Admin/Platform User: PASS

| Item | Result |
|------|--------|
| Existing Togs & Dogs admin behavior intact | PASS |
| Google Calendar connected and healthy | PASS |
| Existing staff/client/booking views work normally | PASS |
| Platform Admin loaded and showed both tenants | PASS |
| No 401/403/auth/session errors observed | PASS |

### Overall Status: ✅ PASS

Release 19N is **complete**. The tenant branding model cleanup is fully validated in production.

> This validation also resolves the outstanding display branding failure from Release 19M (PARTIAL PASS / PENDING DISPLAY FIX). The 19M display defect is now considered remediated by Release 19N.
