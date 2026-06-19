# Release 15H: Matthew Multi-Role Internal TestFlight Smoke Validation Closeout

**Status:** Complete — Passed
**Type:** Validation checkpoint
**Date:** 2026-06-19
**Build:** toganddogs_app_1 1.0.0 (4)
**Tester:** Matthew
**Device:** iPhone 15 Pro
**Roles Tested:** Admin/Owner, Staff, Client/User

---

## 1. Build Details

| Item | Value |
|------|-------|
| App | toganddogs_app_1 |
| Version | 1.0.0 (4) |
| Platform | iOS (Internal TestFlight) |
| Tester | Matthew (sole internal tester) |
| Device | iPhone 15 Pro |
| Roles covered | Admin/Owner, Staff, Client/User |

---

## 2. Admin/Owner Validation

| # | Check | Result |
|---|-------|--------|
| 1 | Login with admin account | ✅ Pass |
| 2 | Request list/dashboard loads | ✅ Pass |
| 3 | Booking detail opens | ✅ Pass |
| 4 | Payment status badge visible | ✅ Pass |
| 5 | No "Generate Payment Link" button on mobile | ✅ Pass (correct — web-only) |
| 6 | No "Send Payment Email" button on mobile | ✅ Pass (correct — web-only) |
| 7 | Pet/client details accessible | ✅ Pass |
| 8 | No crashes or errors | ✅ Pass |

---

## 3. Staff Validation

| # | Check | Result |
|---|-------|--------|
| 1 | Login with staff account | ✅ Pass |
| 2 | Schedule loads | ✅ Pass |
| 3 | Assigned visits display | ✅ Pass |
| 4 | Visit detail opens | ✅ Pass |
| 5 | Payment status shown as read-only | ✅ Pass |
| 6 | Notes and visit details visible | ✅ Pass |
| 7 | Mark Complete button visible | ✅ Pass |
| 8 | No admin-only controls visible | ✅ Pass |
| 9 | No crashes or errors | ✅ Pass |

---

## 4. Client/User Validation

| # | Check | Result |
|---|-------|--------|
| 1 | Login with client account | ✅ Pass |
| 2 | Bookings/requests visible | ✅ Pass |
| 3 | Booking detail opens | ✅ Pass |
| 4 | No admin/staff controls visible | ✅ Pass |
| 5 | No Stripe/payment action buttons | ✅ Pass |
| 6 | No crashes or errors | ✅ Pass |

---

## 5. Overall Result

**✅ ALL ROLES PASSED**

No crashes, no errors, no unintended UI exposure across any role. Payment status badges are read-only and informational on mobile as designed. No payment generation or email actions are present on mobile.

---

## 6. Failures / Gaps

None identified during this validation cycle.

---

## 7. Screenshot/Evidence Handling

| Item | Status |
|------|--------|
| Screenshots reviewed | Manually by Matthew (if taken) |
| Screenshots committed | ❌ No — may contain client contact details |
| Validation method | Checklist pass/fail recorded above |

---

## 8. Remaining External Testing Work

| Item | Status | Next Release |
|------|--------|--------------|
| Ernest internal testing | Deferred (no ASC access available) | N/A |
| Ryan External TestFlight metadata | ❌ Not started | 15I |
| Apple Beta App Review | ❌ Not submitted | 15J |
| Ryan onboarding + install | ❌ Pending review approval | 15K |
| Ryan smoke validation | ❌ Pending install | 15L |

---

## 9. Recommended Next Release

**15I — Ryan External TestFlight Metadata Draft**

Scope:
- Draft beta test information for Apple Beta App Review
- Identify/create demo account for Apple reviewer
- Collect Ryan's Apple ID
- Prepare beta description, test instructions, privacy URL

---

## 10. What This Release Does NOT Do

- ❌ No code changes
- ❌ No new builds
- ❌ No EAS submit
- ❌ No TestFlight uploads
- ❌ No App Store Connect changes
- ❌ No testers added or removed
- ❌ No Apple Beta App Review submitted
- ❌ No Stripe/payment actions
- ❌ No AWS/Terraform changes
- ❌ No DynamoDB/Cognito changes
- ❌ No screenshots committed
