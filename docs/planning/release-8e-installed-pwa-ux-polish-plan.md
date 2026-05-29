# Release 8E: Installed PWA User Experience Polish

**Status:** Planning
**Priority:** Low-Medium (mobile UX quality while Ryan is unavailable)
**Risk to Production:** Very Low (CSS + documentation only)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Safe-area CSS, mobile audit, PWA install guide, validation checklist

---

## 1. Release Purpose

Polish the installed PWA experience for iOS and Android standalone mode. Add safe-area insets for devices with notches/home indicators, audit remaining mobile layout issues, and create user-facing documentation for installing the app.

---

## 2. Current State (After Releases 8A–8D)

| Area | Status |
|------|--------|
| Responsive layout (320px–1440px) | ✅ Validated in 8A |
| PWA installability (manifest + icons + SW) | ✅ Validated in 8C/8D |
| Manifest name/id alignment | ✅ Fixed in 8D |
| iOS safe-area insets | ❌ Not implemented |
| `viewport-fit=cover` meta tag | ❌ Not present |
| PWA install guide for users | ❌ Not created |
| Mobile/PWA validation checklist | ❌ Not formalized |

### The Safe-Area Gap

When the app runs in standalone mode on iPhones with a notch (iPhone X and later) or home indicator bar:
- Content can render behind the notch/status bar area
- Bottom navigation or action buttons can be obscured by the home indicator
- The `env(safe-area-inset-*)` CSS values solve this, but require `viewport-fit=cover` in the meta tag

This is a common PWA issue that's simple to fix with CSS.

---

## 3. Recommended Scope

### Phase 1: Safe-Area CSS (Low Risk)

| Item | Change | Risk |
|------|--------|------|
| Add `viewport-fit=cover` to viewport meta tag | `web/index.html` | Very Low |
| Add safe-area padding to app container | `web/src/App.css` | Very Low |
| Add safe-area padding to sticky header | `web/src/App.css` | Very Low |
| Add safe-area padding to footer | `web/src/App.css` | Very Low |
| Add safe-area padding to full-screen modals | `web/src/Admin.css` | Very Low |
| Add safe-area padding to admin header bar | `web/src/Admin.css` | Very Low |

### Phase 2: Documentation

| Item | Change | Risk |
|------|--------|------|
| Create PWA install guide for Ryan/clients | `docs/operations/pwa-install-guide.md` | None |
| Create mobile/PWA validation checklist | `docs/validation/mobile-pwa-validation-checklist.md` | None |

---

## 4. Safe-Area CSS Implementation Details

### 4.1 viewport-fit=cover

**File:** `web/index.html`

Change the viewport meta from:
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
```
To:
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
```

This tells the browser to extend the viewport into the safe-area regions, allowing CSS to control the padding.

### 4.2 App Container Safe-Area

**File:** `web/src/App.css`

```css
/* PWA standalone safe-area support (iOS notch/home indicator) */
.app-container {
  padding-top: env(safe-area-inset-top, 0px);
  padding-bottom: env(safe-area-inset-bottom, 0px);
  padding-left: env(safe-area-inset-left, 0px);
  padding-right: env(safe-area-inset-right, 0px);
}
```

### 4.3 Sticky Header Safe-Area

**File:** `web/src/App.css`

```css
.main-header {
  padding-top: max(16px, env(safe-area-inset-top, 16px));
  padding-left: max(24px, env(safe-area-inset-left, 24px));
  padding-right: max(24px, env(safe-area-inset-right, 24px));
}
```

At the 480px breakpoint, adjust:
```css
@media (max-width: 480px) {
  .main-header {
    padding-top: max(10px, env(safe-area-inset-top, 10px));
    padding-left: max(12px, env(safe-area-inset-left, 12px));
    padding-right: max(12px, env(safe-area-inset-right, 12px));
  }
}
```

### 4.4 Footer Safe-Area

**File:** `web/src/App.css`

```css
.main-footer {
  padding-bottom: max(32px, env(safe-area-inset-bottom, 32px));
}
```

### 4.5 Full-Screen Modal Safe-Area

**File:** `web/src/Admin.css`

In the existing `@media (max-width: 480px)` block for `.modal-content`:
```css
.modal-content {
  padding-top: max(16px, env(safe-area-inset-top, 16px));
  padding-bottom: max(16px, env(safe-area-inset-bottom, 16px));
}
```

### 4.6 Admin Header Bar Safe-Area

**File:** `web/src/Admin.css`

```css
@media (max-width: 480px) {
  .admin-header-bar {
    padding-left: max(12px, env(safe-area-inset-left, 12px));
    padding-right: max(12px, env(safe-area-inset-right, 12px));
  }
}
```

