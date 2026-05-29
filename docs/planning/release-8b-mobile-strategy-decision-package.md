# Release 8B: Mobile Strategy Decision Package

**Status:** Planning / Decision Document
**Priority:** Strategic (informs next 2-3 months of development direction)
**Risk to Production:** None (planning only)
**Implementation:** None until Matthew decides

---

## 1. Current Mobile State After Release 8A

### What Responsive Web Now Solves

| Area | Status | Notes |
|------|--------|-------|
| Public intake form (`/book`) on phone | ✅ Fully usable | DatePickerGrid scales to 320px, visit windows stack vertically |
| Terms/Privacy pages on phone | ✅ Fully readable | No horizontal overflow |
| Client Portal (`/my-bookings`) on phone | ✅ Fully usable | Cards stack, cancel buttons enlarged, 44px targets |
| Admin Request List on phone | ✅ Fully usable | Table → stacked cards, badges visible |
| Admin New Visit modal on phone | ✅ Fully usable | Full-screen, date picker scales |
| Scheduler on phone | ✅ Fully usable | Mobile list view with `isMobile` detection |
| Staff/Client Management on phone | ✅ Usable | Cards stack, fields responsive |
| Action dropdowns on phone | ✅ Usable | Full-width on mobile, 44px targets |
| Filters/sidebar on phone | ✅ Usable | Collapsible toggle |
| Touch targets (44px minimum) | ✅ Enforced | All interactive elements at ≤480px |
| 320px viewport (iPhone SE) | ✅ No overflow | DatePickerGrid scales to 30px cells |

### What Responsive Web Still Does NOT Solve

| Gap | Impact | Why Web Can't Fix It |
|-----|--------|---------------------|
| **Push notifications** | High | Browsers support web push, but iOS Safari has limited/unreliable support. Native push via FCM/APNs is the gold standard. |
| **"App-like" home screen experience** | Medium | PWA can partially solve this, but iOS PWA support is limited (no badge counts, limited background refresh). |
| **App Store presence** | Medium | Clients can't find the app by searching "Tog and Dogs" in the App Store. |
| **Offline access** | Low | Service workers can cache the shell, but DynamoDB data requires network. Limited value for this app. |
| **Native device features** | Low | Camera for visit photos, biometric login — not currently needed but future possibilities. |
| **Performance on low-end phones** | Low | Current 248KB gzipped bundle loads in ~1-2s on 4G. Acceptable but not instant. |
| **Background sync** | Low | Staff can't receive schedule updates without opening the browser. |

---

## 2. Option A: Continue Responsive Web Only

### What It Means
Keep improving the current React/Vite web app. No PWA, no React Native. Users access via browser bookmark.

### Pros
- Zero additional complexity
- Single codebase to maintain
- Already works well on all devices (after 8A)
- Fastest iteration speed for new features

### Cons
- No push notifications on iOS
- No App Store presence
- Users must remember the URL or bookmark it
- No "app feel" (browser chrome always visible)
- Staff can't get assignment alerts without checking email

### When This Is the Right Choice
- If the business stays small (< 20 clients)
- If Ryan and staff are comfortable checking email for notifications
- If App Store presence isn't important for client acquisition

### Estimated Effort for Next Improvements
- Code-splitting (xlsx lazy load): 30 min
- Loading skeletons: 1-2 hours
- Minor CSS polish: ongoing as needed

---

## 3. Option B: Add PWA Capabilities

### What It Means
Add a `manifest.json`, service worker, and app icons to the existing web app. Users can "Add to Home Screen" and get a full-screen, app-like experience.

### What PWA Gives You

| Feature | iOS Support | Android Support |
|---------|-------------|-----------------|
| Add to Home Screen | ✅ Yes | ✅ Yes |
| Full-screen (no browser chrome) | ✅ Yes | ✅ Yes |
| App icon on home screen | ✅ Yes | ✅ Yes |
| Offline shell (cached HTML/CSS/JS) | ⚠️ Limited | ✅ Yes |
| Push notifications | ❌ Unreliable on iOS | ✅ Yes |
| Background sync | ❌ No | ⚠️ Limited |
| Badge count on icon | ❌ No | ✅ Yes |
| App Store listing | ❌ No | ⚠️ Via TWA (Trusted Web Activity) |

### Implementation Scope

