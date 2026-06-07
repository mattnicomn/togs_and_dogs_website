# Release 8X: Mobile App Distribution Readiness

**Status:** Planning
**Priority:** High (prerequisite for real operational use outside Expo Go)
**Risk to Production:** None (configuration + build tooling only)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** EAS Build configuration, app identity, TestFlight readiness

---

## 1. Purpose

Prepare the mobile app for distribution as a standalone build (not Expo Go) so Ryan and staff can install it on their real devices permanently. Expo Go is sufficient for development testing but is NOT suitable for production use because:
- It requires the development server to be running
- It can't receive push notifications
- It shares the Expo Go app icon/identity
- It can't be installed independently without the Expo Go client

---

## 2. Current Mobile App State

### Configuration

| Item | Current Value |
|------|--------------|
| Expo SDK | 54.0.0 |
| React Native | 0.81.5 |
| App name | "mobile" (placeholder) |
| App slug | "mobile" (placeholder) |
| Bundle identifier (iOS) | Not set |
| Package name (Android) | Not set |
| App icons | ✅ Present (gold paw print) |
| Splash screen | ✅ Present (`splash-icon.png`) |
| EAS config (`eas.json`) | ❌ Not created |
| Expo account linked | ❌ Not confirmed |
| Apple Developer account | ❌ Not confirmed |

### Validated Features (Expo Go)

| Feature | iPhone | Status |
|---------|--------|--------|
| Staff login (Cognito) | ✅ | Validated 8R |
| Today/Upcoming schedule | ✅ | Validated 8L |
| Booking detail view | ✅ | Validated 8O |
| Mark Completed | ✅ | Validated 8T |
| Visit Notes | ✅ | Validated 8W |
| Admin assignment | ✅ | Validated 8M |
| Token refresh | ✅ | Validated 8L |
| Pull-to-refresh | ✅ | Validated 8L |

---

## 3. Distribution Options

### Option A: Continue Expo Go Only

| Pros | Cons |
|------|------|
| Zero setup | Requires dev server running |
| Instant reload | Can't distribute to Ryan without him installing Expo Go |
| Already working | No push notifications possible |
| | Not a "real app" on the device |

**Verdict:** Unsuitable for operational use. Good for development only.

### Option B: EAS Development Build (Recommended First Step)

| Pros | Cons |
|------|------|
| Standalone app on device | Requires Apple Developer account ($99/year) |
| Works without dev server running | Build takes 5-10 minutes in EAS cloud |
| Can install via QR code / link | Limited to registered devices (iOS) |
| Push notifications possible | Requires device UDID registration for iOS ad-hoc |
| Same codebase, no changes | |

**Verdict:** Best first step. Gives Ryan and staff a real standalone app without going through App Store review.

### Option C: Internal iOS TestFlight

| Pros | Cons |
|------|------|
| Up to 10,000 internal testers | Requires Apple Developer account |
| Install via TestFlight app | Requires Apple review (usually < 24 hours for TestFlight) |
| 90-day expiration per build | Must be a member of the dev team |
| Professional install experience | |
| Push notifications supported | |

**Verdict:** Best for wider distribution once the app is stable. Requires App Store Connect setup.

### Option D: Android Internal Testing (Play Console)

| Pros | Cons |
|------|------|
| Install via link / Play Store | Requires Google Play Console ($25 one-time) |
| Up to 100 internal testers | Requires AAB build |
| No review for internal track | |

**Verdict:** Defer until Android users are identified. Ryan uses iPhone.

---

## 4. Recommended Path

```
Step 1: EAS Development Build (this release)
  → Ryan/staff get standalone app on their iPhones
  → No App Store review needed
  → Push notifications can be added later
  
Step 2: TestFlight (future release)
  → Professional distribution
  → Wider team testing
  → Prerequisite for public App Store
  
Step 3: Public App Store (future)
  → Client-facing app
  → Requires full review
```

---

## 5. Required Accounts & Configuration

### Expo Account

| Requirement | Status | Action |
|-------------|--------|--------|
| Expo account created | Verify | `npx expo login` or create at expo.dev |
| Expo project linked | ❌ Not done | Run `npx eas init` in `mobile/` |

### Apple Developer Account

| Requirement | Status | Action |
|-------------|--------|--------|
| Apple Developer Program membership | Verify | $99/year at developer.apple.com |
| Apple ID associated | Verify | Must be the same account used for Xcode signing |
| Team ID known | Verify | Found in Apple Developer portal |

