# Release 15G: Matthew Multi-Role Internal TestFlight Validation Plan

**Status:** Planning
**Priority:** Medium (completes internal role coverage before External TestFlight)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Matthew validates all app roles (admin, staff, client) using separate known profiles

---

## 1. Why Ernest Internal Testing Is Deferred

| Reason | Detail |
|--------|--------|
| No second person with ASC access | Matthew does not have another individual with Apple Developer / App Store Connect internal tester access |
| Ernest availability | Not available as an internal tester at this time |
| Impact | None — internal validation is not blocked because Matthew can test all roles using separate Cognito accounts |
| Decision | Skip Ernest internal tester path; Matthew covers all roles personally |
| Future | If Ernest or another person gains ASC access later, they can be added as an internal tester at any time without code/build changes |

---

## 2. Matthew Multi-Role Validation Strategy

Matthew tests the app three times using different accounts, one per role:

| Role | Account Type | What to Validate |
|------|--------------|------------------|
| Admin/Owner | Matthew's primary admin Cognito account | Full admin capabilities |
| Staff | Staff test Cognito account | Staff daily workflow |
| Client | Client test Cognito account | Client-facing view |

Each test is done on the same build 1.0.0 (4) via Internal TestFlight on Matthew's device. Log out → log in with different account to switch roles.

---

## 3. Admin/Owner Validation Checklist

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 1 | Login with admin account | Dashboard/request list loads | ___ |
| 2 | Request list displays | Shows bookings with status badges | ___ |
| 3 | Booking detail opens | CareCard or detail view loads | ___ |
| 4 | Payment status badge visible | Shows Paid/Pending/Unpaid as appropriate | ___ |
| 5 | No "Generate Payment Link" button on mobile | Correct — web-only action | ___ |
| 6 | No "Send Payment Email" button on mobile | Correct — web-only action | ___ |
| 7 | Staff assignment UI accessible (if applicable) | Loads without error | ___ |
| 8 | Pet/client details accessible | Names, notes, care instructions visible | ___ |
| 9 | No crashes or errors | Stable | ___ |
| 10 | Logout works | Returns to login screen | ___ |

**Safety note:** Do NOT approve/assign/modify real client bookings during this test unless using clearly marked test data.

---

## 4. Staff Validation Checklist

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 1 | Login with staff account | Schedule/daily view loads | ___ |
| 2 | Today's assigned visits display | Shows relevant visits | ___ |
| 3 | Upcoming visits display | Future schedule visible | ___ |
| 4 | Visit detail opens | Client, pet, time, notes visible | ___ |
| 5 | Payment status shown as read-only | Badge/label present, no action buttons | ___ |
| 6 | Pet care instructions visible | Feeding, medication, behavior notes | ___ |
| 7 | Mark Complete button visible | Appears on assigned visits | ___ |
| 8 | Visit notes input accessible | Can type (do not submit on real visits) | ___ |
| 9 | No admin-only controls visible | No approve/reject/assign/payment generate | ___ |
| 10 | No crashes or errors | Stable | ___ |
| 11 | Logout works | Returns to login screen | ___ |

**Safety note:** Do NOT mark real client visits as completed during this test unless using clearly marked test data.

---

## 5. Client Validation Checklist

| # | Check | Expected | Result |
|---|-------|----------|--------|
| 1 | Login with client account | Client view loads | ___ |
| 2 | Bookings/requests visible | Client's own bookings shown | ___ |
| 3 | Booking detail opens | Service type, dates, status visible | ___ |
| 4 | Payment status visible (if implemented for client view) | Read-only indicator or not shown | ___ |
| 5 | No staff-only controls visible | No mark complete, no schedule view | ___ |
| 6 | No admin controls visible | No approve/reject/assign/payment/staff management | ___ |
| 7 | No Stripe links or payment generation buttons | Client pays via email link only | ___ |
| 8 | Pet details visible (if linked) | Client's own pets shown | ___ |
| 9 | No crashes or errors | Stable | ___ |
| 10 | Logout works | Returns to login screen | ___ |

**Note:** Client mobile view may be limited compared to admin/staff. Document what IS visible and whether it meets expectations.

---

## 6. Evidence Handling

| Item | Rule |
|------|------|
| Screenshots | May be reviewed manually during testing |
| Committing screenshots | ❌ Do not commit unless fully redacted |
| Sensitive data in screenshots | Avoid capturing client emails, phones, addresses, access notes |
| Validation recording method | Fill in checklist above (pass/fail) — no raw screenshots needed |
| If issues found | Describe the issue in text, not with unredacted screenshots |

---

## 7. Test Data Safety

| Rule | Detail |
|------|--------|
| Do not modify real client bookings | Use test/sandbox data for any write actions |
| Do not mark real visits as completed | Only use clearly test bookings |
| Do not approve/reject real requests | Admin actions on test data only |
| Do not generate payment links | Web-only, and not needed for mobile validation |
| Payment status is read-only on mobile | No risk of accidental charges from mobile |

---

## 8. Recommended Follow-Up Releases

| Release | Scope |
|---------|-------|
| **15H** | Matthew multi-role internal TestFlight smoke validation closeout |
| **15I** | Ryan External TestFlight metadata draft (beta test info, demo account) |
| **15J** | Apple Beta App Review submission |
| **15K** | Ryan onboarding — invitation + first external install |
| **15L** | Ryan external smoke validation closeout |

---

## 9. What This Document Does NOT Authorize

- ❌ Running the validation (requires Matthew to manually test)
- ❌ Code changes
- ❌ EAS builds or submissions
- ❌ TestFlight uploads
- ❌ App Store Connect changes
- ❌ Adding/removing testers
- ❌ AWS/Terraform changes
- ❌ Stripe/payment actions
- ❌ DynamoDB/Cognito changes
- ❌ Sending emails
- ❌ Committing screenshots or credentials

This is a planning document only. Matthew executes the validation manually at his discretion.
