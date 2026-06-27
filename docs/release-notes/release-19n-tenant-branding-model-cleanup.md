# Release 19N — Tenant Branding Model Cleanup

Release **19N** implements the frontend-only brand separation and operator attribution updates in the operations portal. This ensures that when secondary business tenants are logged in, the UI displays their business name and isolates all product-level branding to platform operator attributions (`usmissionhero`), avoiding any Togs & Dogs branding confusion.

---

## 🚀 Accomplishments

### 1. Dynamic Shell Logo (`App.jsx`)
- Replaced the hardcoded top-left logo `Tog&Dogs` in `App.jsx` with a dynamic version.
- When on an administrative route (`/admin` or `/platform-admin`), the logo displays `<Tenant Business Name>: A Pet Business Platform` (retrieved from the backend via `/admin/tenant-info`).
- On public/client routes, it safely displays the default brand name `Tog&Dogs`.

### 2. Header & Dropdown Alignment
- Replaced the subtitle `Powered by Tog&Dogs` in `AdminDashboard.jsx` (line 3260) with `Powered by usmissionhero` to represent the operator.
- Updated the `UserProfile` call within the admin dashboard to pass `tenantInfo` as a React prop, ensuring consistency across components.
- Modified `UserProfile.jsx` to receive `tenantInfo` as a prop and removed the duplicate local state and `useEffect` fetch call (which was causing duplicate API requests).

### 3. Conditional Clean Footer (`App.jsx`)
- Created a conditional footer in `App.jsx` based on the path.
- For admin/platform routes, the large client-marketing footer (badges, description, and marketing links) is hidden, and a clean, minimal footer bottom is rendered:
  `© 2026 <Tenant Business Name>. Powered by usmissionhero.`
- For public client-facing routes, the default Togs & Dogs marketing footer continues to render normally.

### 4. Build Validation
- Compiled the frontend locally with **Vite**:
  `npm run build`
  - **Status:** **SUCCESSFUL**
  - **JS Bundle Produced:** `dist/assets/index-z7VYqP25.js`

---

## 🔒 Guardrails & Safety Confirmed
- Zero backend Lambda code changes occurred.
- Zero Terraform resource changes were evaluated.
- No Cognito attributes, users, or schemas were altered.
- No tenant metadata changes occurred.
- No production database or Stripe writes occurred.
