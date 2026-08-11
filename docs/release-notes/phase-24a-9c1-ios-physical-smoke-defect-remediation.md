# Phase 24A-9C.1: iOS Physical Smoke Defect Remediation

## 1. Status

- **Status:** **COMPLETE / INDEPENDENTLY REVIEWED / COMMITTED AND PUSHED / REVALIDATED IN CORRECTED PAIRED RELEASE**
- **Date:** 2026-08-10
- **Corrected source SHA:** `2c3e22a95e0062bed5e40f42e39e4669f94a1d43`
- **Implementation commit:** `fix: resolve mobile physical smoke defects`

Phase 24A-9C.1 is complete. The original local closeout recorded remediation only; corrected iOS Build 6 and Android versionCode 4 were subsequently built from `bf9f80d95c1846f197bab24d96463906bc26bfce`, and Matthew reported that the tested remediation behavior passes on both releases. The Android device type remains unconfirmed.

## 2. Physical iPhone Findings

Matthew's physical-iPhone testing of TestFlight `1.0.0 (5)` found three defects:

1. One pet profile crashed when opened from My Pets.
2. The software keyboard obscured lower fields in My Pets edit and Book Pet Care / Intake.
3. The successful-request screen's **View My Bookings** action did not navigate to Bookings.

The same user-run testing confirmed login, logout, the My Pets list, other pet detail/edit/cancel behavior, intake progression, the request-received screen, and Bookings/status rendering.

## 3. Production-Write History

During physical testing, Matthew successfully exercised:

- a customer pet update; and
- a care-request submission.

These were user-performed production actions, not agent-executed writes. No production pet or request data was queried during remediation, and neither write was repeated during implementation, validation, commit, push, or documentation closeout.

## 4. Remediation

### 4.1 Legacy pet read values

API-read pet fields could contain legacy non-string values while the UI assumed strings and called string methods such as `.trim()`. The mobile read boundary now:

- preserves string values;
- converts finite numeric legacy values to strings;
- converts nullish or malformed values to empty strings before rendering or editing;
- normalizes nested veterinarian fields; and
- preserves the existing allowlisted, string-based customer update payload without returning server-owned fields.

Synthetic regression fixtures cover numeric, nullish, malformed, nested-health, and server-only values without accessing the affected production record.

### 4.2 Keyboard avoidance

My Pets edit and Intake now use built-in React Native keyboard-aware structure:

- iOS `KeyboardAvoidingView` behavior;
- additional scroll-bottom clearance;
- existing safe-area containers;
- keyboard tap handling; and
- unchanged Android-native keyboard behavior.

Jest verifies the structure only. Actual focused-field visibility and scrolling still require physical-device revalidation.

### 4.3 Bookings navigation

`IntakeScreen` belongs to `ClientStack`, while `Bookings` is nested inside `ClientTabs`. The success CTA now targets the actual navigator hierarchy:

`ClientTabs -> Bookings`

Regression coverage verifies `navigation.navigate('ClientTabs', { screen: 'Bookings' })` and rejects the former direct `navigate('Bookings')` call. No navigator-file change was required.

## 5. Implementation Scope

- `mobile/src/screens/MyPetsScreen.tsx`
- `mobile/src/screens/IntakeScreen.tsx`
- `mobile/__tests__/MyPetsScreen.test.tsx`
- `mobile/__tests__/IntakeScreen.test.tsx`

No backend, web, contract, adapter, dependency, build-configuration, or distribution file changed.

## 6. Validation and Independent Review

| Gate | Result |
| :--- | :--- |
| Mobile TypeScript | 0 errors |
| Shared constants | 18/18 |
| Generated adapters | 9/9 |
| Backend customer-pet + request-parity suites | 31/31 |
| Focused My Pets | 29/29 |
| Focused Intake + Bookings | 19/19 |
| Full mobile Jest | 109/109 across 10 suites |
| `git diff --check` | Clean |

Kiro independently returned `IMPLEMENTATION_CORRECT` and `READY_FOR_PHASE_24A_9C_1_COMMIT_DECISION` with no findings.

## 7. Final Revalidation State

- **Phase 24A-9C.1:** `COMPLETE`
- **Phase 24A-9C.2:** `PAIRED_REMEDIATION_BUILDS_COMPLETE`
- **Phase 24A-9C:** `REMEDIATION_REVALIDATION_COMPLETE_PASS`
- **iOS:** Build `1.0.0 (6)` passed physical-iPhone remediation validation.
- **Android:** `1.0.0` versionCode `4` passed remediation validation in the user-reported environment; `ANDROID_PHYSICAL_DEVICE_PENDING` remains because the device type is not established.
- **Public App Store / Google Play production:** unapproved
- **Ryan testing:** paused
- **Phase 24A-9D:** separately gated

The final artifact metadata and validation classifications are recorded in `phase-24a-9c2-paired-remediation-revalidation-closeout.md`. No additional pet save or care-request submission was needed or performed.
