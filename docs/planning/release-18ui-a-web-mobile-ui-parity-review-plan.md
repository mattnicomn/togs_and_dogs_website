# Release 18UI-A: Web and Mobile UI Parity Review Plan

**Status:** Planning
**Date:** 2026-06-24
**Priority:** Low-Medium (polish/consistency; no production blocker)
**Scope:** Review web/mobile UI consistency without code changes or rewrites

---

## 1. Current Technology Baseline

### Website (Web)

| Property | Value |
|----------|-------|
| Framework | React (Vite build) |
| Language | JavaScript (JSX) |
| Hosting | S3 + CloudFront (`toganddogs.usmissionhero.com`) |
| Styling | CSS (Portal.css + inline styles) |
| Auth | AWS Cognito (JWT-based) |
| State | Local component state (no global store) |
| Routing | React Router |
| Production | ✅ Deployed and live |

### Mobile App

| Property | Value |
|----------|-------|
| Framework | Expo / React Native |
| Language | JavaScript/TypeScript (JSX/TSX) |
| Distribution | TestFlight Internal only (build 1.0.0 (4)) |
| Auth | AWS Cognito + Expo SecureStore |
| Navigation | React Navigation (stack + tab) |
| State | Local component state |
| API | Same backend as web |
| Production (App Store) | ❌ Not published |

### Key Observation

**Both platforms are React-based.** The website uses React (Vite) and the mobile app uses React Native (Expo). This means:
- Component patterns are similar (JSX, hooks, state)
- Styling systems differ (CSS vs StyleSheet/inline)
- Shared logic is possible (API client, constants, validation)
- A website rewrite is NOT necessary — both are already React

---

## 2. Website Rewrite Recommendation

### Decision: NO Rewrite Necessary

| Reason | Detail |
|--------|--------|
| Website is already React | Same mental model as mobile |
| Website is production-stable | Major features working (admin, payments, platform admin) |
| Rewrite risk outweighs benefit | Would require re-testing everything |
| UI parity achievable through style alignment | Colors, typography, spacing can match without restructuring |

**The goal is visual/behavioral consistency, not code unification.**

---

## 3. UI Areas That Should Match

### Visual Identity (Shared Across Both)

| Element | Web Current | Mobile Current | Alignment Needed? |
|---------|-------------|----------------|-------------------|
| Primary color | `var(--primary)` (blue-green) | Similar teal/green | ⚠️ Verify exact values match |
| Success color | Green | Green | ✅ Likely aligned |
| Warning/error colors | Amber/red | Amber/red | ✅ Likely aligned |
| Background | Light gray/white | Light gray/white | ✅ Likely aligned |
| Font family | System sans-serif | System default (React Native) | ✅ Acceptable difference |
| Font sizes | CSS rem/px | React Native dp | ⚠️ Should feel proportional |
| Border radius | `var(--radius-md)` | Component-specific | ⚠️ Verify consistency |
| Spacing scale | CSS vars | Inline numbers | ⚠️ Document shared scale |

### Behavioral Consistency

| Behavior | Should Match? | Notes |
|----------|---------------|-------|
| Login flow appearance | ✅ Yes | Same branding/messaging |
| Error messages | ✅ Yes | Same copy/tone |
| Loading states | ✅ Yes | Spinner/skeleton style should feel similar |
| Empty states | ✅ Yes | Same messaging patterns |
| Payment status badges | ✅ Yes | Same colors (green/amber/red) and labels |
| Confirmation dialogs | ✅ Yes | Same cautious tone |
| Role-based visibility | ✅ Yes | Same features shown/hidden per role |

### Content/Copy That Must Match

| Item | Match Required? |
|------|-----------------|
| Payment status labels (Paid/Pending/Unpaid) | ✅ Yes |
| Entitlement limit messages | ✅ Yes |
| Booking status labels | ✅ Yes |
| Error messages | ✅ Yes |
| Support contact info | ✅ Yes (`support@usmissionhero.com`) |
| Business name ("Tog & Dogs") | ✅ Yes |

---

## 4. Differences That Should Remain Platform-Specific

| Element | Web | Mobile | Why Different |
|---------|-----|--------|---------------|
| Navigation | Side/top nav | Bottom tab bar | Platform convention |
| Layout density | Tables, multi-column | Single-column cards | Screen size |
| Touch targets | Standard click areas | Larger tap targets (44pt min) | Finger vs cursor |
| Platform admin routes | `/platform-admin` with full UI | Not available on mobile | Complexity/security |
| Payment generation | Full CareCard controls | Not available (web-only) | Fat-finger risk |
| Export download | CSV file download | Not available | File handling |
| Responsive behavior | Fluid/adaptive | Fixed mobile layout | Different contexts |

---

## 5. Design System Approach Recommendation

### Shared Design Tokens (Document, Not Code)

Create a shared reference document listing:

```
Colors:
  --primary: #2980b9 (or current value)
  --success: #10b981
  --warning: #f59e0b
  --error: #ef4444
  --text-primary: #1f2937
  --text-secondary: #6b7280
  --bg-muted: #f9fafb
  --border: #e5e7eb

Spacing scale:
  xs: 4px / 4dp
  sm: 8px / 8dp
  md: 16px / 16dp
  lg: 24px / 24dp
  xl: 32px / 32dp

Border radius:
  sm: 4px
  md: 8px
  lg: 12px
  full: 9999px (pill)

Badge styles:
  Paid: bg green, text white
  Pending: bg amber, text white
  Failed: bg red, text white
  Unpaid: bg gray, text white
```

### UI Parity Checklist (For Manual Review)

| # | Screen | Web | Mobile | Match? |
|---|--------|-----|--------|--------|
| 1 | Login page | Colors, logo, branding | Colors, logo, branding | ___ |
| 2 | Admin dashboard/schedule | Card styles, badges | Card styles, badges | ___ |
| 3 | Request/booking detail | CareCard layout | Detail stack | ___ |
| 4 | Payment status badges | Chip colors + labels | Badge colors + labels | ___ |
| 5 | Empty states | Messaging + icon | Messaging + icon | ___ |
| 6 | Loading states | Spinner style | Spinner style | ___ |
| 7 | Error banners | Color + copy | Color + copy | ___ |
| 8 | Staff schedule | List format | List format | ___ |
| 9 | Visit completion | Notes + button | Notes + button | ___ |
| 10 | Sandbox warning | Banner style | Banner style (if shown) | ___ |

---

## 6. App Store / TestFlight Current State

### Distribution Status

| Channel | Status | Notes |
|---------|--------|-------|
| Internal TestFlight | ✅ Active (Matthew) | Build 1.0.0 (4) |
| External TestFlight | ⏳ Apple Beta Review submitted (15J) | Ryan not invited |
| Public App Store | ❌ Not submitted | Not approved for public release |

### Before Public App Store Release

| Gate | Status | Notes |
|------|--------|-------|
| Multi-role internal validation | ✅ Done (15H) | Admin/staff/client passed |
| Apple Beta Review for external testers | ⏳ Submitted (15J) | Approval status unknown |
| Ryan external TestFlight validation | ❌ Deferred (19-series) | Paused until SaaS maturity gates pass |
| UI parity review | ⏳ This document | Planning |
| Strict tenant-resolution mode enabled | ⏳ Pending (18R/18T) | Required before multi-tenant mobile |
| Payment live mode | ❌ Blocked (EIN) | Not required for App Store per se |
| App Store metadata/screenshots | ❌ Not prepared | Needed before submission |
| Privacy policy URL in app | ✅ Present | Points to production URL |
| Full App Store Review (not beta) | ❌ Not submitted | Separate from Beta Review |

### Public App Store Publishing Approval Gates

| # | Gate | Owner |
|---|------|-------|
| 1 | UI parity acceptable | Matthew visual review |
| 2 | External tester validation complete (Ryan or equivalent) | Matthew |
| 3 | App Store metadata/screenshots prepared | AG + Matthew |
| 4 | Full App Store Review submission | Matthew explicit approval |
| 5 | No critical bugs remaining | AG assessment |
| 6 | Payment track resolved OR clearly not app-dependent | Matthew |
| 7 | Second-tenant readiness confirmed (optional) | Matthew |

---

## 7. Safe AG Follow-Up Options

| Option | Scope | Risk | Approval? |
|--------|-------|------|-----------|
| Read-only UI inventory (compare web/mobile screens) | Documentation | None | No |
| Shared design tokens document | Documentation | None | No |
| Color/spacing alignment in mobile code | Code change | Low | Standard release approval |
| Badge label/copy unification | Code change | Low | Standard release approval |
| App Store metadata/screenshot preparation | Content | None | Documentation only |
| No rewrite or structural changes | N/A | N/A | ✅ Confirmed |

---

## 8. Recommended Release Sequence

| Release | Scope | Priority |
|---------|-------|----------|
| **18UI-A** | Web/mobile UI parity review plan (this document) | ✅ Done |
| **18UI-B** | Shared design tokens reference document | Low |
| **18UI-C** | Mobile color/badge/copy alignment (code) | Low |
| **18UI-D** | App Store metadata preparation (screenshots, description) | Medium (before public submit) |
| **19A** | Second-tenant dry-run planning (after strict mode) | High |

---

## 9. What This Document Does NOT Authorize

- ❌ Code changes (web or mobile)
- ❌ Frontend deployment
- ❌ Mobile builds (EAS)
- ❌ TestFlight changes
- ❌ App Store Connect changes
- ❌ Ryan/tester additions
- ❌ Website rewrite
- ❌ AWS/Terraform changes
- ❌ Cognito/Stripe/Postmark changes
- ❌ Creating a second tenant
- ❌ Enabling strict mode
- ❌ Public App Store submission

This is a review/planning document. UI implementation requires separate approval.
