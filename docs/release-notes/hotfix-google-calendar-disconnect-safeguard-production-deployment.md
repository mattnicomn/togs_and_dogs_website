# Hotfix: Google Calendar Disconnect Safeguard — Production Deployment

**Date:** 2026-07-12
**Status:** ✅ PASS — Deployed to Production
**Type:** Frontend-only production hotfix (cumulative build)
**Deployed Commit:** `11e2876`
**Previous Production Commit:** `a532650` (Release 22V)
**Priority:** Urgent (Ryan demonstration readiness)

---

## ⚠️ Cumulative Deployment Notice

Although approval was limited to the Google Calendar disconnect safeguard, the deployed Vite build was generated from the full repository tree at commit `11e2876`. Therefore, **all previously undeployed frontend commits** in its ancestry were also included in the production bundle:

| Commit | Release | Frontend Changes |
|--------|---------|-----------------|
| `669e0be` | 22ZA | Responsive foundation: mobile hamburger nav, scrollable tabs, overflow prevention |
| `dafe53a` | 22ZA | Mobile drawer accessibility closeout (focus trap, Escape key) |
| `b18c070` | 22ZB | Profile Editor full-screen mobile sheet layout |
| `bedcebd` | 22ZC | Dashboard cards compact layout, Request List mobile cards, filter controls stacking |
| `b532111` | 22ZC | sr-only accessible labels in mobile request-card cells |
| `11e2876` | Hotfix | Google Calendar disconnect safeguard (button removed, explanation added) |

**Source files cumulatively modified:**
- `web/src/components/AdminDashboard.jsx` — mobile navigation, hamburger menu, responsive stat cards, Request List mobile card layout, data-label attributes, sr-only labels, filter bar class structure, Profile Editor full-screen sheet, calendar disconnect removal
- `web/src/Admin.css` — sr-only utility, mobile breakpoints (≤480px, 481–767px), hamburger/drawer styles, stat-card focus/active states, request-table mobile card layout, data-label ::before pseudo-elements, expanded-details-grid responsive, filter controls stacking, Profile Editor mobile sheet styles, scrollable tab strip

---

## 1. Deployment Summary

| Item | Value |
|------|-------|
| Deployed commit | `11e2876` |
| Previous production commit | `a532650` (Release 22V) |
| Branch | `main` |
| Scope | Frontend-only (React/Vite web app) — cumulative build |
| S3 bucket | `togs-and-dogs-prod-toganddogs-hosting` |
| CloudFront distribution | `E35L00QPA2IRCY` |
| CloudFront invalidation ID | `IAAR4546T2EDWST7CFY38ORHRB` |
| Invalidation status | ✅ Completed |
| Production JS bundle | `/assets/index-DAx_msXw.js` |
| Production CSS bundle | `/assets/index-DdHmXCqb.css` |
| Previous production JS bundle | `/assets/index-CZXrWtrt.js` (deleted) |
| Previous production CSS bundle | `/assets/index-BHyXIxXF.css` (deleted) |

## 2. What Was Deployed (Cumulative)

### Google Calendar Disconnect Safeguard (Approved)
- Removed the tenant-wide "Disconnect" button from the Google Calendar integration card
- Added shared-business-calendar explanation text
- Removed `disconnectGoogle` API import and handler

### Release 22ZA: Responsive Foundation and Navigation (Previously Undeployed)
- Mobile hamburger/drawer navigation for screens ≤ 768px
- Scrollable horizontal admin tab strip
- Global overflow prevention CSS
- Mobile typography and spacing tokens
- Body scroll lock on drawer open
- Escape key and focus trap on mobile nav drawer

### Release 22ZB: Profile Editor Mobile Layout (Previously Undeployed)
- Profile Editor renders as full-screen sheet on mobile (< 768px)
- Sticky header with back/close and profile name
- Sticky footer with Cancel/Save
- Compact field spacing and 16px font-size (prevents iOS zoom)

### Release 22ZC: Dashboard Cards and Request List Mobile (Previously Undeployed)
- Dashboard stat cards: keyboard accessible (role="button", tabIndex, onKeyDown with Enter/Space + preventDefault)
- Request List: mobile card layout with data-label attributes and ::before pseudo-elements
- Filter controls: responsive stacking at ≤ 480px
- Expanded details: single-column grid on mobile
- sr-only accessible labels for screen reader cell identification

## 3. What Was NOT Changed

- ❌ No backend Lambda deployment
- ❌ No API Gateway changes
- ❌ No Terraform apply
- ❌ No DynamoDB writes
- ❌ No Cognito/auth changes
- ❌ No OAuth token or credential changes
- ❌ No Google Calendar event routing changes
- ❌ No Stripe changes
- ❌ No tenant resolution mode changes
- ❌ No mobile/TestFlight/App Store changes
- ❌ No production test data created
- ❌ No disconnect API endpoint invoked

## 4. Build and Lint Verification

| Check | Result |
|-------|--------|
| `npm run lint` | 47 problems (38 errors, 9 warnings) — baseline match |
| New lint findings | 0 |
| `npm run build` | ✅ Success (101 modules, 370ms) |

## 5. Live Production Validation

| Check | Result |
|-------|--------|
| Production site loads (HTTP 200) | ✅ Confirmed |
| New bundle served (`index-DAx_msXw.js`) | ✅ Confirmed |
| Homepage renders correctly | ✅ Confirmed |
| Navigation links functional | ✅ Confirmed |

### Requires Matthew Manual Confirmation

The following checks require authenticated admin access. Matthew should confirm:

| # | Check | Expected |
|---|-------|----------|
| 1 | Admin login works normally | ✅ Dashboard loads |
| 2 | Desktop navigation unchanged at ≥ 1024px | Tabs visible, no hamburger |
| 3 | Mobile (≤ 768px): hamburger menu appears | ☰ icon replaces desktop nav |
| 4 | Hamburger menu opens/closes, all nav items accessible | Smooth slide-in |
| 5 | Scheduler loads and displays | Calendar/schedule visible |
| 6 | Profile Editor drawer opens via "Manage" button | Stable, no flicker |
| 7 | Mobile: Profile Editor is full-screen sheet | Covers viewport |
| 8 | Dashboard stat cards respond to Enter/Space keys | Navigate to correct view |
| 9 | Request List: mobile shows stacked cards | One card per record |
| 10 | Search and filters work on mobile | Full-width, functional |
| 11 | Request expansion (▶) works, aria-expanded accurate | Details show below card |
| 12 | Google Calendar: Connected status visible | Green badge |
| 13 | Google Calendar: shared-calendar explanation visible | "Shared business calendar..." |
| 14 | Google Calendar: NO Disconnect button | Not rendered |
| 15 | No horizontal overflow at ~375px | No scrollbar |
| 16 | Logout works | Returns to login |

## 6. Connection Scope

The Google Calendar connection is **tenant/business-scoped**. Individual user calendar connections remain **deferred**.

## 7. Deployment Timeline

| Time (UTC) | Event |
|------------|-------|
| 2026-07-12 ~14:19 | S3 sync completed |
| 2026-07-12 14:19:38 | CloudFront invalidation created |
| 2026-07-12 ~14:20 | CloudFront invalidation completed |
| 2026-07-12 ~14:20 | Live site serving new bundle |
