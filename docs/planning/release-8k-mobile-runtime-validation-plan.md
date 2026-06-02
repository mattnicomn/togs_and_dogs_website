# Release 8K: Mobile Runtime Validation & Expo Device Testing

**Status:** Planning
**Priority:** High (validates real-device behavior before adding more features)
**Risk to Production:** None (read-only validation, no deployment)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Local Expo runtime testing, defect discovery, documentation

---

## 1. Purpose

Validate the React Native mobile app on a real phone, tablet, or emulator to confirm that Releases 8G–8J work correctly in a real mobile environment — not just TypeScript compilation. This is the first time the app will be tested against production APIs from a mobile device.

---

## 2. Preconditions

### Environment Requirements

| Requirement | Status | Notes |
|-------------|--------|-------|
| Node.js ≥ 18 installed | Verify | `node --version` |
| npm or yarn available | Verify | `npm --version` |
| `mobile/node_modules` installed | Verify | Run `npm install` in `mobile/` if missing |
| Expo CLI available | Verify | `npx expo --version` (installed as local dep) |
| Expo Go app on test device | Required | Download from App Store / Play Store |
| Test device on same WiFi as dev machine | Required | For Expo Go to connect to Metro bundler |
| OR: Android emulator / iOS simulator configured | Alternative | If no physical device available |

### Account Requirements

| Requirement | Notes |
|-------------|-------|
| Cognito owner/admin credentials | Ryan's production login OR Matthew's test admin account |
| API Gateway accessible from device | Production API at `a022yxuiue.execute-api.us-east-1.amazonaws.com` |
| At least 1 active request in DynamoDB | For request list to display data |

### Known Configuration

From `mobile/src/api/config.ts`:
```typescript
API_URL: 'https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod'
USER_POOL_ID: 'us-east-1_counlsXGU'
CLIENT_ID: '1u4t7rfo339nkcgaf6q8s8sc6u'
```

---

## 3. Exact Commands

### Step 1: Verify Environment

```bash
cd mobile
node --version          # Expect ≥ 18.x
npm --version           # Expect ≥ 9.x
npx expo --version      # Expect ≥ 0.x or SDK 56 compatible
```

### Step 2: Install Dependencies (if needed)

```bash
cd mobile
npm install
```

### Step 3: TypeScript Compilation Check

```bash
cd mobile
npx tsc --noEmit
```

Expected: 0 errors. If errors appear, document them as blockers.

### Step 4: Start Metro Bundler

```bash
cd mobile
npx expo start
```

This displays a QR code and menu:
- Press `a` for Android emulator
- Press `i` for iOS simulator
- Scan QR code with Expo Go app on physical device

### Step 5: Connect Device

**Option A: Physical device (recommended for real validation)**
1. Install "Expo Go" from App Store (iOS) or Play Store (Android)
2. Ensure device is on same WiFi network as dev machine
3. Scan the QR code shown in the terminal
4. App should bundle and launch on device

**Option B: Emulator/Simulator**
- Android: Start Android Studio emulator first, then press `a`
- iOS: Requires macOS with Xcode; press `i`

**Option C: Expo Go tunnel (if different network)**
```bash
npx expo start --tunnel
```
Note: Requires `@expo/ngrok` — install if prompted.

---

## 4. Validation Checklist

### 4.1 App Launch & Navigation

| # | Test | Expected | Pass? | Notes |
|---|------|----------|-------|-------|
| 1 | Metro bundler starts without errors | Terminal shows QR code + "Metro waiting" | | |
| 2 | App loads on device/emulator | Splash screen → Login screen | | |
| 3 | No red error screen on launch | Clean UI renders | | |
| 4 | No yellow warning banners (or only non-critical) | Clean or minor dep warnings only | | |

### 4.2 Authentication (Cognito)