| Item | Effort | Files |
|------|--------|-------|
| `web/public/manifest.json` | 15 min | New file |
| App icons (192px, 512px) | 30 min | New PNG files |
| Service worker (cache shell) | 1-2 hours | New `sw.js` + registration in `main.jsx` |
| Vite PWA plugin (`vite-plugin-pwa`) | 30 min | `vite.config.js` + `package.json` |
| "Install App" prompt banner | 1 hour | New component |
| Splash screen config | 30 min | `manifest.json` fields |

**Total: ~4-5 hours**

### Risks
- iOS PWA support is limited and Apple frequently changes behavior
- Service worker caching can cause stale content issues if not configured carefully
- Users may not understand "Add to Home Screen" without guidance
- Does NOT solve push notifications on iOS

### When This Is the Right Choice
- If you want an "app-like" feel without building a separate app
- If Android push notifications are sufficient (most staff/Ryan use Android)
- If App Store presence isn't critical
- As a stepping stone before React Native

---

## 4. Option C: Start React Native / Expo

### What It Means
Build a separate mobile app using React Native + Expo. Publish to Apple App Store and Google Play Store. The web app remains for desktop admin tasks.

### What React Native Gives You

| Feature | Status |
|---------|--------|
| Push notifications (iOS + Android) | ✅ Full support via Expo + FCM/APNs |
| App Store presence | ✅ Both stores |
| Native performance | ✅ 60fps animations, instant navigation |
| Offline data caching | ✅ AsyncStorage / SQLite |
| Biometric login | ✅ FaceID / fingerprint |
| Camera for visit photos | ✅ Native access |
| Background refresh | ✅ Background fetch |
| Badge counts | ✅ Both platforms |

### Backend Readiness (Already Done)

| Requirement | Status | Release |
|-------------|--------|---------|
| API Gateway endpoints | ✅ Ready | All roles supported |
| Cognito auth (same user pool) | ✅ Ready | Same `amazon-cognito-identity-js` works in RN |
| Device token registration API | ✅ Ready | Release 7C — `POST /client/devices` |
| Push notification backend | ✅ Ready | Release 7C — Expo Push client planned |
| Role-based API responses | ✅ Ready | `get_effective_role()` works from any client |
| Multi-day booking support | ✅ Ready | `selected_dates` accepted from any client |

### Implementation Phases (from mobile-app-strategy.md)

| Phase | Scope | Effort |
|-------|-------|--------|
| 1: Foundation | Expo setup, Cognito auth, role navigation, API client | 2-3 weeks |
| 2: Client Experience | My Bookings, Request Care, My Pets, Cancel | 2 weeks |
| 3: Staff Experience | My Schedule, Visit Details, Visit Notes | 1-2 weeks |
| 4: Admin/Owner | Dashboard, Request List, Approve/Assign, New Visit | 2-3 weeks |
| 5: App Store Submission | Icons, screenshots, privacy policy, review | 1 week |

**Total: 8-11 weeks for full feature parity**

### Code Reuse Expectations

| Layer | Reuse? | Notes |
|-------|--------|-------|
| Backend API | 100% reuse | Same endpoints, same auth |
| API client logic | ~80% reuse | Same fetch patterns, different HTTP library (axios vs fetch) |
| Auth flow | ~70% reuse | Same Cognito SDK, different storage (AsyncStorage vs localStorage) |
| Business logic | ~50% reuse | Date formatting, status labels, validation rules |
| UI components | 0% reuse | React Native uses `<View>`, `<Text>`, not `<div>`, `<span>` |
| CSS/styling | 0% reuse | React Native uses StyleSheet, not CSS |

### Maintenance Burden

| Concern | Impact |
|---------|--------|
| Two frontends to update for every feature | High — every new screen/feature needs web + mobile |
| App Store review delays | Medium — Apple takes 1-3 days per submission |
| Expo SDK upgrades | Medium — major upgrades every 3-4 months |
| iOS/Android OS compatibility | Low — Expo handles most of this |
| Push notification token management | Low — already built in Release 7C |

### Risks
- **Duplication:** AdminDashboard.jsx is 4500+ lines. Rebuilding in React Native is significant.
- **Maintenance:** Every new feature needs implementation in both web and mobile.
- **Premature:** Building a native app before Ryan validates the web workflow is risky.
- **Scope creep:** "Just one more screen" pressure will extend the timeline.
- **App Store rejection:** Apple may reject if the app is too simple or too similar to a website.

