# Release 8D: PWA Polish & Installed-App Validation

**Status:** Planning
**Priority:** Low (validation + minor polish, not blocking operations)
**Risk to Production:** None if docs-only; Very Low if minor static asset polish
**Terraform Required:** No
**Backend Changes:** None
**Recommendation:** Docs-only validation release with optional minor metadata polish

---

## 1. Current State (After Release 8C)

### What's Deployed and Working

| Asset | Status | Verified |
|-------|--------|----------|
| `/manifest.webmanifest` | ✅ Live | Name, short_name, start_url, scope, display, theme_color, icons |
| `/sw.js` | ✅ Live | No-op pass-through, zero cache, registers successfully |
| `/icon-192.png` | ✅ Live | Gold paw print brand icon |
| `/icon-512.png` | ✅ Live | Gold paw print brand icon |
| `/icon-maskable-512.png` | ✅ Live | Maskable variant with safe-zone padding |
| `index.html` meta tags | ✅ Live | manifest link, theme-color, apple-mobile-web-app-capable, apple-touch-icon |
| Chrome installability | ✅ Verified | Install option appears in Chrome menu |
| iOS Add to Home Screen | ✅ Verified | Share → Add to Home Screen works |
| Cache Storage | ✅ Empty | Zero bytes cached — no stale content risk |
| SPA routing in standalone | ✅ Verified | All routes work when launched from home screen |

### Manifest Content (Current)

```json
{
  "name": "Tog and Dogs Operations",
  "short_name": "Tog & Dogs",
  "display": "standalone",
  "orientation": "portrait",
  "theme_color": "#c28b1e",
  "background_color": "#faf7f2",
  "start_url": "/",
  "scope": "/"
}
```

### index.html PWA Tags (Current)

```html
<link rel="manifest" href="/manifest.webmanifest" />
<meta name="theme-color" content="#c28b1e" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
<meta name="apple-mobile-web-app-title" content="Tog & Dogs" />
<link rel="apple-touch-icon" href="/icon-192.png" />
```

---

## 2. Validation Checklist (Manual Testing)

This is the primary deliverable of Release 8D — a structured validation pass of the installed PWA experience.

### 2.1 Home Screen Icon & Name

| # | Test | Device | Expected | Pass? |
|---|------|--------|----------|-------|
| 1 | Install via Chrome menu → check home screen icon | Android | Gold paw print icon, label "Tog & Dogs" | |
| 2 | Add to Home Screen via Safari Share → check icon | iPhone | Gold paw print icon, label "Tog & Dogs" | |
| 3 | Icon is not blurry or pixelated at home screen size | Both | Crisp at device DPI | |
| 4 | Maskable icon renders correctly (no clipping of paw) | Android | Content within safe zone, no cut-off | |
| 5 | App name under icon is "Tog & Dogs" (short_name) | Both | Not truncated, not "Tog and Dogs Operations" | |

### 2.2 Standalone Display Mode

