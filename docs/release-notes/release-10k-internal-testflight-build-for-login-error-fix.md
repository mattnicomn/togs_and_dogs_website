# Release 10K — Internal TestFlight Build for 10J Login Error Fix

**Status:** ✅ Complete — Internal TestFlight Validation Passed  
**Date:** 2026-06-12  
**Scope:** Build and upload of the Release 10J login error visibility fix  
**No app code changes in this release** — code changes were committed and pushed in `7cccc45` (Release 10J)

---

## Purpose

Release 10K is the build/upload release for the mobile login error visibility fix implemented in Release 10J. No new code was written in this release. This document captures the full Gate A (build) and Gate B (submit) execution and outcomes.

---

## Preflight Results

| Check | Result |
|-------|--------|
| `git pull` | ✅ Already up to date |
| Working tree | ✅ Clean — `nothing to commit` |
| HEAD commit | ✅ `39780a5` — 10K planning confirmed |
| `eas.json` parses | ✅ `autoIncrement: true`, `appVersionSource: remote` |
| `npx tsc --noEmit` | ✅ 0 errors |
| `eas whoami` | ✅ `mattnicomn` / `mbn@usmissionhero.com` |

---

## Gate A — iOS Production Build

**Command:**
```bash
cd mobile
eas build --profile production --platform ios --non-interactive
```

**Result: ✅ SUCCESS**

| Field | Value |
|-------|-------|
| EAS Build ID | `fcf2d1a5-ac12-4331-8338-5ebd182e1582` |
| EAS Build URL | https://expo.dev/accounts/mattnicomn/projects/tog-and-dogs/builds/fcf2d1a5-ac12-4331-8338-5ebd182e1582 |
| IPA Artifact | https://expo.dev/artifacts/eas/vctE258q4J6mDM2OWQwhlptWBeZL1R8DEAYo0B-tty4.ipa |
| App Version | `1.0.0` |
| Build Number | `3` (auto-incremented from 2 → 3 on EAS remote) |
| Profile | `production` |
| Platform | `ios` |
| Distribution Cert Serial | `108B3218A8A3DD2A2D2EE05DE705B786` |
| Cert Expiration | June 6, 2027 |
| Provisioning Profile | `DUNAZN76MH` — status `active`, expires June 2027 |
| Apple Team | `2RA84Y5HZ3` (Matthew Nico, Individual) |

**Credentials:** Remote iOS credentials used from Expo server. No new certificates or provisioning profiles were created.

---

## Gate B — Submit to App Store Connect / TestFlight

**Command:**
```bash
eas submit --platform ios --id fcf2d1a5-ac12-4331-8338-5ebd182e1582 --non-interactive
```

**Result: ✅ SUCCESS — Binary successfully uploaded to Apple App Store Connect**

| Field | Value |
|-------|-------|
| EAS Submission ID | `7bc75952-7a59-4ebc-98a9-78d307199487` |
| EAS Submission URL | https://expo.dev/accounts/mattnicomn/projects/tog-and-dogs/submissions/7bc75952-7a59-4ebc-98a9-78d307199487 |
| Alternate Submission ID | `a6106894-4df6-4f53-83b6-67ea208dc671` (scheduled with --no-wait) |
| ASC API Key Name | `[Expo] EAS Submit aOSjD1M6Ph` |
| ASC API Key ID | `2JDRC3Z2D8` |
| ASC API Key Source | EAS servers |
| ASC App ID | `6778488478` |
| Project ID | `6b77d541-ec62-4950-8375-aef7d21c12ea` |
| TestFlight URL | https://appstoreconnect.apple.com/apps/6778488478/testflight/ios |
| App Version | `1.0.0` |
| Build Number | `3` |

---

## What Is In This Build

The following 10J P0 fix is included in `1.0.0 (3)` (rebuilt on top of the 10H fixes in `1.0.0 (2)`):

| Fix | File(s) |
|-----|---------|
| Login error visibility — prevent `LoginScreen` unmounting during active login; preserve email UX and clear password on failure | `AuthContext.tsx`, `LoginScreen.tsx` |

Source commit: `7cccc45` — `feat(mobile): release 10j mobile login error visibility fix`

---

## Guardrail Confirmations

| Guardrail | Status |
|-----------|--------|
| No new testers invited | ✅ Confirmed — no tester changes made |
| No external tester groups created | ✅ Confirmed |
| No external beta review submitted | ✅ Confirmed |
| No public App Store review submitted | ✅ Confirmed |
| No App Store Connect metadata modified | ✅ Confirmed — upload only |
| No new Apple certificates or provisioning profiles created | ✅ Confirmed — existing remote credentials reused |
| No AWS / Terraform / S3 / CloudFront / Cognito / Postmark / Google Calendar changes | ✅ Confirmed |
| No production data modified | ✅ Confirmed |
| No web/backend production changes deployed | ✅ Confirmed |
| No new features outside 10J scope implemented | ✅ Confirmed |

---

## Gate C — Internal TestFlight Validation Results

**Build tested:** `1.0.0 (3)`  
**Device:** iPhone 15 Pro  
**Tester:** Matthew  
**Date:** 2026-06-12  

| Test | Result | Notes |
|------|--------|-------|
| Wrong-password error visibility | ✅ **PASS** | Friendly login error appears as expected. The page no longer resets to blank fields. Email remains populated, password clears. |
| Forgot password flow | ✅ **PASS** | Flow is visible and functions correctly end-to-end. |
| Login regression (Admin) | ✅ **PASS** | Logged in successfully to `mattnicomn10@gmail.com`. |
| Login regression (Client) | ✅ **PASS** | Logged in successfully to `brearockwell@gmail.com`. |
| Login regression (Staff) | ✅ **PASS** | Logged in successfully to `mattnicomn10@yahoo.com`. |
| Client visits (`brearockwell@gmail.com`) | ✅ **PASS** | Visits now show in the client account. |
| Admin welcome header | ✅ **PASS** | Welcome name is fixed and no longer incorrectly shows "Ryan". |
| General app stability | ✅ **PASS** | App launched successfully. No crashes observed. All tested workflows passed. |

### Double Submission Record Note

Release 10K was submitted twice for the same build to ensure scheduling:
* **Main submission:** `7bc75952-7a59-4ebc-98a9-78d307199487`
* **Extra no-wait submission:** `a6106894-4df6-4f53-83b6-67ea208dc671`
No further action was needed since App Store Connect successfully processed build `1.0.0 (3)`.

---

## Files Changed in This Release (10K)

This release is **docs-only** — no app code was changed. All 10J code changes were committed in `7cccc45`.

| File | Change |
|------|--------|
| `docs/release-notes/release-10k-internal-testflight-build-for-login-error-fix.md` | [NEW] This document |
