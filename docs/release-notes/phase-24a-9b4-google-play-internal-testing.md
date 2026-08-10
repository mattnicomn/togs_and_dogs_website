# Phase 24A-9B.4: Google Play Internal Testing Setup & Android AAB Submission

## 1. Executive Summary & Status

- **Status:** **PHASE 24A-9B.4 COMPLETE / ANDROID VERSIONCODE 3 UPLOADED TO GOOGLE PLAY / INTERNAL TESTING RELEASE ACTIVE / `3 (1.0.0)` AVAILABLE TO INTERNAL TESTERS / ANDROID STUDIO EMULATOR RUNTIME CHECK COMPLETE / ZERO PUBLIC RELEASE / ZERO PRODUCTION WRITES / RYAN PAUSED**
- **Date:** 2026-08-09
- **Authoritative Git Source SHA:** `8a1ce46c0a8bd0d02f4000188b21e115b370281c` (main branch)
- **Android Marketing Version:** `1.0.0` / versionCode `3`
- **iOS Paired Build:** `1.0.0 (5)` — TestFlight (unchanged)

---

## 2. Google Play Internal Testing Release Record

```
================================================================================
TOGS & DOGS ANDROID INTERNAL TESTING RELEASE
================================================================================
Package:               com.usmissionhero.toganddogs
EAS Build ID:          e2bc9a1d-666b-4698-882f-6aa7ba7c2132
Marketing Version:     1.0.0
versionCode:           3
Play Console Status:   Latest release: 3 (1.0.0) — Available to internal testers
Source Git SHA:        8a1ce46c0a8bd0d02f4000188b21e115b370281c
Track:                 Internal Testing (ONLY — not Production/Open/Closed)
Paired iOS Build:      1.0.0 (5), EAS c7b7d9da-056b-45a8-86cd-cd6882969464
Pairing Key:           Shared Git SHA + marketing version 1.0.0
================================================================================
```

---

## 3. Upload & Activation Method

- **AAB Source:** EAS-managed artifact from build `e2bc9a1d-666b-4698-882f-6aa7ba7c2132`.
- **Upload Method:** Manual AAB upload via Google Play Console UI (Internal Testing → Create new release).
- **Release Notes (en-US):** `Phase 24A internal preview: adds My Pets viewing and editing, care-request intake, Book Care navigation, visual consistency improvements, and mobile accessibility enhancements. Internal validation build only.`
- **EAS Submit Automation:** NOT used for this release (Google Play service-account JSON not yet configured in `eas.json`). Manual upload is sufficient for internal testing.

---

## 4. Tester Scope

- **Track:** Google Play Internal Testing
- **Initial Scope:** Matthew only (internal validation)
- **Ryan:** PAUSED — not added
- **Ernest:** Not added during this task
- **Public release:** DEFERRED & UNAPPROVED

---

## 5. Android Studio / Emulator Runtime Check

Matthew confirmed Android versionCode 3 (`1.0.0`) was successfully installed and runtime-checked via Android Studio.

- **Classification:** `ANDROID_EMULATOR_SMOKE_CHECK_PASS` — Initial visual runtime check passed.
- **NOT classified as:** Physical Android device validation (which remains pending for Phase 24A-9C).

---

## 6. Play Pipeline Automation Gap (Future Work)

The current release pipeline requires manual AAB upload for Android. To enable fully automated future releases:

1. **Create Google Play Service Account:**
   - Google Play Console → Setup → API access → Link Google Cloud project → Create service account with "Release Manager" role → Download JSON key.
2. **Configure EAS Submit Android profile in `eas.json`:**
   ```json
   "submit": {
     "production": {
       "ios": { ... },
       "android": {
         "track": "internal",
         "serviceAccountKeyPath": "path/to/service-account.json",
         "releaseStatus": "draft"
       }
     }
   }
   ```
3. **Future command:** `npx eas-cli submit --platform android --latest --non-interactive`

This is a future pipeline hardening item. It does NOT block internal validation.

---

## 7. Historical Issue Resolution

| Previous Issue | Root Cause Determined |
| :--- | :--- |
| "Save Changes" grayed out in tester list | Tester email already present — no actual change, Save correctly disabled |
| AAB upload confusion | EAS Submit Android not configured; manual upload was always the correct path |
| Windows 11 desktop incompatibility | Google Play Games on Windows is not Android mobile. The `.aab` binary is valid; Windows desktop is not the correct validation target. Physical Android phone required for full validation. |

---

## 8. Governance

- **Public App Store / Google Play Production:** DEFERRED & UNAPPROVED
- **Closed/Open Testing:** Not used
- **Ryan Testing:** PAUSED
- **Production Backend:** Targeted by both builds (non-write smoke only authorized for Phase 24A-9C)
- **Pet Edit Save (`PUT /client/pets/{petId}`):** NOT executed
- **Care Request Submit (`POST /client/requests`):** NOT executed
- **Stripe:** Sandbox-only
- **Tenant mode:** `TENANT_RESOLUTION_MODE=multi` DISABLED

---

## 9. Phase Roadmap State After This Task

| Subphase | Status |
| :--- | :--- |
| Phase 24A-9A (Pipeline Preparation) | ✅ COMPLETE |
| Phase 24A-9B (Paired Builds) | ✅ COMPLETE (`PAIRED_ARTIFACTS_READY`) |
| Phase 24A-9B.4 (Google Play Internal Testing) | ✅ COMPLETE (`GOOGLE_PLAY_INTERNAL_COMPLETE`) |
| Phase 24A-9C (Non-Write Physical Device Smoke Validation) | 🔄 ACTIVE (iOS TestFlight + Android emulator checked; physical Android pending) |
| Phase 24A-9D (Controlled Production-Write Validation) | ⏳ GATED — requires separate Matthew approval |
| Phase 24A-9E (Tester Expansion) | ⏳ GATED |
| Public Store Release | ⏳ DEFERRED & UNAPPROVED |
