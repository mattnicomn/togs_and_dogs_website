# Release 15I: Ryan External TestFlight Metadata Draft

**Status:** Draft — Awaiting Matthew Decisions
**Priority:** Medium (required before Apple Beta App Review)
**Risk to Production:** None (planning/draft only)
**Terraform Required:** No
**Code Changes:** None
**Scope:** Draft Apple Beta App Review metadata and Ryan tester instructions

---

## 1. Testing Purpose

Ryan will validate the real-world pet sitting staff workflow on an actual iOS device, confirming:
- Daily schedule visibility and accuracy
- Visit detail access (client info, pet care instructions, timing)
- Visit completion and notes functionality
- Payment status visibility (read-only, informational only)
- Overall app stability during normal staff operations

**Ryan's recommended role:** Staff

**What Ryan will NOT test:**
- Live payments (sandbox-only, not enabled on mobile)
- Admin actions (approve/reject/assign)
- Payment link generation or email sending
- Client onboarding or Cognito management

---

## 2. Apple Beta App Review — Draft Test Instructions

### App Description (for reviewer)

```
Tog & Dogs is a pet care business management app for scheduling, tracking, and
coordinating pet sitting visits. Staff use the app to view their daily schedule,
access pet care instructions, mark visits as completed, and record visit notes.
Admins manage bookings, assign staff, and oversee operations.
```

### What to Test (for Apple reviewer)

```
1. Launch the app and log in using the provided demo account credentials.
2. After login, verify the schedule view loads showing assigned visits.
3. Tap any visit to view booking details (client name, pet, service type, dates).
4. Verify pet care instructions are visible in the visit detail.
5. Verify a "Payment Status" badge is visible (read-only informational label).
6. Verify there are NO payment buttons, Stripe links, or payment generation 
   actions anywhere in the app.
7. Navigate back to the schedule and confirm smooth navigation.
8. Log out and confirm return to the login screen.

Note: This app uses Stripe for web-based payment processing, but NO payment 
transactions or in-app purchases occur within the mobile app itself. Payment 
status indicators are read-only labels showing the state of web-processed payments.
No live payments are enabled — the system is in sandbox/test mode.
```

### Demo Account Strategy

| Option | Recommendation |
|--------|---------------|
| Use a dedicated Apple reviewer test account | ✅ Recommended — clean, minimal data |
| Provide credentials in ASC "Test Information" field | ✅ Standard Apple process |
| Do NOT use Matthew's admin account | Avoid exposing admin capabilities |
| Do NOT use real client accounts | Privacy/data protection |

**Matthew must decide:** Create a dedicated reviewer account or use the existing staff test account. Credentials go ONLY in the App Store Connect "Test Information" field (encrypted, Apple-only access).

---

## 3. Draft Ryan Tester Instructions

### Before You Start

1. Install the **TestFlight** app from the App Store (free) if not already installed
2. Accept the TestFlight invitation email from Apple (sent to your Apple ID email)
3. Open TestFlight → find "Tog & Dogs" → tap Install

### First Launch

1. Open the Tog & Dogs app
2. Log in using the credentials Matthew provides (shared securely, outside chat/repo)
3. You should see your daily schedule of assigned visits

### What to Validate

| # | Check | What You Should See |
|---|-------|---------------------|
| 1 | App opens | No crash, login screen appears |
| 2 | Login works | Schedule/daily view loads after sign-in |
| 3 | Today's visits | Your assigned visits for today (if any) |
| 4 | Visit detail | Tap a visit → see client, pet, time, notes |
| 5 | Pet care info | Feeding, medication, behavior notes visible |
| 6 | Payment badge | Small "Paid" or "Unpaid" label (read-only, informational) |
| 7 | No payment buttons | No "Pay Now", "Generate Link", or Stripe buttons anywhere |
| 8 | Mark Complete | Button visible on assigned visits (test with safe data only) |
| 9 | Visit notes | Can type a note (test with safe data only) |
| 10 | No crashes | App stays stable throughout |

