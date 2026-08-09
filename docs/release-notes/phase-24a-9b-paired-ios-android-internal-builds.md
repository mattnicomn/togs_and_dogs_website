# Phase 24A-9B: Paired iOS + Android Internal Builds Release Notes

## 1. Executive Summary & Status

- **Status:** **PHASE 24A-9B LOCALLY COMPLETE / PAIRED IOS + ANDROID ARTIFACTS SUCCESSFULLY CREATED / IOS TESTFLIGHT SUBMITTED / ANDROID SIGNED AAB CREATED (STORE UPLOAD HELD) / ZERO PUBLIC RELEASE / ZERO PRODUCTION WRITES / AWAITING PHASE 24A-9B.4 GOOGLE PLAY SETUP**
- **Date:** 2026-08-09
- **Authoritative Git Source SHA:** `8a1ce46c0a8bd0d02f4000188b21e115b370281c` (main branch)
- **Shared Marketing Version:** `1.0.0`
- **Purpose:** Execute paired remote EAS builds for iOS and Android from the identical source Git commit, establishing the first synchronized cross-platform mobile release package for Togs & Dogs.

---

## 2. Paired Release Identity Record

```
================================================================================
TOGS & DOGS MOBILE PAIRED RELEASE RECORD
================================================================================
Release Title:          Phase 24A Internal Preview (v1.0.0)
Git Source Commit SHA:  8a1ce46c0a8bd0d02f4000188b21e115b370281c
Shared App Version:     1.0.0
--------------------------------------------------------------------------------
iOS Artifact:
  - EAS Build ID:        c7b7d9da-056b-45a8-86cd-cd6882969464
  - iOS buildNumber:     5  (Version: 1.0.0 (5))
  - Build Status:        SUCCESS
  - IPA Artifact:        https://expo.dev/artifacts/eas/Z-btZD6g2wpc5OCYH5fD1OBg4OyTxtUMxfCZoL3leVM.ipa
  - EAS Submission ID:   fe722283-3205-4a87-8d9a-40162407966c
  - Submission Status:   SUCCESS (Submitted to Apple App Store Connect)
  - TestFlight URL:      https://appstoreconnect.apple.com/apps/6778488478/testflight/ios
  - Classification:      IOS_BUILD_AND_TESTFLIGHT_SUBMISSION_SUCCESS

Android Artifact:
  - EAS Build ID:        e2bc9a1d-666b-4698-882f-6aa7ba7c2132
  - Android versionCode: 3  (Version: 1.0.0, versionCode 3)
  - Build Status:        SUCCESS
  - AAB Artifact:        https://expo.dev/artifacts/eas/1w6wvegHq5Dxk4ubgdbQBzAFtbDIUDOeMcJgA8Bcc7U.aab
  - Google Play Upload:  HELD (Pending Phase 24A-9B.4 setup)
  - Classification:      ANDROID_AAB_BUILD_SUCCESS

Paired Result:           EXACT SOURCE REVISION MATCH (8a1ce46c0a8bd0d02f4000188b21e115b370281c)
Paired Classification:   PAIRED_ARTIFACTS_READY
================================================================================
```

---

## 3. Permanent Paired Release Policy

Every approved Togs & Dogs mobile release adheres to the following rules:
1. **Identical Git SHA:** iOS and Android build artifacts must originate from the exact same Git commit.
2. **Shared Marketing Version:** Both platforms use the exact same marketing version (`version` in `app.json`, e.g. `1.0.0`).
3. **Independent Monotonic Build Numbers:** Platform build numbers increment independently on remote EAS servers (`buildNumber` `5` for iOS vs `versionCode` `3` for Android). They are NOT required to match numerically; canonical pairing is established via the shared Git SHA and marketing version.
4. **Shared Codebase & Contracts:** Both binaries use identical React Native application code, contract definitions (`generatedContracts.ts`), and design tokens (`generatedColors.ts`).
5. **Separately Gated Promotion:** Artifact creation does not trigger store promotion or public publishing.

---

## 4. Pre-Build Validation Summary

- **TypeScript Compilation:** 0 errors (`npm run typecheck --prefix mobile`).
- **Shared Constants:** 18/18 passed (`node shared/validate-constants.mjs`).
- **Shared Contract Adapters:** 9/9 passed (`node shared/validate-contract-adapters.mjs`).
- **Backend Customer Pet Tests:** 18/18 passed (`pytest tests/backend/test_phase1b5c_customer_pet_editing.py`).
- **Backend Request Status Parity:** 13/13 passed (`pytest tests/backend/test_phase24a_request_status_contract_parity.py`).
- **Full Mobile Jest Suite:** 104/104 passed across 10 suites (`npm test --prefix mobile`).
- **Git Diff Line Check:** Clean (`git diff --check`).

---

## 5. Environment & Production Write Safety Boundary

- **Active Environment Target (`mobile/src/api/config.ts`):** Live production API Gateway (`https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod`) and production Cognito User Pool (`us-east-1_counlsXGU`).
- **Safe Non-Write Validation (Authorized for initial preview):**
  - Sign in, navigate tabs, view My Pets read-only detail.
  - Enter pet edit mode, pre-populate fields, test character limits, test Cancel/Discard dialogs.
  - Navigate 3-step Care Request Intake Wizard, select service/dates/pets, view review screen.
  - Test screen-reader accessibility (VoiceOver / TalkBack), 44pt touch targets, 8px/12px UI radii.
- **Production Write Approval Boundary (Requires explicit separate approval):**
  - Tapping `Save Changes` on pet profile edit (`PUT /client/pets/{petId}`).
  - Tapping `Submit Care Request` on Step 3 of Intake Wizard (`POST /client/requests`).

---

## 6. Governance & Roadmap Status

- **Public Store Release:** **DEFERRED & UNAPPROVED**.
- **Ryan Testing:** **PAUSED**.
- **Stripe Payments:** **SANDBOX-ONLY**.
- **Multi-Tenant Mode:** **DISABLED**.
- **Latest Validated Production Baseline:** **Phase 1B.5C-D.2**.

### Subphase Status Matrix
- **Phase 24A-9A (Pipeline Assessment & Preparation):** ✅ COMPLETE
- **Phase 24A-9B (Paired iOS + Android Build Execution):** ✅ COMPLETE (`PAIRED_ARTIFACTS_READY`)
- **Phase 24A-9B.4 (Google Play Internal Testing Setup & Android AAB Submission):** ⏳ NEXT
- **Phase 24A-9C (Cross-Platform Non-Write Physical Device Smoke Validation):** ⏳ PENDING
- **Phase 24A-9D (Controlled Production-Write Validation):** ⏳ PENDING SEPARATE APPROVAL
- **Phase 24A-9E (Internal Tester Scope Expansion):** ⏳ PENDING SEPARATE APPROVAL
