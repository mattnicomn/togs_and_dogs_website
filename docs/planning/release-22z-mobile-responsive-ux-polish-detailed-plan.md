# Release 22Z: Mobile Responsive UX Polish Detailed Plan

**Status:** Planning
**Date:** 2026-07-12
**Priority:** High (user-reported mobile usability issues from production testing)
**Scope:** Implementation-ready responsive design plan for web application mobile experience
**Baseline:** Production Release 22V (bundle `index-CZXrWtrt.js`), docs commit `fda05e3`

---

## 1. Problem Summary

Matthew tested the production web app from an iPhone and identified multiple mobile usability issues:

| Issue | Area | Severity |
|-------|------|----------|
| Admin tabs crowded/offscreen | Navigation | High |
| Two competing navigation layers visible | Header/Nav | High |
| Horizontal scrollbar on Profile Editor | Profile Editor | High |
| Profile Editor content wider than viewport | Profile Editor | High |
| Excessive spacing and oversized typography | Dashboard/Editor | Medium |
| Dashboard cards consume too much vertical space | Admin Dashboard | Medium |
| Checkbox/label misaligned vertically | Profile Editor | Medium |
| Navigation labels wrap awkwardly | Navigation | Medium |
| Header hierarchy confusing on small screens | Navigation | Medium |

---

## 2. Mobile UX Principles

| Principle | Rule |
|-----------|------|
| No horizontal page scroll | No element should cause viewport overflow |
| Touch-first sizing | All interactive targets ≥ 44px (iOS) / 48px (Android) minimum |
| Progressive disclosure | Show essential navigation; collapse secondary into menus |
| Content-first | Reduce chrome, maximize content area on small screens |
| Familiar patterns | Use native-feeling gestures and mobile conventions |
| Graceful degradation | Desktop experience remains unchanged at desktop widths |
| Accessibility | WCAG 2.1 AA minimum for contrast, focus, semantics |
| Safe areas | Respect iOS notch/home indicator via `env(safe-area-inset-*)` |
| Performance | No heavy JS layout recalculations; prefer CSS-only responsive |

---

## 3. Breakpoint Strategy

### Recommended Breakpoints

| Token | Range | Target |
|-------|-------|--------|
| `$bp-xs` | 0–374px | Small phones (iPhone SE, older devices) |
| `$bp-sm` | 375–429px | Standard phones (iPhone 14/15, Pixel) |
| `$bp-md` | 430–767px | Large phones, small tablets |
| `$bp-lg` | 768–1023px | Tablets (iPad portrait) |
| `$bp-xl` | 1024px+ | Desktop (no changes needed) |

### Implementation Approach

```css
/* Mobile-first: base styles target smallest screens */
/* Then layer up with min-width queries */

/* Standard phone */
@media (min-width: 375px) { ... }

/* Large phone / small tablet */
@media (min-width: 430px) { ... }

/* Tablet */
@media (min-width: 768px) { ... }

/* Desktop (existing styles preserved) */
@media (min-width: 1024px) { ... }
```

### Key Decision: Mobile-First vs Desktop-First

**Recommendation: Additive mobile overrides (desktop-first with targeted mobile fixes)**

Rationale: The existing codebase is desktop-first. A full mobile-first rewrite is too risky. Instead, add targeted `max-width` media queries for mobile-specific overrides while preserving all existing desktop behavior.

```css
/* Safer approach for existing codebase */
@media (max-width: 767px) { /* phone overrides */ }
@media (max-width: 1023px) { /* tablet overrides */ }
```

---

## 4. Global Responsive Foundation

### A. Overflow Prevention

```css
/* Apply globally */
html, body {
  overflow-x: hidden;
  width: 100%;
}

*, *::before, *::after {
  box-sizing: border-box;
}

/* Prevent fixed-width elements from causing overflow */
img, video, canvas, svg {
  max-width: 100%;
  height: auto;
}

/* Prevent long strings from breaking layout */
.truncate-safe {
  overflow-wrap: break-word;
  word-break: break-word;
  min-width: 0;
}
```

### B. Mobile Typography Scale

| Element | Desktop | Mobile (≤767px) |
|---------|---------|-----------------|
| Page title (h1) | 24–28px | 20–22px |
| Section heading (h2) | 20–22px | 17–18px |
| Card title (h3) | 16–18px | 15–16px |
| Body text | 14–16px | 14px (minimum) |
| Small/caption | 12–13px | 12px (minimum readable) |
| Button text | 14–16px | 14–15px |

### C. Mobile Spacing Scale