### When This Is the Right Choice
- If push notifications for clients are a business requirement
- If App Store presence is needed for client acquisition
- If Ryan confirms the web app workflow is correct and wants it on his phone natively
- If the business is growing beyond 20+ active clients

---

## 5. Option D: Pause Until Ryan Tests

### What It Means
Do no mobile work. Wait for Ryan to complete his production trial, gather feedback, and then decide based on real usage data.

### Pros
- Zero wasted effort on features Ryan might not need
- Ryan's feedback will clarify whether mobile is actually the priority
- Avoids building a native app for a workflow that hasn't been validated
- Frees Matthew's time for other projects

### Cons
- Delays mobile progress by 2-4 weeks
- If Ryan does want mobile, the timeline extends further

### When This Is the Right Choice
- If there's no urgent business need for mobile beyond "it would be nice"
- If Matthew has other priorities
- If the web app is sufficient for Ryan's daily operations

---

## 6. Authentication & Session Implications

| Approach | Auth Impact |
|----------|-------------|
| **Responsive Web** | No change — Cognito session in localStorage |
| **PWA** | No change — same as web, session persists in standalone mode |
| **React Native** | Same Cognito SDK, but tokens stored in AsyncStorage or SecureStore. Same user pool, same groups. No backend changes. |

All three approaches use the same Cognito user pool and the same JWT-based API authentication. No backend auth changes are needed for any option.

---

## 7. Notification Implications

| Approach | Email | Push (Android) | Push (iOS) |
|----------|-------|----------------|------------|
| **Responsive Web** | ✅ Postmark | ❌ No | ❌ No |
| **PWA** | ✅ Postmark | ✅ Web Push API | ❌ Unreliable |
| **React Native** | ✅ Postmark | ✅ FCM | ✅ APNs |

The backend device registration API (Release 7C) is already deployed. React Native is the only option that gives reliable push on both platforms.

---

## 8. Recommended Phased Roadmap

```
NOW (Release 8B):
  → Decision: Choose path based on this document
  → If PWA chosen: implement in 8B (4-5 hours)
  → If React Native chosen: plan Phase 1 in 8B, implement in 8C+

SOON (after Ryan tests):
  → Gather Ryan's feedback on web app workflow
  → Confirm which screens he uses most on his phone
  → Confirm whether push notifications are a real need

LATER (if React Native approved):
  → Phase 1: Foundation (auth + navigation + API client)
  → Phase 2: Client screens (simplest, highest user count)
  → Phase 3: Staff screens
  → Phase 4: Admin screens (most complex, lowest priority for mobile)
```

---

## 9. Explicit Recommendation

**Recommended path: PWA first, React Native later.**

### Reasoning

1. **PWA is 4-5 hours of work** and gives Ryan an "app-like" experience immediately (home screen icon, full-screen, faster loads). It's a low-risk stepping stone.

2. **React Native is 8-11 weeks** and duplicates the entire frontend. It should only start after Ryan confirms the web workflow is correct and mobile is genuinely the priority.

3. **The web app already works on mobile** (Release 8A validated this). The remaining gaps (push notifications, App Store) are real but not urgent for a business with < 20 clients.

4. **Ryan hasn't tested yet.** Building a native app for a workflow that hasn't been validated in production is premature optimization.

### Suggested Next Steps

| Step | When | What |
|------|------|------|
| 1 | Now | Implement PWA (manifest + service worker + install prompt) — Release 8B |
| 2 | When Ryan tests | Gather feedback on mobile experience with PWA |
| 3 | If push needed | Enable Expo Push backend (already built in 7C) + start React Native Phase 1 |
| 4 | If App Store needed | Complete React Native Phases 2-5 |

---

## 10. Files Affected

### If PWA Chosen (Release 8B Implementation)

| File | Change | New? |
|------|--------|------|
| `web/public/manifest.json` | PWA manifest with app name, icons, colors | ✅ New |
| `web/public/icon-192.png` | App icon 192×192 | ✅ New |
| `web/public/icon-512.png` | App icon 512×512 | ✅ New |
| `web/vite.config.js` | Add `vite-plugin-pwa` | Modified |
| `web/package.json` | Add `vite-plugin-pwa` dependency | Modified |
| `web/index.html` | Add manifest link + theme-color meta | Modified |

