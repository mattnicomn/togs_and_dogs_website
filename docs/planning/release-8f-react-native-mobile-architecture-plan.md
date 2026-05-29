# Release 8F: React Native Mobile App Architecture Plan

**Status:** Planning (architecture decision document)
**Priority:** High (strategic — Ryan's primary interface will be mobile)
**Implementation:** None until Matthew approves
**Scope:** Architecture, screen inventory, auth strategy, phased roadmap

---

## 1. Is React Native Justified?

**Yes.** Here's why:

| Factor | Web PWA | React Native | Winner |
|--------|---------|-------------|--------|
| Ryan's daily use case (phone/tablet, on the go) | Adequate | Excellent | RN |
| Push notifications (iOS + Android) | ❌ iOS unreliable | ✅ Both platforms | RN |
| App Store presence (client discovery) | ❌ No | ✅ Yes | RN |
| Native feel (gestures, transitions, speed) | Adequate | Excellent | RN |
| Offline quick-view of today's schedule | ❌ No | ✅ AsyncStorage | RN |
| Background notification delivery | ❌ No | ✅ Yes | RN |
| Biometric login (FaceID/fingerprint) | ❌ No | ✅ Yes | RN |
| Development speed for first version | ✅ Already done | Slower (new codebase) | PWA |
| Maintenance burden | ✅ Single codebase | ⚠️ Two codebases | PWA |

**Verdict:** The PWA is a solid interim solution, but React Native is the correct long-term target for a business owner who manages operations from his phone. The question is timing, not whether.

### When to Start

**Recommended: Start Phase 1 after Ryan completes 1-2 weeks of production trial on the PWA.** His feedback will confirm which screens he uses most and which workflows feel clunky on mobile. This avoids building native screens for workflows he doesn't actually use daily.

If Matthew wants to start sooner (while Ryan is unavailable), Phase 1 foundation work (project setup, auth, API client) is safe to begin — it doesn't depend on Ryan's feedback.

---

## 2. Architecture: Expo + React Native

### Why Expo

| Factor | Bare React Native | Expo (Managed) |
|--------|-------------------|----------------|
| Project setup | Complex (Xcode + Android Studio) | Simple (`npx create-expo-app`) |
| iOS builds without Mac | ❌ Requires Mac | ✅ EAS Build (cloud) |
| Push notifications | Manual FCM/APNs setup | ✅ Expo Notifications (unified) |
| OTA updates | Manual CodePush setup | ✅ EAS Update (built-in) |
| Native modules | Full access | ✅ Most via Expo SDK; eject if needed |
| App Store submission | Manual | ✅ EAS Submit |

**Recommendation: Expo (managed workflow).** It eliminates the need for local Xcode/Android Studio, handles builds in the cloud, and provides push notifications out of the box. If a native module is ever needed that Expo doesn't support, we can eject to bare workflow later.

### Expo SDK Version

Use the latest stable Expo SDK (currently SDK 52+). Pin the version at project creation.

---

## 3. Admin-First Scope (Phase 1)

### Minimum Viable Screens for Ryan

| # | Screen | Priority | Equivalent Web Feature |
|---|--------|----------|----------------------|
| 1 | **Login** | Required | Cognito auth (same user pool) |
| 2 | **Dashboard / Stats** | Required | Stat cards (intake queue, needs assignment, scheduled) |
| 3 | **Request List** | Required | Filtered list with status chips, service labels, dates |
| 4 | **Request Detail** | Required | CareCard-equivalent: client info, pet info, dates, status |
| 5 | **Approve / Decline** | Required | Status transition action |
| 6 | **Assign Staff** | Required | Worker selection dropdown + calendar sync trigger |
| 7 | **Cancel Visit** | Required | Cancellation with reason |
| 8 | **Today's Schedule** | Required | Scheduler mobile list view (today's visits) |
| 9 | **Client Lookup** | Nice-to-have | Search/browse client profiles |
| 10 | **Staff Lookup** | Nice-to-have | View staff list and assignments |
| 11 | **New Visit (Manual Booking)** | Nice-to-have | Create booking for offline client |

### What Stays Web-Only (For Now)

| Feature | Reason |
|---------|--------|
| Public intake form (`/book`) | Clients use the web; no need to duplicate |
| Terms/Privacy pages | Static content, web is fine |
| Client Portal (`/my-bookings`) | Phase 3 scope |
| Data export (Excel) | Desktop task |
| Bulk operations (bulk purge, bulk status) | Risky on mobile |
| Google Calendar OAuth flow | Requires browser redirect |
| Staff/Client onboarding (Cognito user creation) | Complex admin task, web is fine |
| MasterScheduler (full calendar grid) | Better on desktop/tablet |