| # | Test | Expected | Pass? | Notes |
|---|------|----------|-------|-------|
| 5 | Login screen renders (email + password inputs) | Text inputs visible, keyboard works | | |
| 6 | Enter invalid credentials → tap Login | Error message displayed (not crash) | | |
| 7 | Enter valid owner/admin credentials → tap Login | Navigates to Dashboard/tab navigator | | |
| 8 | Session persists after login (token stored) | App stays logged in on re-open | | |
| 9 | Role is correctly resolved (owner/admin) | Dashboard shows role-appropriate content | | |

### 4.3 Dashboard Screen

| # | Test | Expected | Pass? | Notes |
|---|------|----------|-------|-------|
| 10 | Dashboard renders after login | Stat cards visible | | |
| 11 | Stat cards show real numbers from API | Non-zero counts if requests exist | | |
| 12 | Loading indicator shows while fetching | Spinner or skeleton visible briefly | | |
| 13 | No crash if API returns empty data | Graceful "0" display | | |

### 4.4 Request List Screen

| # | Test | Expected | Pass? | Notes |
|---|------|----------|-------|-------|
| 14 | Request list tab navigates correctly | List screen renders | | |
| 15 | Request cards display with real data | Client names, pet names, dates, status | | |
| 16 | Status badges show correct colors/labels | PENDING_REVIEW, APPROVED, ASSIGNED, etc. | | |
| 17 | Service type shows friendly label | "30-Minute Walk" not "WALK_30MIN" | | |
| 18 | Multi-day badge shows if applicable | "Multi-Day" indicator on range bookings | | |
| 19 | Pull-to-refresh works | Pull down → loading indicator → fresh data | | |
| 20 | Filter/status selector works (if implemented) | Switching filters shows different records | | |
| 21 | Empty state shows if no records match filter | Friendly "No records" message | | |
| 22 | Scroll performance is smooth (no jank) | 60fps scrolling through 10+ records | | |

### 4.5 Request Detail / Card Expansion

| # | Test | Expected | Pass? | Notes |
|---|------|----------|-------|-------|
| 23 | Tap a request card → detail view opens | Full detail screen or expanded card | | |
| 24 | Client name, email, phone visible | Correct data from API | | |
| 25 | Pet names and service type visible | Correct data | | |
| 26 | Dates displayed correctly (single or multi-day) | Formatted dates, not raw ISO strings | | |
| 27 | Visit window displayed as friendly label | "Morning (7–10 AM)" not "MORNING" | | |
| 28 | Status displayed with badge | Colored chip matching web behavior | | |

### 4.6 Admin Approve Action (Release 8J)

| # | Test | Expected | Pass? | Notes |
|---|------|----------|-------|-------|
| 29 | "Approve" button visible on PENDING_REVIEW request | Button renders at bottom of detail | | |
| 30 | Tap "Approve" → confirmation modal appears | "Approve this request?" dialog | | |
| 31 | Tap "Cancel" on modal → returns to detail (no change) | Modal dismissed, no API call | | |
| 32 | Tap "Confirm" on modal → loading state | Button shows spinner/disabled | | |
| 33 | Approval succeeds → success feedback | Toast/alert + status updates to APPROVED | | |
| 34 | Double-tap prevention works | Second tap ignored during loading | | |
| 35 | Approval on already-approved request → graceful error | Backend rejects invalid transition | | |

### 4.7 Schedule Screen

| # | Test | Expected | Pass? | Notes |
|---|------|----------|-------|-------|
| 36 | Schedule tab renders | Today's visits or "No visits today" | | |
| 37 | Scheduled visits show correct date/time/client | Data matches request list | | |

### 4.8 Edge Cases & Error Handling

| # | Test | Expected | Pass? | Notes |
|---|------|----------|-------|-------|
| 38 | Kill app → reopen | Restores session (stays logged in) | | |
| 39 | Toggle airplane mode → attempt action | Error displayed, no crash | | |
| 40 | Rotate device (landscape) | Layout adjusts or remains portrait | | |
| 41 | Background app → return | App resumes without re-login | | |
| 42 | Very long client/pet name | Text truncates or wraps (no overflow) | | |

---

## 5. Expected Results

