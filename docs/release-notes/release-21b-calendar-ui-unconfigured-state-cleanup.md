# Release 21B — Calendar UI Unconfigured-State Cleanup

Release **21B** cleans up the frontend unconfigured-state calendar UI. It replaces the Google-specific connected/disconnected warning flows with provider-neutral unconfigured messaging for non-default tenants (such as `test_tenant_alpha`), while preserving full Google Calendar integrations for the default tenant (`tog_and_dogs`).

---

## Accomplishments

### 1. Frontend UI Scoping and Cleanup
- **Gated Click Handler:** Modified `handleConnectGoogle` in `AdminDashboard.jsx` to return early if the current tenant is not `tog_and_dogs`. This prevents initiating the Google OAuth backend flow and completely avoids the browser alert popup ("Connection failed...").
- **Gated Top Warning Banner:** Gated the top Google Calendar health/warning banner to only render for the default tenant (`tog_and_dogs`), preventing non-default tenants from seeing warnings to connect Google Calendar.
- **Provider-Neutral Settings Card:** Updated the "System Integrations" section in `AdminDashboard.jsx`. If the tenant is not `tog_and_dogs`:
  - Changes card title from "Google Calendar" to "Calendar Integration".
  - Displays status badge as `NOT CONFIGURED` with gray neutral styling.
  - Shows calm messaging:
    * *"Calendar integration is not configured for this business yet."*
    * *"Schedule sync can be enabled by the platform owner when this tenant is ready."*
  - Hides the "Connect Calendar" primary action button and technical details metadata.

### 2. Preserved Default Tenant Behavior
- Left all Google Calendar status checks, warning banners, credentials checks, disconnect capabilities, and connection workflows intact for the default `tog_and_dogs` tenant.

### 3. Frontend Compile Verification
- Ran the production Vite build (`npm run build` inside `web/`) and verified it compiled successfully into `dist/assets/index-Cws62sI4.js` with no deprecations or errors.

### 4. Production Deployment & Smoke Verification
- Synchronized built frontend files from `web/dist/` to the production S3 bucket `s3://togs-and-dogs-prod-toganddogs-hosting`.
- Invalidated CloudFront cache distribution `E35L00QPA2IRCY` (invalidation ID: `I9V2NDXNL6K6M1JO9YCSY8I3Y2`) and verified it completed successfully.
- Verified that the live production HTML at `https://toganddogs.usmissionhero.com` loads successfully and references the new JS bundle `index-Cws62sI4.js`.
- Verified that `/admin` path loads correctly and serves the updated bundle.

---

## Manual Validation Checklist (Post-Deploy)

### A. Test Tenant Owner (`test_tenant_alpha`):
* [ ] `/admin` loads successfully with no auth errors.
* [ ] Top Google Calendar warning banner is hidden.
* [ ] Under "System Integrations", the card displays "Calendar Integration" with status `NOT CONFIGURED`.
* [ ] Message says *"Calendar integration is not configured for this business yet. Schedule sync can be enabled by the platform owner when this tenant is ready."*
* [ ] No primary "Connect Calendar" button appears.
* [ ] No technical details panel containing Google OAuth information appears.
* [ ] No Google Calendar error popup/alert appears.
* [ ] No Togs & Dogs calendar/account details are visible.

### B. Original Tenant Admin (`tog_and_dogs`):
* [ ] `/admin` loads successfully.
* [ ] Google Calendar connection states, badges, and warning banners load and function normally.
* [ ] Technical details panel and account status remain visible.
* [ ] "Connect Calendar" or "Disconnect" actions continue to function as before.

---

## Overall Status: ✅ PASS (Deployment Completed)

Release 21B is successfully deployed to production. Automated smoke checks passed. Manual verification of the checklist is pending Matthew's review.