| Usage | Desktop | Mobile (≤767px) |
|-------|---------|-----------------|
| Section gap | 24–32px | 16–20px |
| Card padding | 16–24px | 12–16px |
| Form field gap | 16–20px | 12–14px |
| Button padding | 12px 24px | 12px 16px |
| Page margin | 24–32px | 12–16px |

### D. Touch Target Minimums

| Element | Minimum Size | Minimum Spacing |
|---------|-------------|-----------------|
| Buttons | 44px height | 8px between |
| Links (navigation) | 44px tap area | 8px between |
| Checkboxes/radios | 44px tap area (including label) | — |
| Input fields | 44px height | — |
| Action menu items | 44px row height | — |
| Close/dismiss buttons | 44px × 44px | — |

### E. iOS Safe Areas

```css
/* For fixed headers/footers */
.mobile-header {
  padding-top: env(safe-area-inset-top);
}

.mobile-footer {
  padding-bottom: env(safe-area-inset-bottom);
}

/* For full-screen panels */
.full-screen-panel {
  padding-left: env(safe-area-inset-left);
  padding-right: env(safe-area-inset-right);
}
```

---

## 5. Component-by-Component Plan

### B. Main Application Header/Navigation

**Current Problem:** Desktop navigation displays all items simultaneously — Portal, My Bookings, Platform Admin, Request Care, theme toggle, account dropdown, plus admin section tabs all visible and competing for space.

**Recommended Pattern: Hamburger/Drawer Navigation**

```
┌─────────────────────────────────────┐
│ [☰]  Tog & Dogs          [👤] [🌙] │  ← Compact header
├─────────────────────────────────────┤
│ [Tab content area]                  │  ← Full-width content
└─────────────────────────────────────┘

Hamburger menu (slide-in drawer):
┌────────────────────┐
│ Navigation         │
│ ─────────────────  │
│ Dashboard          │
│ Request List       │
│ Staff Management   │
│ Client Management  │
│ Scheduler          │
│ ─────────────────  │
│ Platform Admin     │
│ Request Care       │
│ My Bookings        │
│ ─────────────────  │
│ Account            │
│ Sign Out           │
└────────────────────┘
```

**Requirements:**
- Visible on screens ≤ 767px
- Desktop navigation unchanged at ≥ 1024px
- Tablet (768–1023px): evaluate whether tabs still fit; use scrollable strip if yes
- Active section clearly indicated in both menu and header
- Menu closes on navigation and on backdrop tap
- Accessible: `aria-expanded`, `aria-controls`, focus trap when open
- No essential actions hidden (sign out, account always reachable)
- Smooth open/close transition (CSS transform, not JS layout thrash)

### C. Admin Section Navigation (Tabs)

**Current Problem:** Scheduler, Request List, Staff Management, Client Management tabs attempt to fit horizontally on phone screens, causing wrap and overflow.

**Recommended Mobile Pattern: Horizontally Scrollable Tab Strip**

```
┌─────────────────────────────────────┐
│ ← [Scheduler] [Request List] [Sta… │  ← Scroll indicator
└─────────────────────────────────────┘
```

**Requirements:**
- `overflow-x: auto` with `-webkit-overflow-scrolling: touch`
- No wrapping (`white-space: nowrap` on tab container)
- Active tab visible on mount (scroll into view)
- Scroll indicators (fade/gradient) on edges if content overflows
- Tab items: minimum 44px height, adequate horizontal padding
- Desktop: existing tab layout unchanged
- Alternative (if scrollable tabs feel awkward): dropdown/select for section switching on very small screens (< 375px)

### D. Admin Dashboard Cards

**Current Problem:** Intake Queue, Needs Assignment, Scheduled Visits cards are full-width and oversized on mobile, causing excessive vertical scrolling.

**Recommended Mobile Layout:**

| Width | Layout |
|-------|--------|
| < 430px | Single column, compact cards (reduced padding/type) |
| 430–767px | Optional 2-column compact grid |
| ≥ 768px | Existing desktop layout |

**Card Mobile Spec:**
- Padding: 12px
- Title: 15px semibold
- Metric value: 20px bold (down from ~28px desktop)
- Metric label: 12px
- Card gap: 8–12px
- Border-radius: 8px
- No drop shadow on mobile (performance)
- Minimum height: auto (content-driven, not fixed)

### E. Profile Editor Mobile Experience

**Current Problem:** Right-side drawer is too narrow and cramped on mobile. Content overflows horizontally. Fields, checkboxes, and labels are misaligned. Excessive spacing wastes screen space.