| # | Test | Device | Expected | Pass? |
|---|------|--------|----------|-------|
| 6 | Launch from home screen → no browser URL bar | Android | Full-screen standalone, no Chrome UI | |
| 7 | Launch from home screen → no Safari UI | iPhone | Full-screen standalone, no Safari bar | |
| 8 | Status bar shows brand gold color | Android | Gold (#c28b1e) status bar | |
| 9 | Status bar style on iOS | iPhone | Default (dark text on light background) | |
| 10 | Splash/loading screen shows brand colors | Android | Gold theme + cream background during load | |

### 2.3 Route Navigation in Standalone Mode

| # | Test | Device | Expected | Pass? |
|---|------|--------|----------|-------|
| 11 | Launch → lands on `/` (home/portal gateway) | Both | PortalGateway renders | |
| 12 | Navigate to `/book` | Both | IntakeForm renders, date picker works | |
| 13 | Navigate to `/terms` | Both | Terms page renders with version badge | |
| 14 | Navigate to `/privacy` | Both | Privacy page renders | |
| 15 | Navigate to `/admin` | Both | Login or dashboard renders | |
| 16 | Navigate to `/my-bookings` | Both | Client portal login or bookings render | |
| 17 | Use browser back gesture (swipe) | iPhone | Previous route renders (not exit app) | |
| 18 | Use Android back button | Android | Previous route renders (not exit app) | |
| 19 | Deep link: open `toganddogs.usmissionhero.com/book` from external link while app is installed | Both | Opens in standalone app (not browser) | |

### 2.4 No Stale Cache Behavior

| # | Test | Device | Expected | Pass? |
|---|------|--------|----------|-------|
| 20 | Close app → reopen from home screen | Both | Fresh content loads from network | |
| 21 | After a future deployment, reopen app | Both | New content appears immediately (no cached old version) | |
| 22 | DevTools → Application → Cache Storage | Desktop | 0 entries, 0 bytes | |
| 23 | DevTools → Application → Service Workers | Desktop | sw.js registered, no cached resources listed | |

### 2.5 Edge Cases

| # | Test | Device | Expected | Pass? |
|---|------|--------|----------|-------|
| 24 | Kill app (swipe away) → reopen | Both | App restarts fresh from `/` | |
| 25 | Airplane mode → open app | Both | Network error shown (not cached shell) — this is correct behavior | |
| 26 | Rotate device to landscape | Both | Layout adapts (no fixed portrait lock in app) | |
| 27 | Open external link from within app (e.g., email link) | Both | Opens in system browser, not inside the PWA | |

---

## 3. Potential Minor Polish Items

Based on the current manifest and meta tags, these are small improvements that could be made if validation reveals issues:

| # | Item | Severity | Change |
|---|------|----------|--------|
| A | **Manifest `name` inconsistency** — manifest says "Tog and Dogs Operations" but apple-mobile-web-app-title says "Tog & Dogs" | Very Low | Align to "Tog & Dogs" everywhere for consistency |
| B | **Missing `id` field in manifest** — Chrome recommends a `"id": "/"` field for stable app identity across manifest updates | Very Low | Add `"id": "/"` to manifest |
| C | **Missing `categories` field** — optional but helps app store discovery if ever listed via TWA | None | Add `"categories": ["business", "lifestyle"]` |
| D | **Missing `screenshots` field** — Chrome uses these for richer install UI on Android | Low | Add 1-2 screenshots (optional, can defer) |
| E | **apple-touch-icon should be 180×180** — Apple recommends 180px specifically for touch icon | Very Low | Add a 180px icon variant or keep 192px (works fine) |
| F | **No apple-touch-startup-image** — iOS splash screen customization | Very Low | Can add later if iOS splash is important |

### Recommendation on Polish Items

**Items A and B are worth fixing** (2 minutes each, zero risk). Items C–F can be deferred indefinitely — they're nice-to-have with no user-visible impact.

---

## 4. Release 8D Recommendation

**This should be primarily a validation/documentation release.**

| Approach | Scope | Effort | Risk |
|----------|-------|--------|------|
| **Option 1: Docs-only** — run the validation checklist, document results, close | Documentation | 30 min | None |
| **Option 2: Docs + minor manifest polish** — fix items A and B, then validate | 2 file changes + docs | 45 min | Very Low |

**Recommended: Option 2** — fix the name inconsistency and add the `id` field while we're here. It's 2 lines of change with zero risk, and it ensures the manifest is production-correct before Ryan tests.

---

## 5. Files Likely Affected (If Option 2)

| File | Change |
|------|--------|
| `web/public/manifest.webmanifest` | Change `name` to "Tog & Dogs Operations Portal", add `"id": "/"` |
| `docs/release-notes/release-8d-validation-closeout.md` | Validation results documentation |

### Files NOT Changed

- `web/index.html` — already correct
- `web/public/sw.js` — no change
- Icons — no change
- No component files
- No CSS files
- No backend files
- No Terraform
- No `package.json` or `vite.config.js`

---

## 6. Acceptance Criteria

- [ ] Validation checklist (Section 2) completed with pass/fail for each item
- [ ] Any failing items documented with screenshots/description
- [ ] Manifest `name` field aligned with brand ("Tog & Dogs Operations Portal")
- [ ] Manifest `id` field added (`"/"`)
- [ ] `npm run build` passes (if manifest changed)
- [ ] No service worker caching introduced
- [ ] No backend, Terraform, or infrastructure changes
- [ ] Closeout note committed

---

## 7. Risks and Rollback

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Manifest name change causes re-install prompt | Very Low | None | `id` field ensures app identity is stable |
| Validation reveals a real PWA bug | Low | Low | Document and fix in 8D or defer to 8E |
| iOS standalone mode has navigation issues | Low | Low | Document; React Router handles in-app nav |

**Rollback:** Revert manifest to previous version. Redeploy. Instant.

---

## 8. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8D: PWA Polish & Validation.

Minimal static asset change + validation documentation.

=== 1. Update web/public/manifest.webmanifest ===

Change the "name" field from:
  "name": "Tog and Dogs Operations"
To:
  "name": "Tog & Dogs Operations Portal"

Add an "id" field after "scope":
  "id": "/"

Final manifest should be:
{
  "name": "Tog & Dogs Operations Portal",
  "short_name": "Tog & Dogs",
  "description": "Pet care scheduling and operations management",
  "start_url": "/",
  "scope": "/",
  "id": "/",
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

=== 2. Validation ===

Run: npm run build (in web/)
Confirm build passes.
Confirm dist/ contains updated manifest.webmanifest with new name and id field.

=== 3. Run the validation checklist ===

After deployment (if Matthew approves), run through the validation checklist
in Section 2 of the planning document. Document results in a closeout note.

=== 4. Do NOT ===

- Do NOT modify sw.js
- Do NOT add caching or Workbox
- Do NOT modify index.html
- Do NOT modify any .jsx or .css files
- Do NOT modify backend, Terraform, or infrastructure
- Do NOT add npm dependencies

Return: manifest diff, build result, confirmation of minimal change.
```

---

## 9. Commit Commands

```bash
# Planning doc
git add docs/planning/release-8d-pwa-polish-validation-plan.md
git commit -m "docs: Release 8D — PWA polish and validation plan"

# Implementation (after approval)
git add web/public/manifest.webmanifest
git commit -m "fix: Release 8D — align manifest name and add stable id field"

# Closeout (after validation)
git add docs/release-notes/release-8d-validation-closeout.md
git commit -m "docs: Release 8D — PWA validation closeout"
```