---

## 4. Backend Reuse Strategy

### Zero Backend Changes Required

The existing backend is already mobile-ready:

| Backend Component | Mobile Compatibility | Notes |
|-------------------|---------------------|-------|
| API Gateway endpoints | ✅ Same URLs | JSON REST, works from any HTTP client |
| Cognito authentication | ✅ Same user pool | `amazon-cognito-identity-js` works in RN |
| Role-based access (RBAC) | ✅ Same JWT groups | `get_effective_role()` reads JWT claims |
| DynamoDB data model | ✅ No change | Same PK/SK patterns |
| Google Calendar sync | ✅ Triggered by API calls | Mobile calls same `/admin/assign` endpoint |
| Postmark notifications | ✅ No change | Triggered server-side on status transitions |
| Device registration (Release 7C) | ✅ Ready | `POST /client/devices` accepts Expo push tokens |
| Multi-day bookings | ✅ No change | `selected_dates` accepted from any client |
| Notification dedup | ✅ No change | Server-side logic, client-agnostic |

### API Client Layer

The React Native app will have its own `api/client.ts` that mirrors `web/src/api/client.js`:

```typescript
// mobile/src/api/client.ts
const API_URL = 'https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod';

const request = async (path: string, method: string, data?: any, token?: string) => {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = token;
  
  const response = await fetch(`${API_URL}${path}`, {
    method, headers, body: data ? JSON.stringify(data) : undefined
  });
  
  if (!response.ok) throw new Error(await response.text());
  return response.json();
};
```

Same endpoints, same payloads, same responses. The only difference is how the auth token is obtained (from secure storage instead of browser localStorage).

---

## 5. Authentication Approach

### Options Evaluated

| Approach | Pros | Cons | Recommendation |
|----------|------|------|---------------|
| **`amazon-cognito-identity-js` (direct)** | Same library as web, full control, no extra deps | Manual token refresh, manual secure storage | ✅ Recommended |
| **AWS Amplify** | Higher-level API, built-in UI components | Heavy dependency (~2MB), opinionated, version churn | ❌ Too heavy |
| **Cognito Hosted UI** | Zero custom auth code | Redirects to browser, poor UX on mobile | ❌ Bad UX |

### Recommended: Direct Cognito SDK + Expo SecureStore

```typescript
// mobile/src/auth/cognito.ts
import { CognitoUserPool, CognitoUser, AuthenticationDetails } from 'amazon-cognito-identity-js';
import * as SecureStore from 'expo-secure-store';

// Same pool config as web
const poolData = { UserPoolId: 'us-east-1_XXXXX', ClientId: 'XXXXX' };
const userPool = new CognitoUserPool(poolData);

// Token storage: Expo SecureStore (encrypted, per-device)
// Replaces browser localStorage
```

This gives:
- Same auth flow as web (email + password)
- Tokens stored securely (encrypted keychain on iOS, encrypted SharedPreferences on Android)
- Automatic token refresh via Cognito SDK
- Same JWT claims for role resolution
- Biometric unlock can be layered on top later

---

## 6. Proposed Repo Structure

```
togs_and_dogs_website/
├── web/                          ← Existing React/Vite web app (unchanged)
├── mobile/                       ← NEW: React Native / Expo app
│   ├── app.json                  ← Expo config (app name, icons, splash)
│   ├── package.json              ← RN dependencies
│   ├── tsconfig.json             ← TypeScript config
│   ├── babel.config.js           ← Babel for RN
│   ├── App.tsx                   ← Root component
│   ├── src/
│   │   ├── api/
│   │   │   ├── client.ts        ← API client (mirrors web/src/api/client.js)
│   │   │   └── config.ts        ← API URL, pool IDs
│   │   ├── auth/
│   │   │   ├── cognito.ts       ← Cognito auth (mirrors web/src/api/auth.js)
│   │   │   ├── AuthContext.tsx   ← React context for auth state
│   │   │   └── useAuth.ts       ← Hook for login/logout/session
│   │   ├── screens/
│   │   │   ├── LoginScreen.tsx
│   │   │   ├── DashboardScreen.tsx
│   │   │   ├── RequestListScreen.tsx
│   │   │   ├── RequestDetailScreen.tsx
│   │   │   ├── ScheduleScreen.tsx
│   │   │   ├── ClientLookupScreen.tsx
│   │   │   └── StaffLookupScreen.tsx
│   │   ├── components/
│   │   │   ├── StatusChip.tsx
│   │   │   ├── RequestCard.tsx
│   │   │   ├── ActionSheet.tsx
│   │   │   └── StatCard.tsx
│   │   ├── navigation/
│   │   │   ├── AppNavigator.tsx  ← Tab + stack navigation
│   │   │   └── AuthNavigator.tsx ← Login flow
│   │   ├── hooks/
│   │   │   ├── useRequests.ts
│   │   │   └── useStaff.ts
│   │   └── theme/
│   │       └── colors.ts        ← Brand colors (same as web CSS vars)
│   ├── assets/
│   │   ├── icon.png             ← App icon
│   │   ├── splash.png           ← Splash screen
│   │   └── adaptive-icon.png    ← Android adaptive icon
│   └── eas.json                  ← EAS Build config
├── src/backend/                  ← Shared backend (unchanged)
├── infra/                        ← Shared Terraform (unchanged)
├── docs/                         ← Shared docs
└── tests/                        ← Shared backend tests
```

