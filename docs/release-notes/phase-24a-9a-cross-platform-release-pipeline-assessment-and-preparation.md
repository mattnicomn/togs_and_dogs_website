# Phase 24A-9A: Cross-Platform Mobile Release Pipeline Assessment & Preparation

## 1. Executive Summary & Status

- **Status:** **PHASE 24A-9A LOCALLY COMPLETE / RELEASE PIPELINE DEFINED / PAIRED IOS + ANDROID RELEASE MODEL ESTABLISHED / NON-WRITE SMOKE MATRIX DOCUMENTED / ZERO BUILD TRIGGERED / AWAITING MATTHEW PAIRED BUILD DECISION**
- **Date:** 2026-08-09
- **Starting Checkpoint:** `60754d97c1f8cd139e81434531500f21abcdb4d5` (main branch)
- **Purpose:** Establish a repeatable paired iOS + Android internal release process for Togs & Dogs mobile apps originating from the same Git commit, same source code, same design tokens/contracts, and same marketing version.

---

## 2. Paired Release Architecture & Identity

### Paired Release Principle
Every future approved mobile release package is built from a single authoritative source commit:
- **One Source Commit:** e.g., `60754d97c1f8cd139e81434531500f21abcdb4d5`
- **Shared Marketing Version:** `1.0.0`
- **iOS Build Number:** Independent integer managed by EAS remote versioning (`1.0.0 (5)`)
- **Android Version Code:** Independent integer managed by EAS remote versioning / Google Play (`1.0.0`, versionCode `5`)
- **Shared Contracts & Tokens:** Reuses `generatedContracts.ts` and `generatedColors.ts`

---

## 3. Recommended Build & Distribution Commands

### iOS Internal Build (TestFlight)
```bash
npx eas-cli build --platform ios --profile production --auto-submit --non-interactive
```
- **Output:** iOS IPA artifact auto-submitted to Apple TestFlight.
- **Apple App ID:** `6778488478` (Team ID `2RA84Y5HZ3`).

### Android Internal Build (AAB)
```bash
npx eas-cli build --platform android --profile production --non-interactive
```
- **Output:** Android `.aab` App Bundle artifact signed by EAS.
- **Package Name:** `com.usmissionhero.toganddogs`.
- **Distribution Track:** Upload to Google Play Console Internal Testing track (or Internal App Sharing for physical device testing).

---

## 4. Environment & Production Write Safety Boundary

- **Active Environment (`mobile/src/api/config.ts`):** Points to live production API Gateway (`https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod`) and production Cognito User Pool (`us-east-1_counlsXGU`).
- **Non-Write Smoke Boundary (Authorized for initial preview):**
  - Sign in, navigate tabs, view My Pets read-only detail.
  - Enter pet edit mode, test inputs/limits, tap Cancel/Discard.
  - Navigate 3-step Care Request Intake Wizard, pick service/dates/pets, view review screen.
  - Test screen-reader accessibility, 44pt touch targets, 8px/12px UI radii.
- **Write Approval Boundary (Requires explicit separate approval):**
  - Tapping `Save Changes` on pet profile edit (`PUT /client/pets/{petId}`).
  - Tapping `Submit Care Request` on Step 3 of Intake Wizard (`POST /client/requests`).

---

## 5. Pipeline Readiness Classifications

- **Cross-Platform Release Pipeline:** **`PIPELINE_READY`**
- **iOS Channel:** **`IOS_BUILD_READY`**
- **Android Build Artifact Creation:** **`ANDROID_BUILD_READY`**
- **Google Play Internal Testing Track:** **`PLAY_INTERNAL_SETUP_REQUIRED`** (Direct CLI submit requires Google Play service account JSON key; manual AAB upload supported immediately)
- **Physical Device Smoke Validation:** **`DEVICE_VALIDATION_READY`**

---

## 6. Next Steps & Approval Boundary

- **Public Store Release:** Deferred & Unapproved.
- **Ryan Testing:** Paused & Unapproved.
- **Next Decision Required:** Matthew explicit decision to run Phase 24A-9B paired EAS builds.
