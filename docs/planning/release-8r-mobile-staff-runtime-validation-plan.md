# Release 8R: Mobile Staff Runtime Validation & Staff Account Readiness

**Status:** Planning
**Priority:** High (validates staff workflow before adding more features)
**Risk to Production:** None (validation-only, no code deployment)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Physical device testing of staff-scoped mobile experience

---

## 1. Purpose

Confirm that a Cognito staff-role account can log into the React Native mobile app via Expo Go on a physical iPhone/tablet and see the correct staff-scoped schedule workflow delivered in Release 8Q. This closes the pending validation gap documented in the 8Q closeout.

---

## 2. Test Account Requirements

### Option A: Use Existing Staff Account (Preferred)

If a staff user already exists in the Cognito user pool (`us-east-1_counlsXGU`) with:
- Status: `CONFIRMED` or `FORCE_CHANGE_PASSWORD`
- Group membership: `Staff`
- Known email and password

Check via Admin Dashboard → Staff Management for any active staff with a linked Cognito account.

### Option B: Create a Dedicated Test Staff Account (If Needed)

If no active staff account exists with known credentials:
1. Open Admin Dashboard → Staff Management
2. Create a new staff profile (e.g., "Test Staff Mobile") with a real email Matthew can access
3. Use "Onboard" or "Link Login Account" to create the Cognito user
4. Set a temporary password or use the invite flow
5. Log in once via the web to confirm the account works, then test on mobile

**Important:** Do NOT modify any real staff account's password. Use a test account or an account Matthew owns.

### Test Data Requirements

For the staff schedule to show visits:
- At least **1 booking** must be in `ASSIGNED` status with `worker_id` matching the staff account's email
- The booking's `start_date` or `selected_dates` should include today or a future date

If no assigned bookings exist for the test staff:
1. Create a test booking via Admin → + New Visit
2. Assign it to the test staff account
3. Verify it appears in the web admin schedule before testing mobile

For empty-state validation:
- Use a second staff account with zero assignments, OR
- Test before creating any assignments for the account

---

## 3. Validation Environment

### Expo Go Startup Command

```bash
cd mobile
npx expo start --clear --lan --port 8082
```

If port 8082 is occupied:
```bash
npx expo start --clear --lan --port 8083
```

### Device Requirements

- iPhone or iPad with Expo Go installed (App Store)
- Device on same WiFi network as development machine
- Scan QR code from terminal to connect

### Alternative: Tunnel Mode (Different Network)

```bash
npx expo start --clear --tunnel --port 8082
```

---

## 4. Validation Checklist

### 4.1 Staff Login

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 1 | Open app in Expo Go | Login screen renders | |
| 2 | Enter staff credentials | No error on valid credentials | |
| 3 | Successful login | Navigates to staff tab navigator (Schedule tab) | |
| 4 | Role detection | Does NOT show admin Dashboard or Requests tabs | |
| 5 | Only Schedule tab visible | Bottom tab shows "Schedule" only (no Dashboard, no Requests) | |

### 4.2 Staff Schedule — Today / Upcoming

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 6 | Schedule screen loads | Shows "My Schedule" title | |
| 7 | Today section visible | "Today" header with today's date | |
| 8 | Assigned visit card renders | Shows pet name, client, service, time window | |
| 9 | Worker name on card | Shows the staff user's own name | |
| 10 | Upcoming section | Shows future visits (if any exist) | |
| 11 | Visits are scoped to staff user | Only shows visits where `worker_id` matches this user | |
| 12 | Does NOT show other staff's visits | No visits for other workers visible | |

### 4.3 Staff Empty States

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 13 | No visits today | "No visits assigned to you today" or similar | |
| 14 | No upcoming visits | "No upcoming visits" or appropriate message | |

### 4.4 Staff Booking Detail Access

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 15 | Tap a schedule card | Navigates to RequestDetailScreen | |
| 16 | Client info visible | Name, email, phone, address shown | |
| 17 | Pet info visible | Pet names, care instructions, feeding/meds/behavior | |
| 18 | Service details visible | Type, window, dates | |
| 19 | Emergency contact visible | If present on the record | |

### 4.5 Admin Actions Hidden for Staff

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 20 | No "Approve Booking" button | Button NOT rendered on detail screen | |
| 21 | No "Assign Staff" button | Button NOT rendered | |
| 22 | No "Change Staff" button | Button NOT rendered | |
| 23 | No staff picker accessible | Cannot trigger staff selection modal | |

### 4.6 Session & Refresh

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 24 | Pull-to-refresh on schedule | Loading indicator → fresh data | |
| 25 | Background app → return | App resumes, data still visible | |
| 26 | Kill app → reopen | Session persists (stays logged in) | |
| 27 | Extended idle → interact | Token refresh handles silently (or re-login prompt) | |

