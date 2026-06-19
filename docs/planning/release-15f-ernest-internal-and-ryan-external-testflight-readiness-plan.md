# Release 15F: Ernest Internal Tester Confirmation and Ryan External TestFlight Readiness Plan

**Status:** Planning
**Priority:** Medium (enables broader testing coverage)
**Risk to Production:** None (planning only)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Plan Ernest's internal tester setup and Ryan's external TestFlight readiness

---

## 1. Ernest — Internal Tester Readiness

### What "Internal Tester" Means

- Internal TestFlight testers are App Store Connect users with a role (Admin, Developer, Marketing, etc.)
- They can install any uploaded build without Apple Beta App Review
- Limited to 100 internal testers per app
- Requires an Apple ID that is also an ASC team member

### Checklist for Matthew

| # | Check / Action | Status | Notes |
|---|----------------|--------|-------|
| 1 | Does Ernest have an Apple ID? | ___ | Required for TestFlight |
| 2 | Is Ernest already a user in App Store Connect? | ___ | Check ASC → Users and Access |
| 3 | If not, invite Ernest to ASC team | ___ | Role: Developer or Marketing (minimal access) |
| 4 | Ernest accepts ASC invitation | ___ | Must click email link + sign in |
| 5 | Add Ernest to Internal Testing group in TestFlight | ___ | ASC → App → TestFlight → Internal Testing |
| 6 | Ernest installs TestFlight app (if not already) | ___ | Free from App Store |
| 7 | Ernest sees build 1.0.0 (4) in TestFlight and installs | ___ | Automatic after step 5 |

### Ernest Smoke Test Checklist (After Install)

