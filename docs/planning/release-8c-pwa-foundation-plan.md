# Release 8C: PWA Foundation

**Status:** Planning
**Priority:** Low-Medium (mobile UX improvement, not blocking operations)
**Risk to Production:** Very Low (static asset additions only)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Add web app manifest + icons for PWA installability. Defer service worker.

---

## 1. Release Purpose

Make the Tog & Dogs Operations Portal installable as a Progressive Web App so that Ryan, staff, and clients can add it to their phone's home screen and use it in a full-screen, app-like mode — without browser chrome, without building a separate native app.

This is **Phase 1: Installability only.** No service worker, no offline caching, no push notifications. Those are separate future phases.

---

## 2. Current Mobile State (After 8A/8B)

| Area | Status |
|------|--------|
| Responsive layout on all screens | ✅ Validated at 320px–1440px |
| Touch targets (44px minimum) | ✅ Enforced at ≤480px |
| Full-screen modals on mobile | ✅ Working |
| Mobile scheduler list view | ✅ Working |
| Client Portal mobile cards | ✅ Working |
| DatePickerGrid at narrow viewports | ✅ Scaled to 30px cells at ≤360px |
| PWA manifest | ❌ Not present |
| App icons (192px, 512px) | ❌ Not present |
| Service worker | ❌ Not present |
| "Add to Home Screen" capability | ❌ Not available |
| Standalone display mode | ❌ Not available |

---

## 3. Recommended Scope: Manifest-Only PWA (No Service Worker)

### Why Manifest-Only First

| Approach | Installability | Offline | Stale Cache Risk | Complexity |
|----------|---------------|---------|------------------|------------|
| **Manifest only (recommended)** | ✅ Yes | ❌ No | None | Very Low |
| Manifest + service worker | ✅ Yes | ✅ Yes | ⚠️ Medium | Medium |
| `vite-plugin-pwa` | ✅ Yes | ✅ Yes | ⚠️ Medium | Medium |

**Recommendation: Plain manifest-only PWA for Phase 1.**

Reasoning:
- A `manifest.webmanifest` file alone is sufficient for "Add to Home Screen" on both Android and iOS
- No service worker means **zero risk of stale cached content** in production
- No new npm dependency needed (`vite-plugin-pwa` is unnecessary for installability alone)
- The app requires network for all operations (DynamoDB, Cognito, Postmark) — offline caching adds complexity without real value
- Service worker can be added in a future Phase 2 if offline shell caching is desired

### What Manifest-Only Gives You

| Feature | Android Chrome | iOS Safari |
|---------|---------------|------------|
| "Add to Home Screen" prompt | ✅ Automatic (meets criteria) | ✅ Manual (Share → Add to Home Screen) |
| Full-screen standalone mode | ✅ Yes | ✅ Yes |
| Custom app icon on home screen | ✅ Yes | ✅ Yes |
| Custom splash/theme color | ✅ Yes | ✅ Yes (status bar color) |
| No browser chrome (URL bar hidden) | ✅ Yes | ✅ Yes |
| Offline support | ❌ No | ❌ No |
| Push notifications | ❌ No | ❌ No |

### Chrome Install Criteria (Manifest-Only)

For Chrome to show the install prompt, the app needs:
1. ✅ Served over HTTPS (CloudFront provides this)
2. ✅ Has a web app manifest with `name`, `icons`, `start_url`, `display`
3. ⚠️ Has a service worker with a `fetch` handler — **Chrome requires this for the automatic install banner**

**Important nuance:** Chrome's automatic "Install App" banner requires a service worker. However:
- Users can still manually install via Chrome menu → "Install app" or "Add to Home Screen"
- iOS Safari doesn't require a service worker at all
- We can add a minimal no-op service worker (just a fetch passthrough) to trigger Chrome's banner without any caching behavior

### Recommendation: Include a Minimal No-Op Service Worker

A 3-line service worker that does nothing except satisfy Chrome's installability check:

```javascript
// sw.js — minimal no-op service worker for PWA installability
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});
```

This:
- Triggers Chrome's automatic install banner ✅
- Does NOT cache anything ✅
- Does NOT cause stale content ✅
- Can be upgraded to a caching worker later ✅
- Is 3 lines of code with zero risk ✅

