# Release 17O: Platform Management UI MVP

**Status:** Design Complete
**Date:** 2026-06-21
**Priority:** High (enables self-service tenant management for usmissionhero operators)
**Scope:** Design the /platform-admin UI pages, routes, access guards, and frontend integration

---

## 1. Route and Access Model

### URL Structure

| Route | Page | Access |
|-------|------|--------|
| `/platform-admin` | Dashboard / tenant list | `platform_admin` only |
| `/platform-admin/tenants/:companyId` | Tenant detail | `platform_admin` only |
| `/platform-admin/audit` | Platform audit log | `platform_admin` only |

### Access Guard

```jsx
// Route guard: check Cognito groups for platform_admin
function PlatformAdminGuard({ children }) {
  const { user } = useAuth();  // existing auth context
  const groups = user?.signInUserSession?.idToken?.payload?.['cognito:groups'] || [];
  
  if (!groups.includes('platform_admin')) {
    return <Navigate to="/admin" replace />;  // Redirect non-platform users
  }
  return children;
}
```

### Visibility Rules

| Role | Can See /platform-admin? | Can See /admin? |
|------|--------------------------|-----------------|
| `platform_admin` | ✅ Yes | ✅ Yes (superset) |
| `owner` / `admin` | ❌ No (redirected) | ✅ Yes |
| `staff` | ❌ No | ❌ No (staff views only) |
| `client` | ❌ No | ❌ No (client views only) |

### Navigation

- Add a "Platform Admin" link in the header/nav ONLY when user has `platform_admin` group
- Do NOT show this link for business owners, staff, or clients
- Keep existing `/admin` navigation unchanged

---

## 2. MVP Pages

### Page 1: Platform Dashboard / Tenant List (`/platform-admin`)

```
┌─────────────────────────────────────────────────────────┐
│ 🏢 Platform Admin                                       │
│ ─────────────────────────────────────────────────────── │
│                                                         │
│ Tenants (1)                    [Search: ________]       │
│                                                         │
│ ┌─────────────────────────────────────────────────────┐ │
│ │ Tog & Dogs                                          │ │
│ │ company_id: tog_and_dogs                            │ │
│ │ Tier: [Professional]  Status: [Active]              │ │
│ │ Created: May 6, 2025                                │ │
│ │                                         [View →]    │ │
│ └─────────────────────────────────────────────────────┘ │
│                                                         │
│ [View Audit Log]                                        │
└─────────────────────────────────────────────────────────┘
```

### Page 2: Tenant Detail (`/platform-admin/tenants/:companyId`)

```
┌─────────────────────────────────────────────────────────┐
│ ← Back to Tenants                                       │
│                                                         │
│ Tog & Dogs                                              │
│ company_id: tog_and_dogs                                │
│                                                         │
│ ┌── Subscription ───────────────────────────────────┐   │
│ │ Tier: Professional       Status: Active           │   │
│ │ Override Until: —                                  │   │
│ │                              [Edit Subscription]  │   │
│ └───────────────────────────────────────────────────┘   │
│                                                         │
│ ┌── Entitlement Summary ────────────────────────────┐   │
│ │ Max Staff: 5          Max Clients: 100            │   │
│ │ Max Bookings/mo: 250  Max Notifications/mo: 500   │   │
│ │ Google Calendar: ✅    Export: ✅                   │   │
│ │ Custom Branding: ❌    Video Evidence: ❌           │   │
│ └───────────────────────────────────────────────────┘   │
│                                                         │
│ ┌── Current Usage ──────────────────────────────────┐   │
│ │ Staff: 5/5     Clients: ~30/100                   │   │
│ │ (Usage counts are approximate)                    │   │
│ └───────────────────────────────────────────────────┘   │
│                                                         │
│ ┌── Platform Notes ─────────────────────────────────┐   │
│ │ [Internal notes text area — platform admin only]  │   │
│ └───────────────────────────────────────────────────┘   │
│                                                         │
│ ┌── Recent Audit ───────────────────────────────────┐   │
│ │ Jun 21, 2026 — admin_notes updated                │   │
│ │ Jun 20, 2026 — platform_admin smoke validation    │   │
│ └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Page 3: Platform Audit Log (`/platform-admin/audit`)

```
┌─────────────────────────────────────────────────────────┐
│ Platform Audit Log                                      │
│ ─────────────────────────────────────────────────────── │
│                                                         │
│ Date/Time          │ Action           │ Tenant          │
│ ───────────────────┼──────────────────┼──────────────── │
│ Jun 21 10:30 AM    │ tier_changed     │ tog_and_dogs    │
│ Jun 21 10:28 AM    │ notes_updated    │ tog_and_dogs    │
│                                                         │
│ (Showing last 50 entries)                               │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Tenant List Requirements

