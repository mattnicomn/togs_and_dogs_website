# Phase 24A-9C: Cross-Platform Non-Write Physical Device Smoke Validation

## 1. Executive Summary & Status

- **Status:** **PHASE 24A-9C ACTIVE / IOS TESTFLIGHT AVAILABLE / ANDROID INTERNAL TESTING AVAILABLE / ANDROID EMULATOR RUNTIME CHECK CONFIRMED / PHYSICAL ANDROID DEVICE VALIDATION PENDING / NON-WRITE SCOPE AUTHORIZED / PRODUCTION-WRITE BOUNDARY ENFORCED**
- **Date:** 2026-08-09 (started) — ongoing until physical Android device validation complete
- **Source SHA for both builds:** `8a1ce46c0a8bd0d02f4000188b21e115b370281c`

---

## 2. Build Targets for This Validation

| Platform | Version | Build Identifier | Distribution Channel |
| :--- | :--- | :--- | :--- |
| **iOS** | `1.0.0` | Build 5 — EAS `c7b7d9da-056b-45a8-86cd-cd6882969464` | TestFlight (Matthew-only) |
| **Android** | `1.0.0` | versionCode 3 — EAS `e2bc9a1d-666b-4698-882f-6aa7ba7c2132` | Google Play Internal Testing (Matthew-only) |

---

## 3. Production Write Safety Boundary

**The following actions are EXPLICITLY NOT AUTHORIZED during this phase:**

| Action | Endpoint | Status |
| :--- | :--- | :--- |
| Pet Profile Edit Save | `PUT /client/pets/{petId}` | **NOT EXECUTED** |
| Care Request Submit | `POST /client/requests` | **NOT EXECUTED** |

If testing cannot avoid triggering either endpoint: **STOP that scenario immediately.**

---

## 4. Authorized Non-Write Smoke Scenarios

### 4A. Authentication
- Sign in with valid client credentials
- Observe session token storage
- Sign out and confirm session cleared

### 4B. Navigation
- Switch between all tabs (Bookings, My Pets, Profile)
- Verify tab bar renders correctly
- Verify back navigation

### 4C. My Pets — Read-Only
- View pet list
- Open individual pet detail record
- Verify all fields render with correct values

### 4D. My Pets — Edit Mode (Non-Write)
- Tap "Edit Profile" to enter edit mode
- Verify all 10 fields pre-populate correctly
- Modify field values locally; verify character limit enforcement (`PET_FIELDS` max lengths)
- Verify dirty-state detection (unsaved changes indicator)
- **Tap Cancel** — verify discard-changes confirmation `Alert.alert` appears
- Confirm discard; verify edit mode exits without saving
- **DO NOT TAP SAVE CHANGES**

### 4E. Care Request Intake — Non-Write
- Tap `+ Book Care` or `+ Book Pet Care` CTA
- Navigate all 3 intake wizard steps (service selection → date/window → pet selection)
- Verify `SERVICE_TYPES` contract-derived service options render (excluding `MEET_GREET`)
- Select service, date, window, and pet
- Enter notes if safe (non-submit path only)
- Accept terms on Step 3 to reach review screen
- Verify review screen renders all selections correctly
- **DO NOT TAP SUBMIT CARE REQUEST**
- Tap back/cancel to exit wizard

### 4F. Bookings
- View booking/request list
- Verify `StatusBadge` renders correct labels for each request status
- Verify `+ Book Care` CTA visible in header

### 4G. Visual Quality
- Verify 8px action button border radius (`BookingsScreen`, `IntakeScreen`)
- Verify 12px card surface border radius (`IntakeScreen` service grid)
- Verify `COLORS.white` token usage (no raw `#ffffff` strings visible)
- Verify status badge pill shapes (`borderRadius: 99`)
- Verify selection chip shapes (`borderRadius: 20`)
- Verify keyboard avoidance / safe-area behavior

### 4H. Accessibility (where practical)
- Enable VoiceOver (iOS) or TalkBack (Android emulator)
- Verify `accessibilityRole` on interactive elements
- Verify `accessibilityLabel` on form fields and buttons
- Verify `accessibilityState` (`checked`, `disabled`) on applicable controls
- Verify `accessibilityLiveRegion` on status/error messages
- Verify ~44pt minimum touch targets on all interactive elements