---

## 4. Explicitly Deferred (Phase 2+)

| Item | Reason | When |
|------|--------|------|
| Workbox/caching service worker | Stale cache risk; app requires network | After Ryan validates PWA experience |
| `vite-plugin-pwa` dependency | Unnecessary for manifest-only; adds build complexity | Only if caching is needed |
| Offline shell caching | App needs DynamoDB/Cognito — offline is limited value | Future, if ever |
| Push notifications (web push) | Unreliable on iOS; React Native is better path | React Native phase |
| Background sync | Not supported on iOS; limited value | React Native phase |
| Install prompt banner component | Nice-to-have; users can install via browser menu | Phase 2 |

---

## 5. Files to Change

| File | Change | New? |
|------|--------|------|
| `web/public/manifest.webmanifest` | PWA manifest with app metadata | ✅ New |
| `web/public/icon-192.png` | App icon 192×192 (PNG) | ✅ New |
| `web/public/icon-512.png` | App icon 512×512 (PNG) | ✅ New |
| `web/public/icon-maskable-512.png` | Maskable icon for Android adaptive icons | ✅ New |
| `web/public/sw.js` | Minimal no-op service worker (3 lines) | ✅ New |
| `web/index.html` | Add manifest link, theme-color, apple-touch-icon, SW registration | Modified |

### Files NOT Changed

- `web/package.json` — no new dependencies
- `web/vite.config.js` — no plugin changes
- No component files (.jsx)
- No CSS files
- No backend files
- No Terraform

---

## 6. Manifest Content

```json
{
  "name": "Tog & Dogs Operations Portal",
  "short_name": "Tog & Dogs",
  "description": "Pet care scheduling and operations management",
  "start_url": "/",
  "display": "standalone",
  "orientation": "portrait",
  "theme_color": "#c28b1e",
  "background_color": "#faf7f2",
  "icons": [
    {
      "src": "/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "/icon-maskable-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }
  ]
}
```

---

## 7. index.html Changes

Add to `<head>`:

```html
<link rel="manifest" href="/manifest.webmanifest" />
<meta name="theme-color" content="#c28b1e" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<meta name="apple-mobile-web-app-title" content="Tog & Dogs" />
<link rel="apple-touch-icon" href="/icon-192.png" />
```

Add before closing `</body>`:

```html
<script>
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(() => {});
  }
</script>
```

---

## 8. App Icons

For Phase 1, create simple branded placeholder icons:
- **Background:** Brand gold `#c28b1e`
- **Foreground:** White paw print or "T&D" text
- **Format:** PNG, no transparency for `any` purpose; safe zone padding for `maskable`

These can be replaced with professionally designed icons later without any code changes.

---

## 9. Risks and Rollback

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Service worker causes stale content | None | — | No-op worker doesn't cache anything |
| Manifest breaks existing routing | Very Low | Low | `start_url: "/"` matches existing SPA behavior |
| iOS standalone mode breaks back navigation | Low | Low | React Router handles in-app navigation; iOS swipe-back still works |
| Icons look unprofessional | Low | Very Low | Placeholder icons; replace later with branded versions |
| Chrome doesn't show install prompt | Low | Low | Users can still install manually via menu |

**Rollback:** Delete `manifest.webmanifest`, `sw.js`, icons, and revert `index.html`. Redeploy. Instant.

---

## 10. Validation Checklist

### Build Validation
- [ ] `npm run build` passes with no errors
- [ ] `dist/` output contains `manifest.webmanifest`, `sw.js`, and icon PNGs
- [ ] No increase in JS bundle size (manifest/icons are separate static files)

### Lighthouse PWA Audit
- [ ] Run Lighthouse in Chrome DevTools → PWA section
- [ ] "Installable" badge shows green
- [ ] Manifest detected with correct `name`, `icons`, `start_url`, `display`
- [ ] Service worker registered

### Android Chrome
- [ ] Open site → Chrome shows "Install app" banner or menu option
- [ ] Tap Install → app icon appears on home screen
- [ ] Launch from home screen → full-screen, no URL bar
- [ ] Navigate between pages → React Router works normally
- [ ] Status bar shows brand gold color (`#c28b1e`)