### Displayed Fields

| Field | Source | Format |
|-------|--------|--------|
| `display_name` | Tenant metadata | Text |
| `company_id` | Tenant metadata | Monospace/code |
| `subscription_tier` | Tenant metadata | Badge (color-coded) |
| `subscription_status` | Tenant metadata | Badge (color-coded) |
| `created_at` | Tenant metadata | Formatted date |

### Badge Colors

| Tier | Color |
|------|-------|
| Starter | Gray |
| Professional | Blue |
| Premium | Purple |
| Enterprise | Gold |

| Status | Color |
|--------|-------|
| Active | Green |
| Trialing | Blue |
| Past Due | Amber |
| Canceled | Red |
| Disabled | Dark gray |

### NOT Displayed

- ❌ Client names, emails, phone numbers
- ❌ Staff details
- ❌ Pet information
- ❌ Booking details
- ❌ Payment/Stripe IDs
- ❌ Cognito user details

---

## 4. Tenant Detail Requirements

### Metadata Panel

Display from `GET /platform/tenants/{company_id}` response:
- `display_name`, `company_id`
- `subscription_tier`, `subscription_status`
- `admin_override_until` (if set)
- `created_at`, `updated_at`

### Entitlement Summary Panel

Derived from tier (using TIER_LIMITS constants):
- Numeric limits: max_staff, max_active_clients, max_monthly_bookings, max_monthly_notifications
- Feature flags: google_calendar_enabled, export_enabled, custom_branding_enabled, video_evidence_enabled
- Show as ✅/❌ badges

### Usage Counts Panel

From backend response (COUNT queries):
- Staff count: X / max_staff
- Client count: ~X / max_active_clients
- Mark as "approximate" (counts may lag slightly)

### Privacy Constraints

- Do NOT display owner email in the UI unless the backend already safely returns it
- Do NOT display Cognito sub or user IDs
- Do NOT display any client/staff/pet private data on this page

---

## 5. Edit Form Requirements

### Editable Fields

| Field | Input Type | Validation |
|-------|-----------|------------|
| `display_name` | Text input | Required, max 100 chars |
| `subscription_tier` | Dropdown | starter, professional, premium, enterprise |
| `subscription_status` | Dropdown | active, trialing, past_due, canceled, paused, disabled |
| `admin_override_until` | Date picker (optional) | Future ISO date or clear |
| `admin_notes` | Textarea | Free text, max 1000 chars |

### Confirmation Modal

Triggered before submitting PATCH:

```
┌────────────────────────────────────────────────────┐
│ Confirm Tenant Update                              │
│                                                    │
│ Company: tog_and_dogs                              │
│                                                    │
│ Changes:                                           │
│ • subscription_tier: Professional → Premium        │
│                                                    │
│ ⚠️ Changing tier affects entitlement limits.       │
│ Current staff: 5 → new max: 15                    │
│                                                    │
│ [Cancel]           [Confirm & Save]                │
└────────────────────────────────────────────────────┘
```

### Warnings for Risky Changes

| Change | Warning |
|--------|---------|
| Tier downgrade | "Downgrading may restrict current usage. Staff: 5, new limit: 1." |
| Status → canceled/disabled | "This will block all tenant users from logging in." |
| Status → past_due | "Tenant will enter grace period with degraded access after 7 days." |

### NOT Supported in Edit

- ❌ Tenant deletion
- ❌ Raw DynamoDB editing
- ❌ Stripe configuration
- ❌ Cognito user management
- ❌ Client/staff/pet data editing

---

## 6. Audit Log UI

### Display Fields