If Matthew doesn't have an Apple Developer account yet, this is a blocker for iOS builds. Android builds can proceed without one.

### App Identity Configuration

| Field | Recommended Value | Purpose |
|-------|-------------------|---------|
| `name` | "Tog & Dogs" | Display name on home screen |
| `slug` | "tog-and-dogs" | Expo project identifier |
| `ios.bundleIdentifier` | "com.usmissionhero.toganddogs" | Unique iOS app identity |
| `android.package` | "com.usmissionhero.toganddogs" | Unique Android app identity |
| `version` | "1.0.0" | Semantic version for store |
| `ios.buildNumber` | "1" | iOS internal build counter |
| `android.versionCode` | 1 | Android internal build counter |

---

## 6. EAS Configuration (`eas.json`)

```json
{
  "cli": {
    "version": ">= 16.0.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "ios": {
        "simulator": false
      }
    },
    "preview": {
      "distribution": "internal"
    },
    "production": {
      "autoIncrement": true
    }
  },
  "submit": {
    "production": {
      "ios": {
        "appleId": "APPLE_ID_HERE",
        "ascAppId": "APP_STORE_CONNECT_APP_ID",
        "appleTeamId": "TEAM_ID_HERE"
      }
    }
  }
}
```

### Build Profiles

| Profile | Purpose | Distribution |
|---------|---------|-------------|
| `development` | Dev builds with dev client | Internal (ad-hoc) |
| `preview` | Test builds without dev client | Internal (ad-hoc) |
| `production` | App Store / Play Store release | Store |

---

## 7. Updated `app.json`

```json
{
  "expo": {
    "name": "Tog & Dogs",
    "slug": "tog-and-dogs",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "userInterfaceStyle": "light",
    "splash": {
      "image": "./assets/splash-icon.png",
      "resizeMode": "contain",
      "backgroundColor": "#faf7f2"
    },
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.usmissionhero.toganddogs",
      "buildNumber": "1"
    },
    "android": {
      "package": "com.usmissionhero.toganddogs",
      "versionCode": 1,
      "adaptiveIcon": {
        "backgroundColor": "#E6F4FE",
        "foregroundImage": "./assets/android-icon-foreground.png",
        "backgroundImage": "./assets/android-icon-background.png",
        "monochromeImage": "./assets/android-icon-monochrome.png"
      }
    },
    "plugins": [
      "expo-secure-store"
    ],
    "extra": {
      "eas": {
        "projectId": "TO_BE_SET_BY_EAS_INIT"
      }
    }
  }
}
```

---

## 8. Build Process (EAS Development Build)

### One-Time Setup

```bash
# 1. Install EAS CLI globally
npm install -g eas-cli

# 2. Login to Expo account
npx eas login

# 3. Initialize EAS project (links to Expo servers)
cd mobile
npx eas init

# 4. Configure build profiles
# Creates eas.json (see Section 6)

# 5. Register iOS devices (ad-hoc distribution)
npx eas device:create
# Generates a link — Ryan/staff open on their iPhone to register UDID
```

### Build Command

```bash
cd mobile
npx eas build --profile development --platform ios
```

This builds in Expo's cloud servers (no local Xcode required) and produces an `.ipa` file. EAS provides a QR code/link for installation.

### Install on Device

1. EAS build completes → provides install URL
2. Ryan opens URL on iPhone → taps "Install"
3. App appears on home screen as "Tog & Dogs"
4. First launch → login screen

---

## 9. Environment Configuration

### API URL (Already Hardcoded)

```typescript
// mobile/src/api/config.ts
export const CONFIG = {
  API_URL: 'https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod',
  USER_POOL_ID: 'us-east-1_counlsXGU',
  CLIENT_ID: '1u4t7rfo339nkcgaf6q8s8sc6u',
};
```

This is currently hardcoded. For a production build, these values should NOT change (same production backend). However, for future multi-environment support, consider moving to Expo environment variables (`app.config.js` with `process.env`).

**For 8X MVP:** Keep hardcoded. Same API, same Cognito pool. No change needed.

### Secure Storage Behavior

`expo-secure-store` works identically in development builds and production builds. Tokens stored in the iOS Keychain remain encrypted and per-app-scoped.

---

## 10. Build Validation Checklist

After a successful EAS development build + install:

| # | Test | Expected |
|---|------|----------|
| 1 | App icon on home screen | "Tog & Dogs" with gold paw print |
| 2 | Launch app (no dev server) | App starts independently |
| 3 | Login as admin (Ryan) | Dashboard with stats |
| 4 | Login as staff | Schedule with Today/Upcoming |
| 5 | Request list + filters | Real data loads |
| 6 | Assign staff from mobile | Confirmation → success |
| 7 | Mark Completed as staff | Notes saved, visit completed |
| 8 | Token refresh after idle | Session continues without re-login |
| 9 | No network → error handling | Error toast, no crash |
| 10 | Kill app → reopen | Session persists |
| 11 | App name in iOS Settings | "Tog & Dogs" |
| 12 | No Expo Go branding | Standalone app identity |

---

## 11. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| No Apple Developer account | Medium | Blocker for iOS | Matthew must verify/create account |
| Expo Go behavior differs from standalone | Low | Medium | Build validation checklist catches this |
| EAS build fails (SDK/dep issue) | Low | Low | Expo support + error logs |
| Device registration complexity | Low | Low | EAS provides guided flow |
| Push notifications not available yet | N/A | None | Deferred to future release |

---

## 12. Deferred Items

| Item | Reason | When |
|------|--------|------|
| Push notifications | Requires additional Expo config + backend enablement | 9A+ |
| Photo upload | Requires S3 integration | 9B+ |
| Client app screens | Not needed for internal staff/admin use | 9C+ |
| Public App Store release | Requires Apple review, marketing screenshots | 9D+ |
| Android distribution | Ryan uses iPhone; defer until Android users identified | Future |
| Multi-environment config | Only one environment (prod) exists | Future if staging needed |
| OTA updates (EAS Update) | Nice-to-have for hot fixes | After first stable build |

---

## 13. Rollback / No-Change Plan

- If EAS build fails: continue using Expo Go for testing
- If standalone build has issues: identify and fix in 8X.1 patch
- No production backend impact — app connects to same API
- No web/PWA impact
- Uninstalling the development build from a device is trivial (long-press → delete)

---

## 14. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8X: Mobile App Distribution Readiness.

Configuration changes only. No backend, web, Terraform, or infrastructure changes.

=== PREREQUISITES (Matthew must confirm before starting) ===

1. Does Matthew have an Apple Developer account? (Required for iOS builds)
   - If NO: this release is blocked until the account is created ($99/year at developer.apple.com)
   - If YES: provide the Apple Team ID for eas.json configuration

2. Does Matthew have an Expo account?
   - If NO: create one at https://expo.dev/signup
   - If YES: confirm the username

=== 1. Install EAS CLI ===

npm install -g eas-cli
npx eas --version

=== 2. Login to Expo ===

cd mobile
npx eas login
(Enter Expo account credentials)

=== 3. Initialize EAS Project ===

npx eas init
(This creates a project on Expo servers and adds a projectId to app.json)

=== 4. Update mobile/app.json ===

Change:
  "name": "mobile" → "name": "Tog & Dogs"
  "slug": "mobile" → "slug": "tog-and-dogs"

Add to "ios":
  "bundleIdentifier": "com.usmissionhero.toganddogs"
  "buildNumber": "1"

Add to "android":
  "package": "com.usmissionhero.toganddogs"
  "versionCode": 1

Add splash config:
  "splash": {
    "image": "./assets/splash-icon.png",
    "resizeMode": "contain",
    "backgroundColor": "#faf7f2"
  }

=== 5. Create mobile/eas.json ===

{
  "cli": { "version": ">= 16.0.0" },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "ios": { "simulator": false }
    },
    "preview": {
      "distribution": "internal"
    },
    "production": {
      "autoIncrement": true
    }
  }
}

=== 6. Register Test Devices (iOS) ===

npx eas device:create
(Generates a URL — Matthew/Ryan/staff open on their iPhones to register UDIDs)

=== 7. Attempt First Development Build ===

npx eas build --profile development --platform ios

Report: Build succeeds? Any errors? Install URL provided?

=== 8. Validation ===

If build succeeds:
- Install on test device
- Run through the 12-item build validation checklist (Section 10)
- Report pass/fail per item

If build fails:
- Report exact error message
- Do NOT retry without investigating the cause

=== 9. Do NOT ===

- Do NOT modify backend files
- Do NOT modify web/ directory
- Do NOT run Terraform
- Do NOT change AWS resources
- Do NOT submit to App Store (development builds are internal only)
- Do NOT change API URLs or Cognito configuration

Return: EAS init output, app.json diff, eas.json content, build result, install test observations.
```

---

## 15. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-8x-mobile-app-distribution-readiness-plan.md
git commit -m "docs: plan release 8x mobile app distribution readiness"
```