### Why `/mobile` Not `/apps/mobile`

- Simpler path, matches the existing `web/` convention
- No nested `apps/` directory needed for a two-app monorepo
- Clear parallel: `web/` = browser app, `mobile/` = native app

---

## 7. Tablet-Specific Layout Considerations

Ryan uses both phone and tablet. The app should adapt:

| Viewport | Layout Strategy |
|----------|----------------|
| Phone (< 768px) | Single-column, bottom tab navigation |
| Tablet portrait (768px–1024px) | Split view: list on left, detail on right |
| Tablet landscape (> 1024px) | Full split view with wider detail panel |

### Implementation

React Native's `useWindowDimensions()` hook provides real-time width. Use it to conditionally render split-view layouts on tablets:

```typescript
const { width } = useWindowDimensions();
const isTablet = width >= 768;

return isTablet ? <SplitView /> : <StackView />;
```

This gives Ryan a desktop-like experience on his iPad while keeping the phone experience focused and simple.

---

## 8. Phased Roadmap

### Phase 1: Ryan/Admin App Foundation (2-3 weeks)

| Week | Deliverable |
|------|-------------|
| 1 | Expo project setup, Cognito auth, login screen, token storage |
| 1 | API client layer, role detection, auth context |
| 2 | Dashboard screen (stat cards), request list screen (filtered) |
| 2 | Request detail screen (client/pet info, status, dates) |
| 3 | Action flows: approve, assign staff, cancel |
| 3 | Today's schedule screen, basic navigation |

**Exit criteria:** Ryan can log in, view requests, approve bookings, assign staff, and see today's schedule — all from his phone.

### Phase 2: Staff App (1-2 weeks)