| Column | Source |
|--------|--------|
| Timestamp | `timestamp` from audit record |
| Action | `action` field (formatted label) |
| Target Tenant | `target_company_id` |
| Changes | Summary of changed fields (from/to) |

### NOT Displayed

- ❌ Actor Cognito sub (show "Platform Admin" label instead)
- ❌ Raw request bodies
- ❌ Secrets or tokens
- ❌ Private data

---

## 7. Frontend Implementation Scope for AG

### New Files to Create

| File | Purpose |
|------|---------|
| `web/src/components/PlatformAdmin.jsx` | Tenant list + dashboard layout |
| `web/src/components/PlatformTenantDetail.jsx` | Detail view + edit form + audit panel |
| `web/src/components/PlatformAuditLog.jsx` | Standalone audit log page |
| `web/src/api/platform.js` | API helpers for /platform/* routes |

### Files to Modify

| File | Change |
|------|--------|
| `web/src/App.jsx` | Add `/platform-admin/*` routes with guard |

### API Client Functions (`web/src/api/platform.js`)

```javascript
export const getPlatformTenants = () => request('/platform/tenants', 'GET', null, true);
export const getPlatformTenant = (companyId) => request(`/platform/tenants/${companyId}`, 'GET', null, true);
export const updatePlatformTenant = (companyId, data) => request(`/platform/tenants/${companyId}`, 'PATCH', data, true);
export const getPlatformAudit = () => request('/platform/audit', 'GET', null, true);
```

### Error States

| Status | Display |
|--------|---------|
| 401 | Redirect to login |
| 403 | "Platform admin access required" + redirect |
| 404 | "Tenant not found" |
| 500 | "Server error — try again" |

### Loading/Empty States

- Loading spinner while fetching tenants
- "No tenants found" empty state (unlikely but handle)
- "No audit entries" empty state

---

## 8. Validation Plan

### After AG Implementation (17P)

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | Build passes | `npm run build` | ✅ No errors |
| 2 | Non-platform-admin cannot access `/platform-admin` | Log in as staff/owner | Redirected away |
| 3 | Platform admin can access `/platform-admin` | Log in as Matthew | Tenant list loads |
| 4 | Tenant list shows tog_and_dogs | Visual check | Name, tier, status visible |
| 5 | Tenant detail loads | Click tenant | Metadata, entitlements, usage shown |
| 6 | No private data visible | Inspect response/UI | No client emails/phones/addresses |
| 7 | Edit form opens | Click "Edit Subscription" | Form with dropdowns + notes |
| 8 | Confirmation modal works | Make a change → submit | Modal shows before saving |
| 9 | PATCH smoke (safe field) | Update `admin_notes` only | 200 + audit entry written |
| 10 | Audit log shows entry | Navigate to audit | Recent action visible |

### PATCH Smoke Safety

- First edit should be `admin_notes` only (zero entitlement impact)
- Tier/status changes tested separately in 17R with monitoring

---

## 9. Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Non-platform user accesses routes via URL | Route guard checks Cognito groups; backend returns 403 |
| Private data leaks into UI | Backend only returns tenant-level metadata; frontend doesn't query client/staff |
| Accidental tier downgrade | Confirmation modal with impact warning |
| Accidental disable/cancel | Confirmation modal with "blocks all users" warning |
| Stale usage counts | Mark as "approximate"; don't gate decisions on exact counts |
| UI deploys before backend is ready | Backend already deployed (17L); UI is safe to build |

---

## 10. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **17O** | Platform Management UI MVP design (this document) | ✅ Kiro (done) |
| **17P** | AG implements UI + deploys | AG |
| **17Q** | Matthew manual platform-admin UI smoke | Matthew + AG |
| **17R** | Safe tenant metadata edit smoke (admin_notes, then tier if approved) | Matthew + AG |
| **17S** | Second-tenant dry-run through platform admin flow | AG + Kiro |
| **17T** | Phase 2 entitlement gates | AG + Kiro |

---

## 11. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Frontend deployment
- ❌ Creating React components
- ❌ Modifying App.jsx
- ❌ DynamoDB writes
- ❌ Cognito changes
- ❌ Terraform changes
- ❌ Stripe/Postmark changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Ryan/tester changes
- ❌ Second tenant creation

This is a design document. UI implementation (17P) requires separate AG approval.
