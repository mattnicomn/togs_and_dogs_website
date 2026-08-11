# Phase 24A-9C: Cross-Platform Physical Device Smoke Validation

## 1. Executive Summary & Status

- **Status:** **PHASE 24A-9C ACTIVE / IOS PHYSICAL DEFECTS FOUND / PHASE 24A-9C.1 REMEDIATED LOCALLY / CORRECTED PAIRED ARTIFACTS REQUIRED / PHYSICAL IOS AND ANDROID REVALIDATION PENDING**
- **Date:** 2026-08-09 (started), updated 2026-08-10 — ongoing through corrected-build physical revalidation
- **Source SHA for both builds:** `8a1ce46c0a8bd0d02f4000188b21e115b370281c`
- **Corrected remediation SHA:** `2c3e22a95e0062bed5e40f42e39e4669f94a1d43`

---

## 2. Build Targets for This Validation

| Platform | Version | Build Identifier | Distribution Channel |
| :--- | :--- | :--- | :--- |
| **iOS** | `1.0.0` | Build 5 — EAS `c7b7d9da-056b-45a8-86cd-cd6882969464` | TestFlight (Matthew-only) |
| **Android** | `1.0.0` | versionCode 3 — EAS `e2bc9a1d-666b-4698-882f-6aa7ba7c2132` | Google Play Internal Testing (Matthew-only) |

---

## 3. Original Production Write Safety Boundary and Actual History

The original plan did not authorize the following actions:

| Action | Endpoint | Status |
| :--- | :--- | :--- |
| Pet Profile Edit Save | `PUT /client/pets/{petId}` | **EXECUTED ONCE BY MATTHEW DURING USER TESTING** |
| Care Request Submit | `POST /client/requests` | **EXECUTED ONCE BY MATTHEW DURING USER TESTING** |

This documentation corrects the earlier planned-state record. These were user-performed production actions, not agent actions. Agents did not repeat the writes or query production records during remediation or closeout. Future corrected-build revalidation must avoid both writes.

---

## 4. Original Planned Non-Write Smoke Scenarios

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
| Sign in / sign out | iOS | Matthew's iPhone | `PASS` |
| Navigation / tab switching | iOS | Matthew's iPhone | `PARTIAL PASS` — success-screen Bookings CTA failed |
| My Pets read-only view | iOS | Matthew's iPhone | `PARTIAL PASS` — list and other profiles worked; one profile crashed |
| My Pets edit mode | iOS | Matthew's iPhone | `PARTIAL PASS` — edit/cancel and one user Save worked; keyboard obscured lower fields |
| Intake wizard | iOS | Matthew's iPhone | `PARTIAL PASS` — request submission and success screen worked; keyboard obscured lower fields |
| Bookings / status badges | iOS | Matthew's iPhone | `PASS` — list/status rendering observed |
| Visual quality (radii, tokens) | iOS | Matthew's iPhone | Pending corrected-build confirmation |
| Accessibility (VoiceOver) | iOS | Matthew's iPhone | Pending corrected-build confirmation |

**iOS Classification:** `IOS_PHYSICAL_DEFECTS_FOUND_REMEDIATED_LOCALLY_REBUILD_REQUIRED`

The three findings and their local remediation are recorded in `phase-24a-9c1-ios-physical-smoke-defect-remediation.md`.

### Android Emulator (Android Studio)

| Scenario | Platform | Device | Status |
| :--- | :--- | :--- | :--- |
| App launches, initial runtime check | Android | Android Studio Emulator | `PASS` — Matthew confirmed successful install and visual check |

**Android Emulator Classification:** `ANDROID_EMULATOR_SMOKE_PASS` (initial runtime check; full scenario matrix pending)

**Android Physical Device Classification:** `ANDROID_PHYSICAL_DEVICE_PENDING`

> Physical Android validation requires testing on a real Android phone/tablet (not Windows PC / Google Play Games). This remains a release-readiness limitation before broader Android distribution.

---

## 6. Scenarios Requiring Matthew Manual Confirmation

After separately approved paired remediation builds, return this non-write checklist to Matthew for hands-on confirmation:

```
iOS corrected remediation build — Physical iPhone
[ ] 1. Sign in successfully
[ ] 2. Navigate between Bookings / My Pets tabs
[ ] 3. My Pets list loads and shows pet(s)
[ ] 4. Open the previously crashing pet — detail renders without a crash
[ ] 5. Enter edit mode — all 10 fields pre-populate
[ ] 6. Focus and scroll through lower My Pets fields — keyboard does not obscure them
[ ] 7. Modify a field, then Cancel — discard alert appears and no Save occurs
[ ] 8. Tap "+ Book Care" — intake wizard opens
[ ] 9. Navigate Step 1 (service) → Step 2 (date/window) → Step 3 (pets)
[ ] 10. Focus and scroll through lower Intake fields — keyboard does not obscure them
[ ] 11. Reach review, then exit without submitting
[ ] 12. On the existing success path, View My Bookings targets the Bookings tab
[ ] 13. Visual quality — correct border radii, white tokens visible
[ ] 14. General list/detail/edit/cancel/navigation regression checks pass

Android corrected remediation build — Physical Android device (if available)
[ ] 1-14 as above (same scenarios)
```

---

## 7. Production Write History and Revalidation Boundary

- `PUT /client/pets/{petId}` — **executed once by Matthew during user testing**
- `POST /client/requests` — **executed once by Matthew during user testing**
- Agents did not perform or repeat either write and did not query the resulting records.
- Corrected-build revalidation does not require another pet Save or request Submit.

---

## 8. Governance

- **Ryan:** PAUSED — not added to any tester group
- **Public Release:** DEFERRED & UNAPPROVED
- **Google Play Promotion:** Internal Testing ONLY — not promoted
- **Stripe:** Sandbox-only
- **Tenant mode:** DISABLED

---

## 9. Next Steps

1. **Paired remediation builds from the corrected SHA**
   - Requires separate explicit Matthew approval
   - Build iOS and Android from `2c3e22a95e0062bed5e40f42e39e4669f94a1d43`
   - Preserve paired-source discipline; remote build identifiers remain provisional until EAS reports them
2. **Physical corrected-build revalidation**
   - Revalidate the three fixes without another production pet Save or care-request Submit
   - Complete physical Android validation when a device is available
3. **Phase 24A-9D — Any additional controlled production-write validation**
   - Remains separately approval-gated and is not implied by this closeout
4. **Phase 24A-9E — Internal Tester Expansion**
   - Requires separate explicit Matthew approval
   - Adds Ernest (or other approved testers) to TestFlight + Play Internal Testing