### iOS Safari
- [ ] Open site → Share → "Add to Home Screen"
- [ ] App icon appears on home screen with correct icon
- [ ] Launch from home screen → full-screen standalone mode
- [ ] Navigate between pages → works normally
- [ ] Refresh (pull down) → page reloads from network (no stale cache)

### No Stale Cache Behavior
- [ ] Deploy a text change → reopen app from home screen → new content appears immediately
- [ ] No "cached old version" behavior (because no caching service worker)

### No Broken Routing
- [ ] Navigate to `/admin` from home screen launch → renders correctly
- [ ] Navigate to `/book` → renders correctly
- [ ] Navigate to `/terms` → renders correctly
- [ ] Browser back button / iOS swipe-back → works correctly

---

## 11. Recommendation on `vite-plugin-pwa`

**Do NOT use `vite-plugin-pwa` for Phase 1.**

Reasons:
- It auto-generates a service worker with Workbox caching — exactly what we want to avoid
- It adds a build dependency and configuration complexity
- A plain `manifest.webmanifest` + 3-line `sw.js` achieves the same installability goal
- If we want caching later, we can add the plugin in Phase 2 with proper cache-busting strategy

The plugin is excellent for apps that need offline support. This app doesn't — it requires network for every operation.

---

## 12. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8C: PWA Foundation (manifest + icons + minimal service worker).

Frontend static assets only. No component changes, no CSS changes, no backend changes.
No new npm dependencies. No vite.config.js changes.

=== 1. Create web/public/manifest.webmanifest ===

{
  "name": "Tog & Dogs Operations Portal",
  "short_name": "Tog & Dogs",
  "description": "Pet care scheduling and operations management",
  "start_url": "/",
  "display": "standalone",
  "orientation": "portrait",
  "theme_color": "#c28b1e",
  "background_color": "#faf7f2",
  "icons": [
    { "src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any" },
    { "src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any" },
    { "src": "/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}

=== 2. Create web/public/sw.js ===

// Minimal no-op service worker for PWA installability.
// Does NOT cache anything. Passes all requests through to network.
self.addEventListener('fetch', (event) => {
  event.respondWith(fetch(event.request));
});

=== 3. Create app icon PNGs ===

Create simple placeholder icons:
- web/public/icon-192.png (192x192 PNG)
- web/public/icon-512.png (512x512 PNG)
- web/public/icon-maskable-512.png (512x512 PNG with safe-zone padding)

Design: Solid brand gold background (#c28b1e), white "T&D" text centered,
or a simple white paw print silhouette. Keep it clean and minimal.

For the maskable icon, ensure the meaningful content stays within the center
80% safe zone (the outer 10% on each side may be cropped by Android).

If generating icons programmatically is difficult, create solid gold squares
with white text "T&D" as a placeholder. Matthew can replace with branded
icons later.

=== 4. Update web/index.html ===

Add to <head> (after the existing viewport meta tag):

<link rel="manifest" href="/manifest.webmanifest" />
<meta name="theme-color" content="#c28b1e" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<meta name="apple-mobile-web-app-title" content="Tog & Dogs" />
<link rel="apple-touch-icon" href="/icon-192.png" />

Add before closing </body> (after the root div script):

<script>
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch(function() {});
  }
</script>

=== 5. Validation ===

Run: npm run build (in web/)
Confirm:
- Build passes with no errors
- dist/ contains manifest.webmanifest
- dist/ contains sw.js
- dist/ contains icon-192.png, icon-512.png, icon-maskable-512.png
- No change to JS bundle size (icons/manifest are separate static files)

Do NOT deploy.
Do NOT modify any .jsx, .css, .py, or .tf files.
Do NOT install any npm packages.
Do NOT modify vite.config.js.

Return: files created/modified, build result, dist/ contents listing.
```

---

## 13. Commit Command (After Approval)

```bash
git add web/public/manifest.webmanifest web/public/sw.js web/public/icon-192.png web/public/icon-512.png web/public/icon-maskable-512.png web/index.html
git commit -m "feat: Release 8C — PWA foundation (manifest, icons, minimal service worker)"
```