| # | Check | Expected |
|---|-------|----------|
| 1 | App opens without crash | ✅ |
| 2 | Login works with Ernest's Cognito account | ✅ |
| 3 | Appropriate role view loads (admin/staff/client depending on Ernest's role) | ✅ |
| 4 | Schedule or request list loads | ✅ |
| 5 | No crashes or errors | ✅ |

### Open Decision: Ernest's Role

| Question | Options | Matthew Decides |
|----------|---------|-----------------|
| What Cognito role does Ernest have? | admin / staff / client | ___ |
| What should Ernest test? | Full admin flow / staff workflow / client view | ___ |
| Does Ernest need a test account created? | Yes / No (existing account) | ___ |

---

## 2. Ryan — External TestFlight Readiness

### What "External Tester" Means

- External TestFlight testers do NOT need App Store Connect access
- They are invited by email (Apple ID required)
- Requires Apple Beta App Review before the first build can be distributed
- Beta App Review typically takes 24–48 hours
- Up to 10,000 external testers per app

### Prerequisites Before Adding Ryan

| # | Requirement | Status | Notes |
|---|-------------|--------|-------|
| 1 | Build uploaded and processed in ASC | ✅ | 1.0.0 (4) |
| 2 | Beta App Review submitted and approved | ❌ | Not yet submitted |
| 3 | Beta test information filled in | ❌ | Required for submission |
| 4 | External Testing group created | ❌ | Not yet created |
| 5 | Ryan's Apple ID collected | ❌ | Matthew must confirm |
| 6 | Ryan invited to External Testing group | ❌ | After review approval |

### Apple Beta App Review — Required Metadata

| Field | Recommended Value | Status |
|-------|-------------------|--------|
| What to Test | "Test the staff daily schedule, visit completion, and client/pet details views. Payment indicators are read-only (sandbox mode)." | ___ |
| App Description | "Pet care business management app for Tog & Dogs. Manage bookings, schedule visits, track pet details, and coordinate staff." | ___ |
| Feedback Email | Matthew's email or support address | ___ |
| Marketing URL (optional) | `https://toganddogs.usmissionhero.com` | ___ |
| Privacy Policy URL | `https://toganddogs.usmissionhero.com/privacy` | ___ |
| Contact Info | Matthew's name + email (for Apple reviewer) | ___ |
| Demo Account | Required if app has login — provide test credentials for Apple reviewer | ⚠️ Must create/identify |

### Demo Account for Apple Reviewer

Apple requires a working test account to review the app. Options:

| Option | Pros | Cons |
|--------|------|------|
| A: Use existing staff test account (mattnicomn10@yahoo.com) | Already exists, known working | Reviewer sees real-ish data |
| B: Create a dedicated Apple reviewer account | Clean, minimal data | Extra Cognito account to manage |
| C: Provide Matthew admin account credentials | Full access | Exposes admin capabilities |

**Recommendation:** Option A (existing staff test account) or Option B (dedicated reviewer account). Do NOT expose admin credentials to Apple.

### Ryan's Intended Test Role

| Question | Options | Matthew Decides |
|----------|---------|-----------------|
| What role should Ryan test? | staff (primary use case) / admin / both | ___ |
| Does Ryan have a Cognito account? | Yes / needs creation | ___ |
| Should Ryan see real client data? | Yes (production-like) / No (sanitized test data) | ___ |
| Should Ryan see payment status badges? | Yes (read-only, informational) / No | ___ |

**Recommendation:** Ryan tests as **staff** — this is her primary workflow (daily schedule, visit completion, notes). Payment status is visible as read-only indicator. No payment actions available from mobile.

---

## 3. External Tester Safety

### What Ryan SHOULD Be Able to Do

- View daily schedule of assigned visits
- View visit details (client, pet, address, time, notes)
- Mark visits as completed
- Add visit notes
- See payment status badges (read-only)
- View pet care instructions

### What Ryan Should NOT Be Able to Do

- Generate payment links (web-only, admin-only)
- Send payment emails (web-only, admin-only)
- Approve/reject booking requests (admin-only)
- Manage staff/clients (admin-only)
- Access Stripe Dashboard or payment configuration
- See raw request IDs, Stripe session IDs, or technical identifiers

### Data Considerations

| Question | Recommendation |
|----------|---------------|
| Should Ryan see real client names/contacts? | If Ryan is the actual staff provider, yes — this is her normal workflow |
| Should test/dummy data be created for Ryan? | Not necessary if Ryan is testing her own assigned visits |
| Should completed visits from sandbox testing be cleaned up? | Optional — mark as test if visible |

---

## 4. Recommended Follow-Up Releases

| Release | Scope | Requires |
|---------|-------|----------|
| **15G** | Ernest internal tester confirmation (Matthew manual setup) | Matthew action in ASC |
| **15H** | Ryan External TestFlight metadata draft (beta test info, demo account) | Matthew decisions above |
| **15I** | Apple Beta App Review submission | Build + metadata complete |
| **15J** | Ryan onboarding — invitation + first install | Beta Review approved |
| **15K** | Ryan External smoke validation closeout | Ryan tests + feedback |

---

## 5. Manual Decisions for Matthew

| # | Decision | Options | Default Recommendation |
|---|----------|---------|------------------------|
| 1 | Ernest's Apple ID/email for ASC | [to be provided] | — |
| 2 | Ernest's ASC role | Developer / Marketing / App Manager | Developer |
| 3 | Ernest's Cognito role for testing | admin / staff / client | Staff |
| 4 | Ryan's Apple ID/email for External TestFlight | [to be provided] | — |
| 5 | Ryan's intended test role | staff / admin / both | Staff |
| 6 | Demo account for Apple reviewer | Existing staff test / new dedicated / admin | Existing staff test |
| 7 | Should Ryan see real client data? | Yes / sanitized | Yes (normal staff workflow) |
| 8 | Should payment badges be visible to Ryan? | Yes (read-only) / hidden | Yes (read-only) |

---

## 6. Risks and Blockers

| Risk | Impact | Mitigation |
|------|--------|------------|
| Ernest doesn't have an Apple ID | Cannot be added as internal tester | Ernest creates Apple ID first |
| Apple Beta App Review rejected | Cannot add Ryan | Ensure metadata/demo account are correct; resubmit |
| Ryan's Apple ID unknown | Cannot invite | Matthew collects from Ryan |
| Ryan unavailable for testing | Cannot validate staff workflow | Schedule testing window |
| Demo account credentials exposed | Security concern | Use a dedicated test account, not admin |
| Build is stale by time Ryan tests | May miss recent fixes | Build fresh before Ryan invite if significant changes |

---

## 7. What This Document Does NOT Authorize

- ❌ Adding testers to App Store Connect
- ❌ Creating external testing groups
- ❌ Submitting for Apple Beta App Review
- ❌ Inviting Ryan or Ernest
- ❌ Creating Cognito accounts
- ❌ Building or submitting EAS builds
- ❌ Code changes
- ❌ AWS/Terraform/Stripe/DynamoDB changes
- ❌ Sending emails/notifications
- ❌ Committing credentials or Apple IDs

This is a planning document only. Each follow-up action (15G–15K) requires Matthew's explicit approval.
