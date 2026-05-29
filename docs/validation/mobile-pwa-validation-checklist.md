# Mobile PWA Validation Checklist

**Last Updated:** Release 8E  
**Purpose:** Repeatable checklist for validating the installed PWA experience after deployments.

---

## Prerequisites

- Access to an Android device or Chrome DevTools mobile emulation
- Access to an iPhone or iOS Safari (for iOS-specific checks)
- The portal deployed at `toganddogs.usmissionhero.com`

---

## Checklist

### Installation

- [ ] **Android Chrome install:** Open site in Chrome → "Install app" option appears in menu or banner → installs successfully
- [ ] **iOS Safari install:** Open site in Safari → Share → "Add to Home Screen" → icon appears on home screen

### Standalone Mode

- [ ] **No browser chrome (Android):** Launch from home screen → no URL bar, no Chrome UI visible
- [ ] **No browser chrome (iOS):** Launch from home screen → no Safari bar visible
- [ ] **Theme color:** Status bar shows brand gold (#c28b1e) on Android
- [ ] **iOS status bar:** Default style (dark text on light background), not obscured

### Safe-Area (Notch/Home Indicator)

- [ ] **Top safe-area:** Content is not hidden behind the notch or status bar on iPhone X+
- [ ] **Bottom safe-area:** Footer and bottom buttons are not hidden behind the iOS home indicator
- [ ] **Landscape safe-area:** Side insets apply correctly if device is rotated (left/right notch area)

### Navigation

- [ ] **Home route (`/`):** Renders correctly when launched from home screen
- [ ] **Public booking (`/book`):** Renders correctly, date picker usable
- [ ] **Terms (`/terms`):** Renders correctly, scrollable
- [ ] **Privacy (`/privacy`):** Renders correctly, scrollable
- [ ] **Admin (`/admin`):** Login or dashboard renders correctly
- [ ] **Client portal (`/my-bookings`):** Login or bookings render correctly
- [ ] **Back gesture (iOS):** Swipe-back navigates to previous route (not exit app)
- [ ] **Back button (Android):** Hardware/gesture back navigates to previous route

### Content Freshness

- [ ] **No stale cache:** Close app → reopen → content is fresh from network
- [ ] **After deployment:** New content appears immediately without manual cache clear
- [ ] **Cache Storage empty:** DevTools → Application → Cache Storage shows 0 entries

### Visual Quality

- [ ] **Icon quality:** Home screen icon is crisp, not blurry or pixelated
- [ ] **Icon shape (Android):** Maskable icon renders correctly in adaptive icon shape
- [ ] **App name:** Shows "Tog & Dogs" under the icon (not truncated)
- [ ] **No horizontal overflow:** No horizontal scrollbar on any page at any viewport width

### Viewport Widths (DevTools)

Test the following pages at each width — confirm no overflow, readable text, usable controls:

| Width | Device Reference | Pages |
|-------|-----------------|-------|
| 320px | iPhone SE (1st gen) | /book, /admin |
| 375px | iPhone SE (2nd/3rd gen) | All pages |
| 390px | iPhone 12/13/14 | All pages |
| 430px | iPhone 14 Pro Max | /admin, /book |
| 768px | iPad Mini | /admin (sidebar) |

---

## Pass/Fail Summary

| Area | Status | Notes |
|------|--------|-------|
| Installation | | |
| Standalone mode | | |
| Safe-area | | |
| Navigation | | |
| Content freshness | | |
| Visual quality | | |
| Viewport widths | | |

---

## When to Run This Checklist

- After any frontend deployment that modifies CSS, layout, or PWA assets
- After manifest or service worker changes
- Before closing any mobile-related release
- During Ryan's production trial (first install)