### What NOT to Do

- ❌ Do not share login credentials with anyone
- ❌ Do not screenshot and share client contact details publicly
- ❌ Do not mark real client visits as completed unless Matthew approves
- ❌ Do not attempt to find payment/billing controls (they don't exist on mobile)
- ❌ Do not modify client or pet records

### Reporting Issues

If you find a problem:
- Note what screen you were on
- Describe what happened vs what you expected
- Share a screenshot with Matthew directly (redact client details if sharing broadly)
- Include approximate time of the issue

---

## 4. App Store Connect Metadata Checklist

| Field | Draft Value | Status |
|-------|-------------|--------|
| Beta App Description | "Pet care business management app for scheduling and coordinating pet sitting visits." | Draft |
| What to Test | See Section 2 above | Draft |
| Feedback Email | `support@usmissionhero.com` | ✅ Confirmed |
| Marketing URL | `https://toganddogs.usmissionhero.com` | ✅ |
| Privacy Policy URL | `https://toganddogs.usmissionhero.com/privacy` | ✅ |
| Contact First Name | [Matthew — first name only in ASC] | Pending |
| Contact Last Name | [Matthew — last name only in ASC] | Pending |
| Contact Email | [Matthew's contact email for Apple] | Pending |
| Contact Phone | [Matthew's phone for Apple] | Pending |
| Demo Account Username | [to be created/confirmed by Matthew] | Pending |
| Demo Account Password | [to be entered ONLY in ASC — never in docs/chat] | Pending |
| Export Compliance | Does the app use encryption? Likely "Yes" (HTTPS/TLS) — standard exemption applies | Verify |
| Review Notes | "No in-app purchases. No live payments. Payment status indicators are read-only labels. Stripe integration is web-only." | Draft |

---

## 5. Export Compliance / Encryption Note

The app uses HTTPS (TLS) for API communication and secure token storage (Expo SecureStore). This typically qualifies for the standard encryption exemption (uses only standard OS-provided encryption, no custom cryptography).

**Matthew should confirm:** When submitting, select "Yes, but only uses standard OS-level encryption" or the equivalent exemption option in ASC.

---

## 6. Required Matthew Decisions

| # | Decision | Options | Default Recommendation |
|---|----------|---------|------------------------|
| 1 | Ryan's Apple ID email | [Matthew collects from Ryan] | — |
| 2 | Ryan's intended test role | Staff / Client / Both | Staff |
| 3 | Demo account for Apple reviewer | New dedicated / existing staff test | Dedicated reviewer account |
| 4 | Demo account credentials | [Create and enter ONLY in ASC] | — |
| 5 | Should Ryan see real client data? | Yes / Sanitized test data | Yes (normal staff workflow) |
| 6 | Contact info for Apple (name/email/phone) | Matthew's details | — |
| 7 | Export compliance answer | Standard exemption | Standard exemption |
| 8 | Test data prep needed? | Create test visits for Ryan / use existing | Use existing if available |

---

## 7. Recommended Next Releases

| Release | Scope | Depends On |
|---------|-------|------------|
| **15J** | Apple Beta App Review submission (enter metadata in ASC, submit build for review) | Matthew decisions above |
| **15K** | Ryan external invitation + first install | Beta Review approved |
| **15L** | Ryan external smoke validation closeout | Ryan tests |

---

## 8. What This Document Does NOT Authorize

- ❌ Entering metadata in App Store Connect
- ❌ Submitting for Apple Beta App Review
- ❌ Creating external tester groups
- ❌ Inviting Ryan
- ❌ Creating Cognito accounts
- ❌ Building or submitting EAS builds
- ❌ Code changes
- ❌ AWS/Terraform/Stripe/DynamoDB changes
- ❌ Sending emails/notifications
- ❌ Committing credentials or Apple IDs

This is a planning/draft document only. Apple Beta App Review submission (15J) requires Matthew's explicit approval after decisions are confirmed.
