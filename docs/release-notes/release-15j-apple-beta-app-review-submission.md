# Release 15J: Apple Beta App Review Submission

**Status:** Submitted — Awaiting Apple Review
**Type:** App Store Connect / TestFlight Beta Review
**Date:** 2026-06-19
**Build:** toganddogs_app_1 1.0.0 (4)

---

## 1. Submission Summary

| Item | Value |
|------|-------|
| Build submitted | 1.0.0 (4) |
| Review type | Apple Beta App Review (External TestFlight) |
| Submitted by | Matthew (manually in App Store Connect) |
| Expected review time | ~24–48 hours |
| Purpose | Enable external TestFlight distribution to Ryan (staff tester) |

---

## 2. Beta App Review Metadata Entered

| Field | Value |
|-------|-------|
| Beta App Description | Pet care business management app for coordinating scheduled pet sitting visits. Staff testers can log in, view assigned visits, review pet care details, see notes and visit windows, and verify read-only payment status indicators. |
| What to Test | Log in with staff demo account → schedule → visit detail → pet/client details → payment badge (read-only) → confirm no payment buttons/Stripe links |
| Feedback Email | support@usmissionhero.com |
| Privacy Policy URL | https://toganddogs.usmissionhero.com/privacy |
| Review Notes | Live payments not enabled. Stripe is web-only and sandbox-only. Mobile payment indicators are informational/read-only labels. |
| Demo Account | Staff test credentials entered in ASC only (not committed/logged) |
| Contact Info | Matthew's details (entered in ASC only) |
| Export Compliance | Standard HTTPS/TLS encryption — no proprietary/non-standard cryptography |

---

## 3. External Testing Group

| Item | Status |
|------|--------|
| External group created | ✅ (e.g., "Staff Testers") |
| Build added to group | ✅ 1.0.0 (4) |
| Ryan added to group | ❌ Not yet — waiting for Beta Review approval |

---

## 4. Security / Credential Handling

| Item | Status |
|------|--------|
| Demo credentials entered only in ASC | ✅ |
| Credentials committed to repo | ❌ No |
| Credentials in chat/logs | ❌ No |
| Credentials in documentation | ❌ No |

---

## 5. What Happens Next

| Scenario | Action |
|----------|--------|
| Apple approves Beta Review | Matthew can add Ryan's Apple ID to the external tester group |
| Apple requests changes | Review feedback, update metadata, resubmit |
| Apple rejects | Investigate reason, fix issues, resubmit |

---

## 6. Remaining Steps After Approval

| Release | Action |
|---------|--------|
| 15K | Add Ryan's Apple ID to External Testing group → Ryan receives TestFlight invitation |
| 15L | Ryan installs, tests staff workflow, reports findings |

---

## 7. What This Release Did NOT Do

- ❌ No code changes
- ❌ No new EAS builds
- ❌ No EAS submit
- ❌ No TestFlight upload (used existing processed build)
- ❌ No Ryan invite (pending approval)
- ❌ No AWS/Terraform changes
- ❌ No Stripe/payment actions
- ❌ No DynamoDB/Cognito changes
- ❌ No credentials committed or exposed
- ❌ No frontend deployment
