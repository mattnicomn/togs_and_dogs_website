# Release 10F — Internal TestFlight Mobile Smoke Validation Checklist

This document details the read-only smoke validation plan for verifying the first production iOS TestFlight build on the Tog & Dogs platform. This verification is performed manually by Matthew to confirm that the build launched, authenticated, and rendered the production API data correctly before conducting any mutating tests or adding external testers.

---

## 🛠️ Current State & Scope

- **Build Version:** `1.0.0 (1)`
- **EAS Submission ID:** `95baf1c7-083b-47a3-a59c-87597af7209c`
- **Internal Test Group:** `Togs & Dogs Internal Testers`
- **Device Under Test:** iPhone 15 Pro
- **Environment:** Production (Cognito User Pool, API Gateway, DynamoDB)
- **Scope:** Read-Only Mobile Smoke Validation. **No mutating actions are allowed in this phase.**

> [!WARNING]
> ### ⚠️ Mutating Actions Prohibited
> To prevent unintended impact on live customer records or triggering production side-effects, the following actions **MUST NOT** be performed during this smoke validation:
> - Do not approve any requests.
> - Do not assign staff to requests.
> - Do not complete visits or mark jobs as complete.
> - Do not delete, archive, or purge any records.
> - Do not trigger notifications intentionally.

---

## 📋 Smoke Validation Checklist

### Scenario 1: Launch & Session Persistence
- [ ] **App Launch:** Tap the app icon in TestFlight. Confirm the splash screen displays and the login form loads successfully without any crash.
- [ ] **Visual Layout:** Verify headers, input fields, and login buttons are aligned correctly without clipping or visual defects on the iPhone 15 Pro screen.
- [ ] **Session Re-Entry:** After logging in (Scenario 2), force-close the app completely, then reopen it. Verify you are automatically routed to the Dashboard (bypassing the login screen).

### Scenario 2: Authentication & Session Validation
- [ ] **Staff Login:** Log in using your existing production Staff credentials. Verify authentication succeeds and Cognito tokens are retrieved successfully.
- [ ] **Access Redirection:** Confirm the app successfully navigates to the main Dashboard screen upon successful login.
- [ ] **Validation Failures:** Test entering incorrect login credentials. Verify a clean, user-friendly error message is displayed (no raw API/OAuth error dumps).

### Scenario 3: API Connectivity & Layout Inspection
- [ ] **Dashboard Render:** Verify that the main Schedule/Dashboard screen loads and retrieves production visits/jobs data from the API Gateway.
- [ ] **Loading States:** Confirm that visual loading indicators (spinners or skeletons) appear while fetching data and disappear cleanly when the list renders.
- [ ] **Text & Formatting:** Inspect the layout on iPhone 15 Pro to ensure no label texts, dates, or pet names overlap or are clipped.

### Scenario 4: Request List & Detail Views
- [ ] **Schedule Navigation:** Navigate to the main Schedule list. Verify you can scroll through the list of assigned/scheduled visits.
- [ ] **Detail Inspection:** Tap on a visit or request detail card. Verify the details page/drawer opens smoothly.
- [ ] **Content Accuracy:** Confirm that the pet name, client details, service type, schedule time, and visit notes render correctly as read-only data.
- [ ] **Google Calendar Health Status:** Verify if there is a calendar integration banner or health status visible on the dashboard or settings screen, and ensure it correctly reflects the connection state.

---

## 📊 Smoke Validation Results Table

*Matthew can fill in this table as each test step is performed:*

| Test Step | Description | Pass/Fail | Notes / Observations | Screenshot? |
|-----------|-------------|-----------|----------------------|-------------|
| **1.1 Launch** | App starts and displays login screen without crashing | | | [ ] Yes / [ ] No |
| **1.2 Visuals** | Layout fits the iPhone 15 Pro display size, text is legible | | | [ ] Yes / [ ] No |
| **2.1 Staff Auth** | Cognito login completes using production Staff account | | | [ ] Yes / [ ] No |
| **2.2 Redirection** | App loads Dashboard view after login | | | [ ] Yes / [ ] No |
| **2.3 Failure Msg** | Incorrect password triggers a clean error message | | | [ ] Yes / [ ] No |
| **3.1 API Fetch** | Schedule data successfully loads from the production database | | | [ ] Yes / [ ] No |
| **3.2 Spinner** | Loading states display and dismiss correctly | | | [ ] Yes / [ ] No |
| **4.1 Scroll** | Scroll behavior in the Schedule list is smooth | | | [ ] Yes / [ ] No |
| **4.2 Detail View** | Tapping a card opens the visit detail view cleanly | | | [ ] Yes / [ ] No |
| **4.3 Read-Only** | Details (Pet, Client, Notes, Date) render accurately | | | [ ] Yes / [ ] No |
| **4.4 Health Status** | Calendar integration health banner renders correctly | | | [ ] Yes / [ ] No |
| **5.1 Session Re-Entry** | Re-launching app maintains active login session | | | [ ] Yes / [ ] No |

---

## 🎯 Exit Criteria & Next Steps

This release is successful once all checklist items are marked **PASS** with no observed app crashes or severe layout defects.

On successful exit of the read-only smoke validation phase, Matthew may approve moving to:
1. **Phase 2 (Mutating Validation):** Controlled testing of mutating actions (e.g. completing a designated test visit) using safe test-marked data.
2. **Phase 3 (External Ryan Testing):** Setting up the external TestFlight beta group and submitting the build for Apple's Beta App Review (Gate D) to grant Ryan testing access.