**Recommended Mobile Pattern: Full-Screen Sheet**

| Width | Behavior |
|-------|----------|
| < 768px | Full-screen editor (covers entire viewport) |
| ≥ 768px | Right-side drawer (existing behavior, preserved) |

**Full-Screen Mobile Editor Spec:**

```
┌─────────────────────────────────────┐
│ [←] Edit Staff Profile        [✕]  │  ← Sticky header
├─────────────────────────────────────┤
│                                     │
│ Profile Details                     │  ← Scrollable content
│ ┌─────────────────────────────────┐ │
│ │ Display Name                    │ │
│ │ [Ryan York                    ] │ │
│ │                                 │ │
│ │ Email (read-only)               │ │
│ │ ryan@example.com                │ │
│ │                                 │ │
│ │ ☑ Can be assigned to jobs       │ │  ← Inline checkbox+label
│ └─────────────────────────────────┘ │
│                                     │
│ Login Identity                      │
│ ...                                 │
│                                     │
├─────────────────────────────────────┤
│ [Cancel]              [Save Changes]│  ← Sticky footer
└─────────────────────────────────────┘
```

**Requirements:**
- Full viewport width and height on mobile
- `position: fixed; inset: 0;` (same pattern as 22S portal fix)
- Sticky header: back arrow, profile name, close button
- Sticky footer: Cancel + Save buttons (always visible without scrolling to bottom)
- Internal vertical scroll for section content
- No horizontal scrollbar
- All form inputs: `width: 100%`, minimum 44px height
- Checkbox + label on same horizontal row: `display: flex; align-items: center; gap: 8px;`
- Section headings: 16–17px, reduced bottom margin
- Field labels: 12–13px
- Compact vertical spacing between fields: 12–14px
- Protected/orphaned warning banners: full-width, reduced padding, readable text
- Danger Zone: preserved at bottom, separated visually
- Unsaved-change guard: preserved (modal confirmation on close)
- Protected-admin guardrails: preserved (no delete/disable/unlink for protected accounts)
- Body scroll lock: maintained (22S pattern)

### F. Mobile Forms and Content Widths

**Global form field rules for mobile:**

```css
@media (max-width: 767px) {
  input, select, textarea, button {
    width: 100%;
    max-width: 100%;
    min-width: 0;
    font-size: 16px; /* Prevents iOS zoom on focus */
    height: 44px; /* Touch-friendly */
  }

  textarea {
    height: auto;
    min-height: 88px;
  }

  /* Prevent long values from expanding containers */
  input[type="email"],
  input[type="text"],
  input[type="url"] {
    text-overflow: ellipsis;
    overflow: hidden;
  }
}
```

**Key rules:**
- No element uses a fixed pixel width that exceeds mobile viewport
- All containers: `max-width: 100%`
- Long email addresses / names: ellipsis or word-break
- Select controls: full-width, native mobile picker preferred
- No desktop min-width values on mobile

### G. Request List and Data-Heavy Views

**Current Problem:** Table/list rows designed for desktop don't adapt to narrow screens.

**Recommended Mobile Pattern: Card-Based Layout**

```
┌─────────────────────────────────────┐
│ Joey Rockwell                       │
│ Overnight · Sep 15–18               │
│ Status: [Approved ✓]               │
│ Staff: Ryan York                    │
│                            [⋮ More] │
└─────────────────────────────────────┘
```

**Requirements:**
- < 768px: card layout (stacked fields, one card per row)
- ≥ 768px: existing table/list layout preserved
- Card shows: client name, service, dates, status badge, assigned staff
- Action menu: "⋮" kebab button (44px touch target)
- Filters/tabs: horizontally scrollable strip (same as admin tabs)
- Status badges: compact pills
- Multi-day labels: "Sep 15–18" with day count if space allows
- Visit windows: truncate to first + "+N more" if multiple

### H. Scheduler and Client Management

**Scheduler mobile:**
- Date picker: full-width, native date input or compact calendar widget
- Day/week view: scrollable horizontally within container (not page)
- Event cards: compact, single-line summary
- No page-level horizontal scroll

**Client Management mobile:**
- Client cards: single column, compact
- Pet info: collapsed by default, expandable
- Action menus: kebab button
- Search/filter: full-width input at top

### I. Platform Admin

**Mobile adjustments:**
- Tenant list: single-column card layout
- Tenant detail: stacked sections (not side-by-side)
- Audit log: compact timeline format
- Navigation: included in hamburger menu
- No tenant behavior, count, or configuration changes

### J. Public Pages (/book, /my-bookings, /privacy, /terms)