### 4.7 Edge Cases

| # | Test | Expected | Pass? |
|---|------|----------|-------|
| 28 | Disconnect WiFi → pull-to-refresh | Error message shown, no crash | |
| 29 | Long pet name or care instructions | Text wraps, no overflow | |
| 30 | Rotate device to landscape | Layout adapts without breaking | |

---

## 5. Sensitive Field Review

Confirm the backend's `sanitize_booking_for_role(item, 'staff')` correctly redacts:

| Field | Should Staff See? |
|-------|-------------------|
| `client_name` | ✅ Yes (needed for visit) |
| `client_email` | ✅ Yes (contact during visit) |
| `client_phone` | ✅ Yes (contact during visit) |
| `pet_names` / `pet_info` | ✅ Yes (care instructions) |
| `address` | ✅ Yes (visit location) |
| `vet_info` / `emergency_contact` | ✅ Yes (safety) |
| `internal_pricing_notes` | ❌ No (redacted by sanitize) |
| `admin_notes` | ❌ No (redacted) |
| `audit_log` | ❌ No (redacted) |
| `discount_rationale` | ❌ No (redacted) |

If the mobile detail screen accidentally shows fields that should be redacted, document it as a finding (not a code fix in this release).

---

## 6. Expected Outcomes

### All Tests Pass

- Staff mobile workflow is confirmed functional
- Release 8Q validation gap is closed
- Ready to proceed to next mobile feature release

### Blockers Found

If issues are discovered:

| Potential Issue | Action |
|----------------|--------|
| Staff login fails (Cognito group not recognized) | Check `cognito:groups` claim in JWT; may need Cognito User Pool config check |
| Staff sees admin tabs | Check role resolution logic in `AppNavigator.tsx` |
| Schedule shows all visits (not staff-scoped) | Check filter logic in `ScheduleScreen.tsx` — should filter by `worker_id` |
| Admin actions visible to staff | Check role guard in `RequestDetailScreen.tsx` |
| Token refresh fails for staff | Same auth flow as admin — should work identically |

Document any blockers for a targeted fix in Release 8R.1 or 8S.

---

## 7. What This Release Does NOT Do

| Excluded | Reason |
|----------|--------|
| Code changes | Validation-only unless a critical blocker requires a fix |
| Backend modifications | Staff scoping already handled server-side |
| Cognito group changes | Staff group already exists |
| App Store submission | Local Expo Go testing only |
| Web/PWA changes | Unrelated |
| New mobile features | Validate existing before adding more |

---

## 8. Rollback / No-Change Posture

This release has zero deployment risk:
- No code is deployed
- No production data is modified
- No infrastructure changes
- If validation passes, document and close
- If validation fails, document the issue and plan a fix

---

## 9. AG Validation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — execute Release 8R: Staff Runtime Validation.

This is a VALIDATION release. No code changes unless a specific critical defect
blocks the staff login or schedule visibility.

=== 1. Identify Staff Test Account ===

Check Admin Dashboard → Staff Management for an active staff profile
with a linked Cognito account. Document the email being used for testing.

If no staff account is available:
- Report this as a blocker
- Do NOT create Cognito users without Matthew's explicit approval
- Provide manual steps for Matthew to create the test account

=== 2. Start Expo Development Server ===

cd mobile
npx expo start --clear --lan --port 8082

(If port occupied, use --port 8083)
Report: Metro bundler starts successfully? Any warnings?

=== 3. Connect iPhone via Expo Go ===

Scan QR code with Expo Go app.
Report: App bundles and launches? Any red screen errors?

=== 4. Login as Staff ===

Enter staff credentials on the login screen.
Report: Login succeeds? Correct tab navigator shown (Schedule only)?

=== 5. Run Validation Checklist ===

Execute the full 30-item checklist from Section 4 of this planning document.
For each item, report: PASS, FAIL (with description), or BLOCKED (with reason).

=== 6. Document Results ===

If all pass: Update the 8Q closeout note to confirm staff validation passed,
then create a brief 8R closeout confirming completion.

If issues found: Document each issue with:
- What was expected
- What actually happened
- Screenshot if possible
- Recommended fix

=== 7. Do NOT ===

- Do NOT modify backend files
- Do NOT modify Terraform or AWS resources
- Do NOT modify Cognito user pool settings
- Do NOT create Cognito users without Matthew's approval
- Do NOT deploy to App Store
- Do NOT modify the web app

Return: validation results per checklist item, any blockers, recommendation.
```

---

## 10. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-8r-mobile-staff-runtime-validation-plan.md
git commit -m "docs: plan release 8r mobile staff runtime validation"
```
