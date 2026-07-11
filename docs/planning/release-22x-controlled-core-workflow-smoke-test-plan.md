# Release 22X: Controlled Core Workflow Smoke Test Plan

**Status:** Planning
**Date:** 2026-07-11
**Priority:** Medium (stability confirmation before new features)
**Scope:** Safe display-only production smoke test that Matthew can run without mutations

---

## 1. Purpose

After Release 22V stabilized the Profile Editor drawer and Client Portal My Bookings display, this plan defines a controlled smoke test Matthew can execute in production to confirm all core workflows render correctly. No data mutations, email sends, account changes, or payment actions are permitted during this test.

---

## 2. Safe Display-Only Smoke Tests

### Area 1: Page Load Checks

| # | Test | URL/Path | Expected Behavior | Pass/Fail | Notes |
|---|------|----------|-------------------|:---------:|-------|
| 1 | Homepage loads | `/` | Marketing page renders, no console errors | ⬜ | |
| 2 | Public intake form loads | `/book` | Step 1 renders with service selection | ⬜ | |
| 3 | Privacy Policy loads | `/privacy` or equivalent | Content renders | ⬜ | |
| 4 | Terms of Service loads | `/terms` or equivalent | Content renders | ⬜ | |
| 5 | Admin portal loads | `/admin` | Dashboard renders after login | ⬜ | |
| 6 | Platform Admin loads | `/platform-admin` | Tenant list renders | ⬜ | |
| 7 | Client portal My Bookings loads | `/my-bookings` | Booking list renders | ⬜ | |

### Area 2: Staff Management & Profile Editor

| # | Test | Expected Behavior | Pass/Fail | Notes |
|---|------|-------------------|:---------:|-------|
| 8 | Staff Management tab loads | Staff cards visible with simplified layout | ⬜ | |
| 9 | Cards show: name, role badge, status, "Manage" button | No inline action buttons on cards | ⬜ | |
| 10 | Click "Manage" → drawer opens from right | Smooth slide-in, no flicker | ⬜ | |
| 11 | No page-level horizontal scrollbar | Body stays within viewport | ⬜ | |
| 12 | Drawer scrolls internally | Long section content scrolls within drawer | ⬜ | |
| 13 | Background does not scroll when drawer is open | Body scroll locked | ⬜ | |
| 14 | Click X → drawer closes cleanly | No visual artifacts | ⬜ | |
| 15 | Click outside drawer → closes | Backdrop click dismisses | ⬜ | |
| 16 | USmissionhero shows "⚠️ Orphaned Login" warning | Banner in Login Identity section | ⬜ | |
| 17 | USmissionhero account security actions disabled/hidden | No Resend Invite, Reset, etc. | ⬜ | |
| 18 | Protected admin (Matthew) shows 🔒 Protected banner | Yellow/amber protected banner | ⬜ | |
| 19 | Protected admin dangerous actions hidden | No Unlink, Delete, Disable visible | ⬜ | |
| 20 | Other staff (e.g., Ryan York) show normal active state | Actions available normally | ⬜ | |

### Area 3: Client Portal My Bookings Display

| # | Test | Expected Behavior | Pass/Fail | Notes |
|---|------|-------------------|:---------:|-------|
| 21 | Booking cards render | Cards with service, dates, status | ⬜ | |
| 22 | Multi-day bookings show date range | e.g., "Sep 15–23, 2026" with "(X days)" badge | ⬜ | |
| 23 | Single-day bookings show single date | No range, just the date | ⬜ | |
| 24 | No timezone-offset errors | Dates not shifted by ±1 day | ⬜ | |
| 25 | All selected visit windows display | Friendly labels (e.g., "Morning", "Afternoon") | ⬜ | |
| 26 | Status badges display correctly | Approved/Pending/Completed/etc. | ⬜ | |

### Area 4: Admin Request List & Queues

| # | Test | Expected Behavior | Pass/Fail | Notes |
|---|------|-------------------|:---------:|-------|
| 27 | Request List loads with tab navigation | All Active, Needs Action, Completed, Cancelled tabs | ⬜ | |
| 28 | Needs Action count matches current state | Empty if records were cleared; shows count if new requests exist | ⬜ | |
| 29 | If cancellation records exist: shows "Cancellation Requested" red badge | Urgent chip styling | ⬜ | |
| 30 | If cancellation records exist: "Review Cancellation" in dropdown | Action visible but DO NOT CLICK | ⬜ | |
| 31 | Cancelled tab loads | Shows only terminal cancellations (or empty) | ⬜ | |
| 32 | Filter counts match visible records | No mismatch between count badges and list | ⬜ | |

### Area 5: Google Calendar & Integrations

| # | Test | Expected Behavior | Pass/Fail | Notes |
|---|------|-------------------|:---------:|-------|
| 33 | Google Calendar status/banner displays | Shows current state: "Connected" or "Reconnect Required" | ⬜ | |
| 34 | If reconnect banner shows: DO NOT click reconnect | Read-only observation only | ⬜ | |
| 35 | Postmark/notification area: no unexpected error banners | Normal state display | ⬜ | |

---

## 3. Restricted Actions (DO NOT Perform During Smoke Test)

