# Release 10B: TestFlight Readiness & App Store Connect Preparation

**Status:** Planning / Readiness Gap Analysis
**Priority:** Medium (enables TestFlight distribution when approved)
**Risk to Production:** None (planning-only)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Readiness checklist and gap identification

---

## 1. Current Mobile Configuration Summary

### EAS / Expo Config

| Field | Value | Source |
|-------|-------|--------|
| EAS Project | `@mattnicomn/tog-and-dogs` | `app.json` → `owner` + `slug` |
| EAS Project ID | `6b77d541-ec62-4950-8375-aef7d21c12ea` | `app.json` → `extra.eas.projectId` |
| iOS Bundle ID | `com.usmissionhero.toganddogs` | `app.json` → `ios.bundleIdentifier` |
| Android Package | `com.usmissionhero.toganddogs` | `app.json` → `android.package` |
| App Name | "Tog & Dogs" | `app.json` → `name` |
| Version | 1.0.0 | `app.json` → `version` |
| Build Number (iOS) | 1 | `app.json` → `ios.buildNumber` |
| Expo SDK | 54 | `package.json` |
| Latest Preview Build | `58efd764-f170-4d6e-801c-7a1a7e76a2af` | EAS dashboard |
| Encryption Declaration | `ITSAppUsesNonExemptEncryption: false` | `app.json` → `ios.infoPlist` |

### Build Profiles (eas.json)

| Profile | Distribution | Purpose |
|---------|-------------|---------|
| `development` | internal (ad-hoc) | Dev client builds for Matthew |
| `preview` | internal (ad-hoc) | Standalone preview builds for Matthew |
| `production` | (default — store) | **App Store / TestFlight submission** |

### Assets Present

| Asset | Exists? | Requirement |
|-------|---------|------------|
| `icon.png` (1024×1024) | ✅ | App Store icon + device icon |
| `splash-icon.png` | ✅ | Splash screen |
| Android adaptive icons | ✅ | Android only |
| `favicon.png` | ✅ | Web/Expo Go |

---

## 2. TestFlight Readiness Checklist

### ✅ Already Done (No Action Needed)

| Item | Status |
|------|--------|
| Apple Developer account active | ✅ |
| Bundle ID registered (`com.usmissionhero.toganddogs`) | ✅ |
| EAS project configured and linked | ✅ |
| iOS icon present (1024×1024) | ✅ |
| Production build profile defined | ✅ |
| Encryption exemption declared | ✅ (`ITSAppUsesNonExemptEncryption: false`) |
| App builds and runs on device | ✅ (preview build validated) |
| Privacy Policy page live | ✅ (`toganddogs.usmissionhero.com/privacy`) |

### ❌ Not Yet Done (Required Before TestFlight)

| Item | Blocking? | Who Must Do It | Notes |
|------|-----------|---------------|-------|
| **Create App Store Connect app record** | ✅ Blocking | Matthew (manual, in browser) | Must be done in appstoreconnect.apple.com |
| **App Store Connect submit config in eas.json** | ✅ Blocking | Kiro/AG (after ASC record exists) | Needs `ascAppId` and `appleTeamId` |
| **Upload first production build to TestFlight** | ✅ Blocking | `eas build` + `eas submit` | Requires ASC record first |
| **App Store screenshots** | ⚠️ For external TestFlight | Matthew (capture from device) | Not needed for internal; needed for external beta review |
| **App description / what-to-test text** | ⚠️ For external TestFlight | Matthew/Kiro | Brief beta description |
| **Create external tester group** | ⚠️ For Ryan | Matthew (in ASC) | After first build processes |
| **Submit for Beta App Review** | ⚠️ For external testers | Apple (~24 hours) | Required for first external build only |
| **Invite Ryan by email** | ⚠️ For Ryan | Matthew (in ASC) | After beta review approval |

---

## 3. App Store Connect App Record Prerequisites

When Matthew creates the app record in App Store Connect, these fields are required:

### Required Fields

| Field | Recommended Value | Notes |
|-------|-------------------|-------|
| **Platform** | iOS | |
| **App Name** | Tog & Dogs | Must be unique on the App Store (check availability) |
| **Primary Language** | English (US) | |
| **Bundle ID** | `com.usmissionhero.toganddogs` | Must match app.json exactly |
| **SKU** | `tog-and-dogs-ios-001` | Internal identifier, not public |
| **Primary Category** | Business OR Lifestyle | Matthew's choice |
| **Secondary Category** | (optional) | |

### Required for TestFlight Processing