### Successful Validation

If all checks pass:
- The app is confirmed functional on a real mobile device
- Core admin workflows (view + approve) work against production APIs
- The foundation is solid for adding more actions (assign, cancel) in subsequent releases
- Document results in a closeout note

### Blockers (Document If Found)

| Potential Blocker | Action |
|-------------------|--------|
| `npm install` fails (dependency conflict) | Document exact error, resolve in 8K fix |
| TypeScript errors prevent compilation | Document errors, fix in 8K |
| Metro bundler crashes | Document error, check Node/Expo version compat |
| Expo Go can't connect to Metro | Try `--tunnel` mode or check firewall |
| Cognito auth fails on device | Check CLIENT_ID, verify Cognito app client settings allow mobile |
| API calls fail with CORS or network error | Check API Gateway CORS config (should work — no CORS on mobile native) |
| Red screen crash on specific screen | Screenshot + document stack trace |

---

## 6. What This Release Does NOT Do

| Excluded | Reason |
|----------|--------|
| App Store submission | Not ready — still testing locally |
| EAS cloud build | Not needed for Expo Go testing |
| Backend changes | No API modifications needed |
| New mobile features | This is validation-only |
| Web app changes | Web is stable, no touch |
| Terraform / AWS changes | Infrastructure unchanged |
| Production data mutations | Only test "Approve" on a test request if safe |

---

## 7. Rollback / No-Change Posture

This release has zero deployment risk:
- No code is deployed to production servers
- No app is submitted to stores
- The mobile app runs locally via Expo Go only
- If issues are found, they're documented for the next fix release
- The web app and backend are completely unaffected

If the validation reveals critical blockers:
- Document them in the closeout note
- Plan a fix release (8K.1 or 8L) before proceeding with more features
- Fall back to PWA for Ryan's daily use until native is ready

---

## 8. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — execute Release 8K: Mobile Runtime Validation.

This is a TESTING release. No code changes unless a specific defect requires a fix.
Primary goal: run the mobile app on a real device or emulator and validate behavior.

=== 1. Environment Setup ===

cd mobile
npm install              # Ensure all deps are installed
npx tsc --noEmit        # Verify TypeScript compiles clean

Report: Any TypeScript errors or dependency warnings.

=== 2. Start Metro Bundler ===

cd mobile
npx expo start

Report: Does Metro start successfully? Any warnings?

=== 3. Connect Test Device ===

Use one of:
- Physical device with Expo Go (scan QR code)
- Android emulator (press 'a')
- iOS simulator (press 'i' — requires macOS)

Report: Does the app bundle and launch? Any red screen errors?

=== 4. Run Validation Checklist ===

Execute the full checklist from Section 4 of this planning document.
For each item, report: PASS, FAIL (with description), or BLOCKED (with reason).

Priority order:
1. App launch (#1-4)
2. Login (#5-9)
3. Dashboard (#10-13)
4. Request list (#14-22)
5. Request detail (#23-28)
6. Approve action (#29-35)
7. Schedule (#36-37)
8. Edge cases (#38-42)

=== 5. Document Results ===

Create docs/release-notes/release-8k-validation-closeout.md with:
- Date
- Device/emulator used
- Expo Go version
- Node/npm/Expo SDK versions
- Pass/fail summary per section
- Screenshots of any failures
- List of any blockers or defects found
- Recommendation: proceed to 8L or fix first

=== 6. Fix ONLY If ===

Only make code changes if:
- A simple TypeScript error prevents compilation (typo, missing import)
- A trivial config issue blocks device connection
- Document any fix made and include in the closeout

Do NOT:
- Modify backend files
- Modify web/ directory
- Modify Terraform
- Change AWS resources
- Submit to App Store
- Run EAS Build
- Change API endpoints or Cognito config

Return: validation results, any blockers found, recommendation for next release.
```

---

## 9. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-8k-mobile-runtime-validation-plan.md
git commit -m "docs: Release 8K — mobile runtime validation plan"
```