### Why `max()` Instead of Direct `env()`

Using `max(desired-padding, env(safe-area-inset-*))` ensures:
- On devices without notches: the normal padding applies (env returns 0)
- On devices with notches: the safe-area inset applies if it's larger than the normal padding
- No layout shift on non-notch devices

---

## 5. Mobile Audit Checklist (DevTools Verification)

Run through these viewports in Chrome DevTools device toolbar:

| Width | Device | Pages to Check |
|-------|--------|---------------|
| 320px | iPhone SE (1st gen) | /book, /admin, /my-bookings |
| 360px | Galaxy S series | /book, /admin |
| 375px | iPhone SE (2nd/3rd gen), iPhone 6/7/8 | All pages |
| 390px | iPhone 12/13/14 | All pages |
| 414px | iPhone 6/7/8 Plus | /admin, /book |
| 430px | iPhone 14 Pro Max | /admin, /book |
| 768px | iPad Mini / tablet | /admin (sidebar behavior) |

For each viewport, check:
- [ ] No horizontal overflow (no horizontal scrollbar)
- [ ] Text is readable (min 14px body text)
- [ ] Touch targets are ≥44px
- [ ] Modals don't overflow viewport
- [ ] Date picker grid fits without scrollbar
- [ ] Action dropdowns don't clip off-screen
- [ ] Status badges are visible and not truncated

---

## 6. PWA Install Guide (User-Facing)

**File:** `docs/operations/pwa-install-guide.md`

Content outline:

### For iPhone (iOS Safari)
1. Open Safari and navigate to `toganddogs.usmissionhero.com`
2. Tap the **Share** button (square with arrow) at the bottom of the screen
3. Scroll down and tap **"Add to Home Screen"**
4. Confirm the name "Tog & Dogs" and tap **Add**
5. The app icon will appear on your home screen
6. Tap it to open the portal in full-screen mode (no browser bars)

### For Android (Chrome)
1. Open Chrome and navigate to `toganddogs.usmissionhero.com`
2. Chrome may show an **"Install app"** banner at the bottom — tap **Install**
3. If no banner appears: tap the **three-dot menu** (⋮) → **"Install app"** or **"Add to Home screen"**
4. Confirm and tap **Install**
5. The app icon will appear on your home screen and in your app drawer
6. Tap it to open the portal in full-screen mode

### Notes
- The app requires an internet connection to work
- All your bookings, client data, and scheduling are live — same as the website
- If you need to update the app, simply close and reopen it — updates happen automatically

---

## 7. Mobile/PWA Validation Checklist

**File:** `docs/validation/mobile-pwa-validation-checklist.md`

A repeatable checklist for validating the installed PWA experience after deployments:

1. **Install on Android** — Chrome install prompt works
2. **Install on iOS** — Share → Add to Home Screen works
3. **Standalone mode** — no browser chrome visible
4. **Safe-area** — content not obscured by notch or home indicator
5. **Navigation** — all routes work from home screen launch
6. **Back gesture** — iOS swipe-back and Android back button work
7. **Orientation** — portrait and landscape both render correctly
8. **No stale cache** — fresh content loads on every open
9. **Theme color** — status bar shows brand gold
10. **Icon quality** — not blurry or pixelated on home screen

---

## 8. Files Affected

| File | Change | New? |
|------|--------|------|
| `web/index.html` | Add `viewport-fit=cover` to viewport meta | Modified |
| `web/src/App.css` | Add safe-area padding to container, header, footer | Modified |
| `web/src/Admin.css` | Add safe-area padding to modal and admin header (mobile) | Modified |
| `docs/operations/pwa-install-guide.md` | User-facing install instructions | ✅ New |
| `docs/validation/mobile-pwa-validation-checklist.md` | Repeatable PWA test checklist | ✅ New |

### Files NOT Changed

- No `.jsx` component files
- No `manifest.webmanifest` or `sw.js`
- No `package.json` or `vite.config.js`
- No backend files
- No Terraform
- No icons

---

## 9. Acceptance Criteria

- [ ] `viewport-fit=cover` added to viewport meta tag
- [ ] Safe-area CSS applied to app container, header, footer, and modals
- [ ] No layout regression on non-notch devices (env() returns 0, `max()` preserves normal padding)
- [ ] `npm run build` passes
- [ ] PWA install guide created with iPhone and Android instructions
- [ ] Mobile/PWA validation checklist created
- [ ] No horizontal overflow at any tested viewport width
- [ ] No backend, Terraform, or infrastructure changes

---

## 10. Validation Plan