| Field | Value | Notes |
|-------|-------|-------|
| **Privacy Policy URL** | `https://toganddogs.usmissionhero.com/privacy` | Already live |
| **Support URL** | `https://toganddogs.usmissionhero.com` | Main portal |
| **Marketing URL** | (optional — leave blank) | Not required for TestFlight |
| **Age Rating** | 4+ (no objectionable content) | Pet care app, no mature content |
| **Export Compliance** | "No" (uses HTTPS only, no custom crypto) | Already declared in app.json |

### Required for External Beta Review

| Field | Value | Notes |
|-------|-------|-------|
| **Beta App Description** | "Pet care scheduling app for staff and admin use. Manage bookings, assignments, and visit completions." | Brief, honest |
| **What to Test** | "Login with staff or admin credentials. View schedule, approve bookings, assign staff, mark visits completed." | Guidance for reviewers |
| **Feedback Email** | `mbn@usmissionhero.com` | Where Apple sends review feedback |
| **Demo Account** | Provide credentials if required by Apple | May need a test account for review |
| **Screenshots** | At least 1 iPhone screenshot | Apple requires for external beta |

---

## 4. Privacy Nutrition Label (App Privacy)

Apple requires a data privacy declaration. Based on current app behavior:

### Data Collected

| Data Type | Collected? | Linked to Identity? | Used for Tracking? |
|-----------|-----------|--------------------|--------------------|
| **Email Address** | ✅ Yes (login) | ✅ Yes | ❌ No |
| **Name** | ✅ Yes (profile) | ✅ Yes | ❌ No |
| **Phone Number** | ✅ Yes (client profile) | ✅ Yes | ❌ No |
| **Physical Address** | ✅ Yes (visit location) | ✅ Yes | ❌ No |
| **User Content** (visit notes) | ✅ Yes | ✅ Yes | ❌ No |
| **Identifiers** (Cognito sub) | ✅ Yes | ✅ Yes | ❌ No |
| **Usage Data** | ❌ No | — | — |
| **Diagnostics** | ❌ No | — | — |
| **Location** | ❌ No | — | — |
| **Health** | ❌ No | — | — |
| **Financial** | ❌ No | — | — |
| **Sensitive** | ❌ No | — | — |

### Purposes

| Purpose | Applies? |
|---------|---------|
| App Functionality | ✅ Yes |
| Analytics | ❌ No |
| Advertising | ❌ No |
| Third-Party Advertising | ❌ No |
| Developer's Advertising | ❌ No |
| Product Personalization | ❌ No |

---

## 5. EAS Submit Configuration Gap

The current `eas.json` does NOT have a `submit` section. Before `eas submit` can work, add:

```json
"submit": {
  "production": {
    "ios": {
      "appleId": "MATTHEW_APPLE_ID_EMAIL",
      "ascAppId": "APP_STORE_CONNECT_APP_ID",
      "appleTeamId": "APPLE_TEAM_ID"
    }
  }
}
```

- `appleId`: Matthew's Apple ID email (used for authentication)
- `ascAppId`: The numeric app ID assigned when the ASC record is created (found in ASC → App Information)
- `appleTeamId`: Found in Apple Developer → Membership → Team ID

**This cannot be filled in until the App Store Connect record exists.**

---

## 6. Internal vs External TestFlight Path

### Internal TestFlight (Matthew / Ernest)

| Step | Prerequisite | Apple Review? |
|------|-------------|---------------|
| 1. Create ASC app record | Apple Developer account | ❌ |
| 2. Build with `eas build --profile production --platform ios` | EAS CLI, valid credentials | ❌ |
| 3. Submit with `eas submit --platform ios` | `eas.json` submit config | ❌ |
| 4. Wait for processing | ~5-15 minutes | ❌ |
| 5. Add Matthew/Ernest as internal testers | Must be ASC users | ❌ |
| 6. Install via TestFlight app | TestFlight on device | ❌ |

**No Apple review for internal testers.** Immediate availability after processing.

### External TestFlight (Ryan + Business Testers)

| Step | Prerequisite | Apple Review? |
|------|-------------|---------------|
| 1-4. Same as internal | Same | ❌ |
| 5. Create external tester group | Build processed | ❌ |
| 6. Add beta description + what-to-test | Text prepared | ❌ |
| 7. Submit build to external group | — | ✅ Beta App Review (~24h) |
| 8. After approval: invite Ryan by email | Ryan's Apple ID email | ❌ |
| 9. Ryan installs via TestFlight | TestFlight on device | ❌ |

**First external build requires Apple Beta Review.** Subsequent builds to the same group usually auto-approve.

---

## 7. Manual Steps Only Matthew Can Perform

