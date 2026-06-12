# Release 10I — Internal TestFlight Build for 10H Mobile P0 Fixes

**Status:** ✅ Complete — Build uploaded to App Store Connect / TestFlight  
**Date:** 2026-06-12  
**Scope:** Build and upload of 10H mobile P0 fixes only  
**No app code changes in this release** — code changes were committed in `d43e603` (Release 10H)

---

## Purpose

Release 10I is the build/upload release for the mobile P0 fixes implemented in Release 10H. No new code was written in this release. This document captures the full Gate A (build) and Gate B (submit) execution and outcomes.

---

## Preflight Results

| Check | Result |
|-------|--------|
| `git pull` | ✅ Already up to date |
| Working tree | ✅ Clean — `nothing to commit` |
| HEAD commit | ✅ `d43e603` — 10H fixes confirmed at HEAD |
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
| EAS Build ID | `41d864b5-07c0-49c6-8b7b-69818cfc73d6` |
| EAS Build URL | https://expo.dev/accounts/mattnicomn/projects/tog-and-dogs/builds/41d864b5-07c0-49c6-8b7b-69818cfc73d6 |
| IPA Artifact | https://expo.dev/artifacts/eas/HrOTr4YKkIu_ylDPJA9tdNG4n5tqTLXHgZeMAQBbd_0.ipa |
| App Version | `1.0.0` |
| Build Number | `2` (auto-incremented from 1 → 2 on EAS remote) |
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
eas submit --platform ios --id 41d864b5-07c0-49c6-8b7b-69818cfc73d6 --non-interactive
```

**Result: ✅ SUCCESS — Binary successfully uploaded to Apple App Store Connect**

| Field | Value |
|-------|-------|
| EAS Submission ID | `78a5c652-1f65-45b3-9cf2-a402967e9365` |
| EAS Submission URL | https://expo.dev/accounts/mattnicomn/projects/tog-and-dogs/submissions/78a5c652-1f65-45b3-9cf2-a402967e9365 |
| ASC API Key Name | `[Expo] EAS Submit aOSjD1M6Ph` |
| ASC API Key ID | `2JDRC3Z2D8` |
| ASC API Key Source | EAS servers (configured during 10E Gate B) |
| ASC App ID | `6778488478` |
| Project ID | `6b77d541-ec62-4950-8375-aef7d21c12ea` |
| TestFlight URL | https://appstoreconnect.apple.com/apps/6778488478/testflight/ios |
| App Version | `1.0.0` |
| Build Number | `2` |

---

## What Is In This Build

The following 10H P0 fixes are included in `1.0.0 (2)`:

| Fix | File(s) |
|-----|---------|
| Login error — user-friendly messages via `getFriendlyAuthError()` | `LoginScreen.tsx` |
| Forgot password — full send-code + reset flow | `LoginScreen.tsx`, `cognito.ts` |
| Admin welcome header — `"Welcome back, Ryan"` → dynamic email prefix | `DashboardScreen.tsx` |
| Admin web-only features notice card (Calendar / user mgmt deferred) | `DashboardScreen.tsx` |
| Client bookings — real `/client/requests` fetch replacing placeholder | `BookingsScreen.tsx`, `api/client.ts` |

Source commit: `d43e603` — `feat(mobile): release 10h p0 auth, client appointments, and welcome header fixes`

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
| No new features outside 10H scope implemented | ✅ Confirmed |

---

## Gate C — Internal TestFlight Validation Results

**Build tested:** `1.0.0 (2)`  
**Device:** iPhone 15 Pro  
**Tester:** Matthew  
**Date:** 2026-06-12

| Test | Result | Notes |
|------|--------|-------|
| Wrong-password error visibility | ❌ **FAIL** | Entering a wrong password resets the form to blank email/password with no error message visible. Root cause identified — see Release 10J. |
| Forgot password flow | ✅ Pass | Flow works correctly end-to-end |
| Client appointments (`brearockwell@gmail.com`) | ✅ Pass | Visits now show correctly in the Bookings tab |
| Admin welcome header | ✅ Pass | Correct user name shown, no longer hardcoded "Ryan" |
| Staff user regression (`mattnicomn10@yahoo.com`) | ✅ Pass | Staff user schedule and login working correctly |

### Remaining Issue — Login Error Visibility

**Symptom:** Entering a wrong password causes the login form to silently reset to blank fields with no error message.  
**Root cause:** Identified and fixed in Release 10J. See `docs/release-notes/release-10j-mobile-login-error-visibility-fix.md`.  
**Status:** Fix implemented and pushed. New TestFlight build required.

---

## Files Changed in This Release (10I)

This release is **docs-only** — no app code was changed. All 10H code changes were committed in `d43e603`.

| File | Change |
|------|--------|
| `docs/release-notes/release-10i-internal-testflight-build-for-10h-fixes.md` | [NEW] This document |