**Care request form (/book):**
- Already validated in 22D/22E for UX
- Ensure step navigation is touch-friendly
- All inputs full-width on mobile
- Date pickers use native mobile controls

**My Bookings (/my-bookings):**
- Already fixed in 22U/22V for date/window display
- Cards should use compact mobile layout
- Status badges: inline pills

**Privacy/Terms:**
- Content pages: ensure max-width, readable line length, adequate padding

---

## 6. Accessibility and Usability Requirements

| Requirement | Implementation |
|-------------|---------------|
| Touch target minimum | 44px × 44px (interactive elements) |
| Focus visibility | Visible focus ring on all interactive elements |
| Semantic navigation | `<nav>`, `<main>`, `<aside>`, landmark roles |
| Reduced motion | `@media (prefers-reduced-motion: reduce)` — disable transitions |
| No hover-only controls | All hover interactions also accessible via tap/focus |
| Sufficient contrast | 4.5:1 minimum for text, 3:1 for large text (WCAG AA) |
| Readable font size | Minimum 14px body text, 12px captions |
| Screen reader labels | `aria-label` on icon-only buttons (hamburger, close, kebab) |
| Skip navigation | Skip-to-content link for keyboard users |
| Focus trap | In open menus/drawers, focus cycles within |

---

## 7. Validation Matrix

### Device/Width Test Matrix

| Width | Device Example | Must Test |
|-------|---------------|:---------:|
| 320 × 568 | iPhone SE (1st gen) | ✅ |
| 375 × 667 | iPhone 8 / SE (2nd gen) | ✅ |
| 390 × 844 | iPhone 14 | ✅ |
| 414 × 896 | iPhone 11 Pro Max | ✅ |
| 430 × 932 | iPhone 15 Pro Max | ✅ |
| 768 × 1024 | iPad portrait | ✅ |
| 1024 × 768 | iPad landscape / small desktop | ✅ (regression) |
| 1440 × 900 | Desktop | ✅ (regression) |

### Page/Feature Validation Checklist

| # | Page/Feature | No H-Scroll | Nav Usable | Content Readable | Touch Targets OK | Pass/Fail |
|---|-------------|:-:|:-:|:-:|:-:|:-:|
| 1 | `/` (homepage) | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 2 | `/book` (intake form) | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 3 | `/my-bookings` | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 4 | `/admin` (dashboard) | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 5 | `/admin` → Request List | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 6 | `/admin` → Staff Management | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 7 | `/admin` → Profile Editor | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 8 | `/admin` → Client Management | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 9 | `/admin` → Scheduler | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 10 | `/platform-admin` | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 11 | `/privacy` | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 12 | `/terms` | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

### Regression Checks (Desktop Must Not Break)

| # | Check | Status |
|---|-------|--------|
| 1 | Desktop admin dashboard layout unchanged | ⬜ |
| 2 | Desktop Profile Editor drawer width/position unchanged | ⬜ |
| 3 | Desktop tabs layout unchanged | ⬜ |
| 4 | Desktop request list/table layout unchanged | ⬜ |
| 5 | Desktop typography/spacing unchanged | ⬜ |
| 6 | All existing 22V functionality preserved | ⬜ |

---

## 8. Regression Risks

| Risk | Mitigation |
|------|------------|
| Desktop layout breaks from mobile CSS | Use scoped `max-width` media queries; never modify styles outside query |
| Drawer behavior regresses | Mobile uses full-screen sheet; desktop path preserved via breakpoint guard |
| Navigation becomes inaccessible | Test with keyboard and screen reader after changes |
| iOS-specific rendering issues | Test on real iPhone (not just browser DevTools) |
| Performance impact from new CSS | Avoid JavaScript-driven layout; prefer CSS media queries and flexbox/grid |
| Z-index conflicts | Document z-index layers; test drawer/menu/overlay stacking |

---

## 9. Rollback Considerations

| Scenario | Rollback Approach |
|----------|-------------------|
| Mobile CSS causes desktop regression | Revert the specific CSS file change; redeploy previous bundle |
| Navigation refactor breaks functionality | Feature-flag the mobile nav behind a breakpoint; revert to desktop nav |
| Profile Editor full-screen causes issues | Conditionally render: check `window.innerWidth` or media query in JS |
| Broad regression across pages | Revert entire commit; rebuild from previous passing bundle |

All changes should be purely CSS/JSX layout changes. No backend, API, or data changes means rollback is a simple frontend redeploy.

---

## 10. Phased Implementation Release Sequence