| # | Action | Reason |
|---|--------|--------|
| 1 | Submit a care request via `/book` | Creates DynamoDB record + potential notification |
| 2 | Approve or deny a cancellation | Modifies booking status + potential calendar/email |
| 3 | Click "Resend Invite" for any staff | Sends Cognito invitation email |
| 4 | Click "Send Password Reset" | Sends password reset email |
| 5 | Click "Set Temporary Password" | Modifies Cognito user state |
| 6 | Click "Unlink Login Reference" | Modifies staff profile identity link |
| 7 | Click "Delete Profile" | Permanently removes staff record |
| 8 | Click "Disable Login" or "Restore Login" | Modifies Cognito user enabled state |
| 9 | Save any profile edits (click "Save Changes") | Writes to DynamoDB |
| 10 | Assign staff to a booking | Modifies booking + potential calendar event |
| 11 | Reconnect Google Calendar | Initiates OAuth flow + token write |
| 12 | Disconnect Google Calendar | Deletes token secret |
| 13 | Trigger any Stripe/payment flow | Payment state mutation |
| 14 | Create, edit, or delete clients/pets | DynamoDB writes |
| 15 | Create production test data | Pollutes production state |
| 16 | Approve/deny/archive any record | Status mutation |
| 17 | Modify tenant metadata in Platform Admin | Tenant state change |

**If any confirmation modal appears unexpectedly: click Cancel immediately.**

---

## 4. Pass/Fail Criteria

### Overall PASS

All 35 display checks pass without errors. No mutations were performed. No unexpected banners, errors, or broken layouts were observed.

### Overall FAIL

One or more checks reveal:
- Broken page load (white screen, console error, 500 response)
- Incorrect data display (wrong dates, missing records, mismatched counts)
- Layout regression (scrollbar returns, drawer flickers, overflow)
- Missing expected UI elements (orphaned banner gone, protected badge missing)

### Partial PASS

Some checks pass, some reveal cosmetic or minor display issues that don't block core workflows.

---

## 5. Escalation Rules

| Situation | Action |
|-----------|--------|
| Display-only mismatch found | Document the issue (area, expected vs observed). Stop testing that area. |
| Data looks wrong/unexpected | Do NOT edit or fix. Note the issue. Create a triage release if needed. |
| Action accidentally triggers confirmation modal | Click Cancel immediately. Note which action triggered it. |
| Production mutation is needed to fix something | Stop. Require separate explicit Matthew approval in a new release. |
| Console errors visible | Note the error message. Do not attempt to fix in production. |
| Page fails to load entirely | Note URL, attempt refresh once. If persistent, document as FAIL. |

---

## 6. Recording Results

### Format

For each area, record:
- **Area tested:** (e.g., "Staff Management & Profile Editor")
- **Expected behavior:** (from checklist)
- **Observed behavior:** (what actually happened)
- **Pass/Fail:** ✅ or ❌
- **Screenshots:** Optional for failures, but DO NOT commit screenshots to git
- **Notes/Blockers:** Any context

### After Testing

- If all PASS: Report summary to Kiro/AG, proceed to next feature planning
- If any FAIL: Create a targeted triage release documenting the specific failure
- Retain notes locally; do not commit raw test logs to the repository

---

## 7. Post-22V Specific Checks (Regression Verification)

These target the exact issues fixed in 22S/22U/22V:

| # | Regression | Fixed In | How to Verify | Pass/Fail |
|---|-----------|----------|---------------|:---------:|
| R1 | Drawer flicker/disappear on open | 22S | Open 3+ different staff drawers in sequence | ⬜ |
| R2 | Page horizontal scrollbar when drawer open | 22S | Open drawer, check bottom of viewport | ⬜ |
| R3 | Background scrolling behind drawer | 22S | Open drawer, attempt mouse scroll on background | ⬜ |
| R4 | Timezone date offset (date shifted by 1 day) | 22U | Compare displayed dates with known booking dates | ⬜ |
| R5 | Multi-day booking shows single date only | 22U | Find multi-day booking, verify range format | ⬜ |
| R6 | Visit windows missing or only showing first | 22U | Find booking with multiple windows, verify all show | ⬜ |

---

## 8. Recommended Next Path After Smoke Test

| Smoke Result | Next Step |
|-------------|-----------|
| **All PASS** | Proceed to next product feature planning (see options below) |
| **FAIL — layout/drawer regression** | Create 22Y triage: identify if 22S fix regressed or new issue |
| **FAIL — data display issue** | Create 22Y triage: investigate data vs rendering mismatch |
| **FAIL — page load error** | Create 22Y triage: check backend/API/deployment health |
| **Partial PASS — cosmetic only** | Document issues, proceed to feature planning with known minor items |

### Next Feature Options (After PASS)

| Option | Description | Priority |
|--------|-------------|----------|
| A | Profile Editor polish (edit save behavior, field validation, audit history stub) | Medium |
| B | Client booking detail page improvements (view full details, pet info, payment status) | Medium |
| C | Google Calendar reconnect readiness review (if banner shows degraded) | Medium (if needed) |
| D | Production data retention/test-record labeling policy | Low-Medium |
| E | Staff assignment workflow polish (calendar event creation, notification) | Medium |
| F | Admin UX improvements (record lifecycle, archive, stale detection) | Low |

---

## 9. What This Document Does NOT Authorize

- ❌ Running any mutation action during smoke test
- ❌ Code changes
- ❌ Deployment
- ❌ Terraform/AWS changes
- ❌ DynamoDB writes
- ❌ Cognito/identity/profile changes
- ❌ Email/password/invite actions
- ❌ Stripe/payment changes
- ❌ Google Calendar reconnect/disconnect
- ❌ Mobile/TestFlight/App Store changes
- ❌ Creating test data in production
- ❌ Committing screenshots or test logs

This is a read-only validation plan. All mutation actions require separate explicit approval.
