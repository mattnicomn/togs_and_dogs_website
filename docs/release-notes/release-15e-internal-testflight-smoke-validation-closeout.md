# Release 15E: Internal TestFlight Smoke Validation Closeout

**Status:** Complete — Passed
**Type:** Validation checkpoint
**Date:** 2026-06-19
**Build:** toganddogs_app_1 1.0.0 (4)
**Tester:** Matthew
**Device:** iPhone 15 Pro
**Role/Path Tested:** Admin + Staff

---

## 1. Build Details

| Item | Value |
|------|-------|
| App | toganddogs_app_1 |
| Version | 1.0.0 |
| Build number | 4 |
| Platform | iOS (TestFlight Internal) |
| Tester | Matthew |
| Device | iPhone 15 Pro |
| Distribution | Internal TestFlight |

---

## 2. Manual Validation Checklist

| # | Check | Result |
|---|-------|--------|
| 1 | App opened without crash | ✅ Pass |
| 2 | Login worked (Cognito auth) | ✅ Pass |
| 3 | Schedule loaded (daily view) | ✅ Pass |
| 4 | Request detail loaded | ✅ Pass |
| 5 | Payment status visible on schedule | ✅ Pass |
| 6 | Payment badge visible on request detail | ✅ Pass |
| 7 | No mobile payment actions/links present | ✅ Pass (correct — web-only) |
| 8 | Pet/client details displayed | ✅ Pass |
| 9 | Notes/visit details displayed | ✅ Pass |
| 10 | Crashes or errors observed | ❌ None |

**Overall Result: ✅ PASS**

---

## 3. Payment Status Visibility Confirmed

Screenshots (reviewed manually, not committed) confirmed:

- Admin booking detail showing **"Payment Status: Paid"** badge
- Staff booking detail showing **"Payment Status: Unpaid / Not Set"** (informational only)
- No mobile payment action buttons or Stripe links visible on any screen
- Payment status is read-only on mobile as designed

---

## 4. Screenshot Evidence Handling

| Item | Status |
|------|--------|
| Screenshots reviewed | ✅ Manually by Matthew |
| Screenshots committed to repo | ❌ No — contain visible client contact details |
| Sensitive data in screenshots | Client emails, phone numbers, access notes visible |
| Redaction required before committing | Yes, if ever needed |
| Decision | Do not commit; validation confirmed verbally |

---

## 5. Remaining Tester Items

| Item | Status | Next Step |
|------|--------|-----------|
| Matthew (Internal TestFlight) | ✅ Active, validated | Done |
| Ernest (Internal TestFlight) | ⏳ Unknown | Confirm ASC access, add if available |
| Ryan (External TestFlight) | ❌ Not added | Requires Apple Beta App Review submission |

---

## 6. Recommended Next Release

**15F — Ernest Internal Tester Confirmation and Ryan External TestFlight Readiness Plan**

Scope:
- Confirm whether Ernest has App Store Connect access
- If yes, add as Internal tester (no Apple review needed)
- Plan Ryan's External TestFlight setup:
  - Apple Beta App Review submission
  - Metadata/screenshots preparation
  - Test account for Apple reviewer
  - Ryan's Apple ID collection
- Define Ryan validation checklist

---

## 7. What This Release Does NOT Do

- ❌ No code changes
- ❌ No new builds
- ❌ No EAS submit
- ❌ No TestFlight uploads
- ❌ No App Store Connect changes
- ❌ No external testers added
- ❌ No Stripe/payment actions
- ❌ No AWS/Terraform changes
- ❌ No DynamoDB/Cognito changes
- ❌ No screenshots committed