### Build Validation
```bash
npm run build  # in web/
```

### DevTools Viewport Testing
- Test at 375px (iPhone SE) with "Show device frame" enabled
- Test at 390px (iPhone 14) with notch simulation
- Verify safe-area padding appears in computed styles when device frame has notch
- Verify no padding change on desktop (1440px)

### Real Device Testing (If Available)
- Install PWA on iPhone with notch → verify content doesn't go behind status bar
- Install PWA on Android → verify install prompt and standalone mode
- Verify footer isn't hidden behind iOS home indicator

---

## 11. Risks and Rollback

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| `viewport-fit=cover` causes layout shift on some browsers | Very Low | Low | `env()` with fallback 0px; `max()` preserves existing padding |
| Safe-area padding adds unwanted space on non-notch devices | None | — | `env(safe-area-inset-*, 0px)` returns 0 on non-notch devices |
| CSS changes break desktop layout | Very Low | Low | Safe-area values are 0 on desktop; `max()` preserves existing values |

**Rollback:** Revert `index.html` viewport meta and remove safe-area CSS lines. Redeploy. Instant.

---

## 12. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8E: Installed PWA User Experience Polish.

CSS + documentation only. No component logic changes, no backend changes.

=== 1. Update web/index.html ===

Change the viewport meta tag from:
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
To:
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />

=== 2. Update web/src/App.css ===

Add at the TOP of the file (before .app-container):

/* PWA Standalone Safe-Area Support (iOS notch/home indicator) */

Then modify .app-container to add:
  padding-top: env(safe-area-inset-top, 0px);
  padding-bottom: env(safe-area-inset-bottom, 0px);
  padding-left: env(safe-area-inset-left, 0px);
  padding-right: env(safe-area-inset-right, 0px);

Modify .main-header to change padding to:
  padding-top: max(16px, env(safe-area-inset-top, 16px));
  padding-left: max(24px, env(safe-area-inset-left, 24px));
  padding-right: max(24px, env(safe-area-inset-right, 24px));

Add to .main-footer:
  padding-bottom: max(32px, env(safe-area-inset-bottom, 32px));

In the existing @media (max-width: 480px) block, update .main-header:
  padding-top: max(10px, env(safe-area-inset-top, 10px));
  padding-left: max(12px, env(safe-area-inset-left, 12px));
  padding-right: max(12px, env(safe-area-inset-right, 12px));

=== 3. Update web/src/Admin.css ===

In the existing @media (max-width: 480px) block, add to .modal-content:
  padding-top: max(16px, env(safe-area-inset-top, 16px));
  padding-bottom: max(16px, env(safe-area-inset-bottom, 16px));

In the same breakpoint, add to .admin-header-bar:
  padding-left: max(12px, env(safe-area-inset-left, 12px));
  padding-right: max(12px, env(safe-area-inset-right, 12px));

=== 4. Create docs/operations/pwa-install-guide.md ===

Title: "Installing Tog & Dogs on Your Phone"
Last Updated: Release 8E
Audience: Ryan, Staff, Clients

Sections:
- For iPhone (iOS Safari): Share → Add to Home Screen (step-by-step with descriptions)
- For Android (Chrome): Install banner or menu → Install app (step-by-step)
- Notes: requires internet, updates automatically, same data as website

Keep language simple and non-technical. Include emoji for visual cues.

=== 5. Create docs/validation/mobile-pwa-validation-checklist.md ===

Title: "Mobile PWA Validation Checklist"
Last Updated: Release 8E

A repeatable 10-item checklist:
1. Install on Android Chrome
2. Install on iOS Safari
3. Standalone mode (no browser chrome)
4. Safe-area (content not behind notch/home indicator)
5. All routes work from home screen launch
6. Back gesture works (iOS swipe, Android button)
7. Portrait and landscape render correctly
8. No stale cache (fresh content on reopen)
9. Theme color on status bar
10. Icon quality on home screen

=== 6. Validation ===

Run: npm run build (in web/)
Confirm no errors.
Test in Chrome DevTools at 390px with iPhone 14 frame (has notch).
Verify safe-area padding appears in computed styles.
Verify no layout change at 1440px desktop.
Do NOT deploy.

Return: files changed, build result, viewport test observations.
```

---

## 13. Commit Command (After Approval)

```bash
git add web/index.html web/src/App.css web/src/Admin.css docs/operations/pwa-install-guide.md docs/validation/mobile-pwa-validation-checklist.md docs/planning/release-8e-installed-pwa-ux-polish-plan.md
git commit -m "feat: Release 8E — PWA safe-area CSS, install guide, and mobile validation checklist"
```