These require browser access to App Store Connect and cannot be automated:

1. Create the App Store Connect app record
2. Fill in privacy nutrition label
3. Set age rating and category
4. Add internal testers (if using internal path)
5. Create external tester group
6. Set beta app description / what-to-test text
7. Provide Apple Demo Account if requested during review
8. Approve the `eas submit` authentication (first time may require App Store Connect API key or Apple ID auth)

---

## 8. Steps Kiro/AG Can Perform After Approval

1. Update `eas.json` with submit configuration (once ASC app ID is known)
2. Run `eas build --profile production --platform ios`
3. Run `eas submit --platform ios`
4. Draft beta description / what-to-test text
5. Capture screenshots from simulator or device
6. Document the TestFlight process for future rebuilds

---

## 9. Risks and Open Questions

| Risk / Question | Impact | Resolution |
|----------------|--------|-----------|
| App name "Tog & Dogs" may be taken | Blocks ASC record | Check availability; alternatives: "Tog and Dogs", "Tog & Dogs Pet Care" |
| Apple Beta Review rejects build | Blocks external testing | Unlikely for functional app; ensure no placeholder/test screens visible |
| Ryan's Apple ID email unknown | Blocks invite | Ask Ryan when ready |
| Demo account for Apple review | May be required | Create a read-only test account OR document that login requires real credentials |
| Screenshots needed for external | Apple requirement | Capture from simulator or real device |
| 90-day build expiration | Testers must reinstall | Rebuild monthly; EAS makes this trivial |
| Push notifications not implemented | Apple may ask about notification permissions | Not declared in current config — not a blocker |

---

## 10. Approval Gates

| Gate | Action | Approver |
|------|--------|----------|
| **Gate A** | Create App Store Connect app record | Matthew |
| **Gate B** | Update `eas.json` with submit config | Matthew |
| **Gate C** | Build production iOS binary | Matthew |
| **Gate D** | Submit to App Store Connect / TestFlight | Matthew |
| **Gate E** | Add internal testers | Matthew |
| **Gate F** | Submit for external Beta App Review | Matthew |
| **Gate G** | Invite Ryan to external group | Matthew (when Ryan is ready) |

**No gate should be crossed without explicit approval.**

---

## 11. Validation Checklist (For When Matthew Approves)

| # | Check | Expected |
|---|-------|----------|
| 1 | App Store Connect record exists | App visible at appstoreconnect.apple.com |
| 2 | Bundle ID matches | `com.usmissionhero.toganddogs` in ASC matches app.json |
| 3 | `eas.json` has submit config | `ascAppId` and `appleTeamId` filled in |
| 4 | `eas build --profile production` succeeds | Build completes without error |
| 5 | `eas submit --platform ios` succeeds | Build uploaded to ASC |
| 6 | Build appears in TestFlight tab | Processing complete, available for testing |
| 7 | Internal tester can install | Matthew/Ernest install via TestFlight |
| 8 | App launches on TestFlight build | Login → Dashboard → Schedule works |
| 9 | External group created | "Business Testers" group visible |
| 10 | Beta review submitted + approved | Build available for external testers |
| 11 | Ryan receives invite and installs | TestFlight install successful |

---

## 12. What This Document Does NOT Authorize

- ❌ Creating the App Store Connect record
- ❌ Modifying `eas.json`
- ❌ Building any new iOS binaries
- ❌ Submitting anything to Apple
- ❌ Inviting any testers
- ❌ Modifying mobile code
- ❌ Changing AWS/production resources
- ❌ Pushing credentials or API keys to the repo

This is a readiness assessment only. Implementation requires per-gate approval.

---

## 13. Summary of Gaps

| Category | Ready? | Gap |
|----------|--------|-----|
| EAS project config | ✅ | None |
| iOS bundle ID | ✅ | None |
| App icon | ✅ | None |
| Encryption declaration | ✅ | None |
| Privacy policy URL | ✅ | None |
| App Store Connect record | ❌ | Must be created manually by Matthew |
| `eas.json` submit config | ❌ | Needs `ascAppId` + `appleTeamId` (available after ASC record) |
| Screenshots | ❌ | Need to capture for external beta |
| Beta description text | ❌ | Need to write (short, simple) |
| Ryan's Apple ID | ❌ | Need to ask Ryan when ready |
| Privacy nutrition label | ❌ | Answers documented above (Section 4), needs entry in ASC |

**Bottom line:** The app itself is TestFlight-ready. The blocker is App Store Connect setup (manual, ~15-20 minutes for Matthew) and the `eas.json` submit config (Kiro can add once ASC app ID is known).