**Recommendation: Phased implementation (4 phases + validation)**

The scope is large enough that a single implementation release is risky. Phased delivery allows validation between each step and limits blast radius.

| Phase | Release | Scope | Risk | Effort |
|-------|---------|-------|------|--------|
| 1 | 22ZA | Global responsive foundation + mobile navigation | Medium | Medium |
| 2 | 22ZB | Profile Editor full-screen mobile layout | Medium | Medium |
| 3 | 22ZC | Dashboard cards + Request List mobile layout | Low-Medium | Medium |
| 4 | 22ZD | Scheduler, Client Management, Platform Admin polish | Low | Medium |
| 5 | 22ZE | Cross-device validation and production readiness | Low | Low |

### Phase 1 — 22ZA: Responsive Foundation and Navigation

**Scope:**
- Add global overflow prevention (`box-sizing`, `max-width: 100%`, `overflow-x: hidden`)
- Add mobile typography and spacing scale CSS variables
- Implement hamburger/drawer mobile navigation (< 768px)
- Implement scrollable tab strip for admin section tabs
- Hide desktop navigation on mobile; show hamburger
- Preserve desktop navigation at ≥ 1024px

**Acceptance criteria:**
- No horizontal scrollbar on any page at 375px width
- Hamburger menu opens/closes smoothly
- All navigation items accessible from menu
- Admin tabs scroll horizontally without page overflow
- Desktop layout unchanged at 1440px

### Phase 2 — 22ZB: Profile Editor Mobile Layout

**Scope:**
- Profile Editor renders as full-screen sheet on < 768px
- Sticky header with back/close + profile name
- Sticky footer with Cancel/Save
- Internal scroll for sections
- Compact field spacing and typography
- Checkbox + label on one row
- All inputs full-width, 44px minimum height
- 16px font-size on inputs (prevent iOS zoom)
- Warning banners (orphaned/protected) remain visible

**Acceptance criteria:**
- Profile Editor: no horizontal scrollbar at 320px
- Checkbox and label appear on same line
- Sticky header/footer don't cover content
- All sections scrollable
- Unsaved-change guard works
- Protected-admin guardrails preserved

### Phase 3 — 22ZC: Dashboard Cards and Request List

**Scope:**
- Dashboard metric cards: compact single-column on phone, optional 2-col on 430px+
- Request List: card-based layout on < 768px
- Status badges: compact pills
- Action menus: kebab button pattern
- Filter tabs: scrollable strip (from 22ZA foundation)

**Acceptance criteria:**
- Dashboard cards readable without excessive scrolling
- Request List cards show essential info (name, service, date, status)
- Actions accessible via kebab menu
- No overlapping elements

### Phase 4 — 22ZD: Scheduler, Client Management, Platform Admin

**Scope:**
- Scheduler: scrollable within container, compact event cards
- Client Management: single-column cards, expandable pet info
- Platform Admin: single-column tenant cards, compact audit timeline
- All remaining pages pass validation matrix

**Acceptance criteria:**
- All 12 pages pass validation matrix at all test widths
- No horizontal scroll on any page
- All interactive elements meet 44px touch target

### Phase 5 — 22ZE: Cross-Device Validation and Production Readiness

**Scope:**
- Full validation matrix execution at all 8 widths
- Desktop regression verification
- Real-device testing (iPhone + iPad if available)
- Bug fix pass for any issues found
- Final production deployment approval

**Acceptance criteria:**
- All checks in validation matrix pass
- Desktop regression checks pass
- No new horizontal scrollbar on any page
- Navigation usable with one hand on phone

---

## 11. Screenshots Policy

- ❌ Do NOT commit screenshots to the repository
- ✅ Screenshots may be taken locally for reference during development
- ✅ Screenshots may be shared in chat/communication for validation
- ✅ Describe visual issues in text when documenting defects

---

## 12. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Deployment
- ❌ Terraform/AWS changes
- ❌ DynamoDB writes
- ❌ Cognito/identity/profile changes
- ❌ Email/password/invite actions
- ❌ Stripe/payment changes
- ❌ Google Calendar reconnect/disconnect/token changes
- ❌ Mobile Expo/TestFlight/App Store/Google Play changes
- ❌ Tenant behavior, count, or configuration changes
- ❌ Protected-admin deletion/disable/unlink capability
- ❌ Backend behavior changes
- ❌ Ryan/tester changes
- ❌ 22Y remediation items (password-reset, calendar disconnect, protected-admin policy)

This is an implementation-ready design document. AG implementation (22ZA) requires separate approval.