---

## 5. Platform Validation Matrix

### iOS (Matthew's physical iPhone via TestFlight)

| Scenario | Platform | Device | Status |
| :--- | :--- | :--- | :--- |
| Sign in / sign out | iOS | Matthew's iPhone | Pending Matthew confirmation |
| Navigation / tab switching | iOS | Matthew's iPhone | Pending Matthew confirmation |
| My Pets read-only view | iOS | Matthew's iPhone | Pending Matthew confirmation |
| My Pets edit mode (no Save) | iOS | Matthew's iPhone | Pending Matthew confirmation |
| Intake wizard all steps (no Submit) | iOS | Matthew's iPhone | Pending Matthew confirmation |
| Bookings / status badges | iOS | Matthew's iPhone | Pending Matthew confirmation |
| Visual quality (radii, tokens) | iOS | Matthew's iPhone | Pending Matthew confirmation |
| Accessibility (VoiceOver) | iOS | Matthew's iPhone | Pending Matthew confirmation |

**iOS Classification:** `IOS_NONWRITE_SMOKE_PENDING` (awaiting Matthew hands-on confirmation)

### Android Emulator (Android Studio)

| Scenario | Platform | Device | Status |
| :--- | :--- | :--- | :--- |
| App launches, initial runtime check | Android | Android Studio Emulator | `PASS` — Matthew confirmed successful install and visual check |

**Android Emulator Classification:** `ANDROID_EMULATOR_SMOKE_PASS` (initial runtime check; full scenario matrix pending)

**Android Physical Device Classification:** `ANDROID_PHYSICAL_DEVICE_PENDING`

> Physical Android validation requires testing on a real Android phone/tablet (not Windows PC / Google Play Games). This remains a release-readiness limitation before broader Android distribution.

---

## 6. Scenarios Requiring Matthew Manual Confirmation

Return this checklist to Matthew for hands-on confirmation on both platforms:

```
iOS TestFlight (Build 1.0.0 (5)) — Physical iPhone
[ ] 1. Sign in successfully
[ ] 2. Navigate between Bookings / My Pets tabs
[ ] 3. My Pets list loads and shows pet(s)
[ ] 4. Open pet detail — all fields visible
[ ] 5. Enter edit mode — all 10 fields pre-populate
[ ] 6. Modify a field — character limit enforced
[ ] 7. Tap Cancel — discard alert appears → Confirm discard
[ ] 8. Tap "+ Book Care" — intake wizard opens
[ ] 9. Navigate Step 1 (service) → Step 2 (date/window) → Step 3 (pets)
[ ] 10. Reach review screen — all selections shown
[ ] 11. Tap back/cancel — wizard exits without submitting
[ ] 12. Bookings screen — status labels render correctly
[ ] 13. Visual quality — correct border radii, white tokens visible
[ ] 14. Keyboard behavior — forms scroll correctly when keyboard open

Android Internal Testing (versionCode 3) — Physical Android device (if available)
[ ] 1-14 as above (same scenarios)
```

---

## 7. Production Write Boundary Confirmation

- `PUT /client/pets/{petId}` — **NOT EXECUTED**
- `POST /client/requests` — **NOT EXECUTED**
- No production pet records modified
- No care requests created
- No operational data changed

---

## 8. Governance

- **Ryan:** PAUSED — not added to any tester group
- **Public Release:** DEFERRED & UNAPPROVED
- **Google Play Promotion:** Internal Testing ONLY — not promoted
- **Stripe:** Sandbox-only
- **Tenant mode:** DISABLED

---

## 9. Next Steps After This Phase

1. **Phase 24A-9D — Controlled Production-Write Validation**
   - Requires separate explicit Matthew approval
   - Authorizes: pet edit Save + care-request Submit with real production data
2. **Phase 24A-9E — Internal Tester Expansion**
   - Requires separate explicit Matthew approval
   - Adds Ernest (or other approved testers) to TestFlight + Play Internal Testing