### If React Native Chosen (Future)

```
mobile/                          (entire new directory)
├── app.json
├── package.json
├── babel.config.js
├── src/
│   ├── screens/
│   ├── components/
│   ├── api/client.js            (mirrors web/src/api/client.js)
│   ├── auth/cognito.js
│   └── navigation/
```

---

## 11. Acceptance Criteria (If PWA Chosen)

- [ ] `manifest.json` exists with correct app name, icons, theme color
- [ ] App icons (192px, 512px) exist in `web/public/`
- [ ] Service worker caches the app shell (HTML, CSS, JS)
- [ ] "Add to Home Screen" works on Android Chrome
- [ ] "Add to Home Screen" works on iOS Safari
- [ ] App launches in standalone mode (no browser chrome)
- [ ] `npm run build` passes
- [ ] No backend changes
- [ ] Existing web app behavior unchanged

---

## 12. Validation Plan (If PWA Chosen)

| # | Test | Device | Expected |
|---|------|--------|----------|
| 1 | Open site in Chrome Android → "Install app" prompt | Android | App installs to home screen |
| 2 | Launch from home screen | Android | Full-screen, no browser chrome |
| 3 | Open site in Safari iOS → Share → Add to Home Screen | iPhone | App icon appears on home screen |
| 4 | Launch from home screen | iPhone | Full-screen standalone mode |
| 5 | Kill network → reopen app | Both | Cached shell loads (data may be stale) |
| 6 | Normal web browsing still works | Desktop | No change to desktop experience |

---

## 13. Risks and Rollback

| Risk | Impact | Mitigation |
|------|--------|------------|
| Service worker caches stale content | Medium | Use `workbox` with network-first strategy for API calls |
| iOS PWA limitations frustrate users | Low | PWA is a bonus, not a requirement — web still works |
| PWA install prompt is confusing | Low | Add a small banner with clear instructions |
| React Native scope creep | High | Only start after Ryan validates web workflow |

**Rollback (PWA):** Remove `manifest.json`, service worker, and plugin. Redeploy. Instant.
**Rollback (React Native):** Delete `mobile/` directory. No production impact.

---

## 14. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

### If Matthew Chooses PWA (Release 8B):

```
AG — implement Release 8B: PWA Foundation.

Frontend-only. No backend, Terraform, or infrastructure changes.

=== 1. Install vite-plugin-pwa ===

cd web
npm install -D vite-plugin-pwa

=== 2. Update web/vite.config.js ===

Add the PWA plugin:

import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icon-192.png', 'icon-512.png'],
      manifest: {
        name: 'Tog & Dogs Operations Portal',
        short_name: 'Tog & Dogs',
        description: 'Pet care scheduling and operations management',
        theme_color: '#c28b1e',
        background_color: '#faf7f2',
        display: 'standalone',
        start_url: '/',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' }
        ]
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png}'],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/a022yxuiue\.execute-api/,
            handler: 'NetworkFirst',
            options: { cacheName: 'api-cache', expiration: { maxEntries: 50, maxAgeSeconds: 300 } }
          }
        ]
      }
    })
  ],
  // ... rest of existing config unchanged
})

=== 3. Create app icons ===

Create simple placeholder icons (can be replaced with branded versions later):
- web/public/icon-192.png (192x192, gold/cream with paw print or "T&D" text)
- web/public/icon-512.png (512x512, same design)

For now, create solid-color placeholders with the brand gold (#c28b1e).
Matthew can replace with proper branded icons later.

=== 4. Update web/index.html ===

Add in <head>:
<link rel="manifest" href="/manifest.json" />
<meta name="theme-color" content="#c28b1e" />
<link rel="apple-touch-icon" href="/icon-192.png" />

=== 5. Validation ===

Run: npm run build (in web/)
Confirm no errors.
Confirm dist/ contains manifest.json and service worker files.
Do NOT deploy.

Return: files changed, build result, confirmation of manifest and SW generation.
```

### If Matthew Chooses React Native (Future — separate release):

```
This would be a separate Release 8C planning task. Do not implement yet.
```

---

## 15. Commit Command (Planning Doc)

```bash
git add docs/planning/release-8b-mobile-strategy-decision-package.md
git commit -m "docs: Release 8B — mobile strategy decision package (PWA vs React Native)"
```