| Deliverable |
|-------------|
| Staff login (same app, role-based navigation) |
| My Schedule screen (today's visits with care instructions) |
| Visit detail screen (client info, pet info, access codes) |
| Push notifications for new assignments |

### Phase 3: Client App (2 weeks)

| Deliverable |
|-------------|
| Client login (same app, role-based navigation) |
| My Bookings screen (upcoming/past visits) |
| Request Care screen (service type, dates, pets) |
| Cancel Visit flow |
| Push notifications for approvals and schedule changes |

### Phase 4: Native Features (1-2 weeks)

| Deliverable |
|-------------|
| Push notifications (Expo Notifications + backend device registration) |
| Biometric login (FaceID / fingerprint) |
| App Store submission (iOS + Android) |
| OTA updates via EAS Update |

---

## 9. Push Notification Integration

### Backend Already Ready (Release 7C)

| Component | Status |
|-----------|--------|
| `POST /client/devices` — register device token | ✅ Deployed |
| `DELETE /client/devices/{deviceId}` — remove token | ✅ Deployed |
| Device token DynamoDB schema (`DEVICE#<id>` / `USER#<sub>`) | ✅ Deployed |
| Expo Push client (`expo_push_client.py`) | ⏳ Planned (Release 7C Phase 2) |
| Push dispatch in `notify_event()` | ⏳ Planned (Release 7C Phase 2) |

### Mobile-Side Implementation

```typescript
import * as Notifications from 'expo-notifications';

// Get Expo push token
const token = (await Notifications.getExpoPushTokenAsync()).data;
// Register with backend
await registerDevice(token, platform, appVersion);
```

Push notifications will complement (not replace) Postmark email. Both channels fire for the same events.

---

## 10. Risks and Maintenance Implications

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Two codebases to maintain** | Medium | Admin-first scope limits duplication; web handles complex/rare tasks |
| **Feature drift (web vs mobile)** | Medium | Shared API means data is always consistent; UI can differ |
| **Expo SDK upgrades** | Low | Upgrade every 2-3 months; EAS handles build compatibility |
| **App Store rejection** | Low | Follow Apple guidelines; app has real utility (not a wrapper) |
| **Auth token handling differences** | Low | Same Cognito SDK; only storage mechanism differs |
| **Ryan doesn't use it** | Low | Start with admin-only; validate before expanding |
| **Scope creep** | Medium | Strict phase boundaries; web handles everything mobile doesn't |

### Estimated Ongoing Maintenance

- **New feature (both platforms):** +30-50% effort vs web-only (API is shared, only UI differs)
- **Bug fixes:** Usually platform-specific (one fix, not two)
- **Expo upgrades:** ~2-4 hours per quarter
- **App Store updates:** ~1 hour per submission (mostly automated via EAS)

---

## 11. Recommendation

**Start React Native Phase 1 foundation work after Release 8E is closed and Matthew approves.**

The foundation (project setup, auth, API client) doesn't depend on Ryan's feedback and can be built while he's unavailable. The screen implementations (dashboard, request list, actions) should ideally wait for Ryan's PWA trial feedback to confirm which workflows he uses most.

**Suggested timeline:**
- **Now:** Approve this architecture plan
- **Next 1-2 weeks:** AG sets up Expo project, auth, API client (Phase 1 foundation)
- **When Ryan tests:** Gather feedback on which screens to prioritize
- **After feedback:** Build remaining Phase 1 screens, then Phase 2-4

---

## 12. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8F Phase 1 Foundation: React Native / Expo Project Setup.

Create the mobile app foundation. No backend changes. No Terraform. No web app changes.

=== 1. Create Expo Project ===

In the repo root, run:
  npx create-expo-app mobile --template blank-typescript

This creates mobile/ with:
  - app.json (Expo config)
  - package.json
  - tsconfig.json
  - App.tsx
  - assets/

=== 2. Configure app.json ===

Update mobile/app.json:
  name: "Tog & Dogs"
  slug: "tog-and-dogs"
  version: "1.0.0"
  orientation: "default" (allows both portrait and landscape)
  icon: "./assets/icon.png"
  splash: { image: "./assets/splash.png", backgroundColor: "#faf7f2" }
  ios: { bundleIdentifier: "com.usmissionhero.toganddogs" }
  android: { package: "com.usmissionhero.toganddogs", adaptiveIcon: { ... } }

=== 3. Install Core Dependencies ===

cd mobile
npx expo install amazon-cognito-identity-js expo-secure-store @react-navigation/native @react-navigation/native-stack @react-navigation/bottom-tabs react-native-screens react-native-safe-area-context

=== 4. Create API Client ===

Create mobile/src/api/config.ts:
  export const API_URL = 'https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod';
  export const USER_POOL_ID = '...'; // Same as web
  export const CLIENT_ID = '...'; // Same as web

Create mobile/src/api/client.ts:
  Mirror web/src/api/client.js with TypeScript types.
  Use the same endpoint paths and payload shapes.

=== 5. Create Auth Module ===

Create mobile/src/auth/cognito.ts:
  Same CognitoUserPool setup as web/src/api/auth.js.
  Store tokens in Expo SecureStore instead of localStorage.

Create mobile/src/auth/AuthContext.tsx:
  React context providing: user, session, role, login(), logout(), isLoading.

=== 6. Create Basic Navigation ===

Create mobile/src/navigation/AppNavigator.tsx:
  - If not authenticated: show LoginScreen
  - If authenticated: show bottom tab navigator with:
    - Dashboard tab
    - Requests tab
    - Schedule tab
    - More tab (placeholder)

=== 7. Create Login Screen ===

Create mobile/src/screens/LoginScreen.tsx:
  - Email + password inputs
  - Login button
  - Error display
  - Loading state
  - Calls cognito.signIn()

=== 8. Create Placeholder Screens ===

Create stub screens that just show the screen name and user role:
  - DashboardScreen.tsx ("Dashboard — Role: owner")
  - RequestListScreen.tsx ("Requests — loading...")
  - ScheduleScreen.tsx ("Today's Schedule")

=== 9. Validation ===

Run: npx expo start (confirm app launches in Expo Go or simulator)
Run: npx expo export --platform web (confirm no TypeScript errors)
Confirm: Login screen renders, auth flow connects to Cognito

Do NOT submit to App Store.
Do NOT modify web/ directory.
Do NOT modify backend, Terraform, or AWS resources.
Do NOT add Cognito pool IDs to committed code (use environment config).

Return: files created, dependency list, screenshot of login screen if possible.
```

---

## 13. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-8f-react-native-mobile-architecture-plan.md
git commit -m "docs: Release 8F — React Native mobile app architecture plan"
```
