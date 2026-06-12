# Release 10H — Mobile P0 Auth, Client Dashboard, and Welcome Header Fixes

**Status:** Implementation Complete — Pending New TestFlight Build  
**Priority:** High  
**Risk to Production:** Low (mobile-only code changes; no backend, infrastructure, or data modifications)  
**Backend Changes:** None  
**Scope:** Mobile app code fixes only

---

## Release Purpose

Address P0 issues discovered during the Release 10F internal TestFlight smoke validation on Matthew's iPhone 15 Pro (TestFlight build `1.0.0 (1)`).

---

## Issues Addressed

### Issue 1: Login Error — No Visible User Feedback on Wrong Password
**Root Cause:** The `LoginScreen.tsx` error catch block passed `e.message` directly from the Cognito SDK, which can include raw error codes like `NotAuthorizedException: Incorrect username or password.` — visible but potentially leaking internal API contract terminology. More importantly, the catch was correct, but the error display needed sanitization and hardening.  
**Fix:** Added `getFriendlyAuthError()` function that maps known Cognito error codes/messages to clean user-facing copy. Default fallback: `"Incorrect email or password. Please try again."` — never exposes raw Cognito internals.

### Issue 2: Forgot Password — No Flow Available
**Root Cause:** No forgot password functionality existed in the mobile app. The `LoginScreen.tsx` had no link or flow to trigger password reset.  
**Fix:** Implemented a complete in-screen, mode-toggled forgot password flow with three states:
- `login` — standard sign-in screen with a new "Forgot password?" link
- `forgotSendCode` — email entry to trigger Cognito `forgotPassword()` (sends a 6-digit code)
- `forgotResetPassword` — code + new password + confirm fields with clear success/error state

Added two new exported functions to `cognito.ts`:
- `forgotPassword(email)` — wraps `CognitoUser.forgotPassword()`
- `confirmForgotPassword(email, code, newPassword)` — wraps `CognitoUser.confirmPassword()`

### Issue 3: Admin Dashboard — Hardcoded "Welcome back, Ryan"
**Root Cause:** `DashboardScreen.tsx` line 95 had a static hardcoded string `"Welcome back, Ryan"`.  
**Fix:** Replaced with a dynamic expression using the authenticated user's email from `AuthContext`:
```
Welcome back, {user ? user.split('@')[0] : 'there'}
```
This derives the name from the email prefix (e.g., `mattnicomn10@gmail.com` → `"Welcome back, mattnicomn10"`). The fallback is `"there"` if no user is loaded. Full display name support can be added when a profile endpoint is available.

### Issue 4: Admin Mobile — Missing Google Calendar / User Management Parity (Deferred P1)
**Root Cause:** These features only exist in the web admin portal. Building full mobile management screens is out of scope for 10H.  
**Fix (10H):** Added a "Web Admin Portal Features" notice card to `DashboardScreen.tsx` informing the user that Google Calendar management and staff/client administration are available via the web portal. No code change required for feature logic.  
**Deferred:** Full mobile equivalents are P1/P2 features for a future release.

### Issue 5: Client User (`brearockwell@gmail.com`) — No Appointments Shown
**Root Cause:** `BookingsScreen.tsx` was a **placeholder screen** — it never made any API call. It displayed a static message: *"Your booked pet care visits will render here."* The backend already has a fully functional `/client/requests` endpoint that returns sanitized bookings scoped to the logged-in client by `client_id`.  
**Fix:** Replaced the placeholder with a complete `BookingsScreen` implementation that:
- Calls `GET /client/requests` (a protected endpoint using the Cognito ID token)
- Backend resolves the client profile via `resolve_client_identity()` (sub → email fallback)
- Displays each appointment card with: pet name, service type, date(s), sitter, and status badge
- Shows a spinner while loading
- Shows a clear error state with a retry button on failure  
- Shows a friendly empty state if no appointments are linked
- Supports pull-to-refresh
- Added `getClientRequests()` to `mobile/src/api/client.ts`

> [!NOTE]
> **If `brearockwell@gmail.com` still shows no appointments after this fix**, the issue is a data linkage problem — the Cognito sub/email for this user does not match any `CLIENT#` profile in DynamoDB. This would require a one-time production data fix (adding `cognito_sub` or verifying email in the client profile record) — which requires Matthew's explicit approval before any data mutation.

---

## Files Changed

| File | Change |
|------|--------|
| `mobile/src/screens/LoginScreen.tsx` | Added `getFriendlyAuthError()`, forgot password mode-toggle UI (3 states), "Forgot password?" link |
| `mobile/src/auth/cognito.ts` | Added `forgotPassword()` and `confirmForgotPassword()` exports |
| `mobile/src/screens/DashboardScreen.tsx` | Fixed hardcoded "Ryan" → dynamic user email prefix, added web-only features notice card |
| `mobile/src/screens/BookingsScreen.tsx` | Complete replacement — real `/client/requests` fetch, appointment cards, loading/error/empty states |
| `mobile/src/api/client.ts` | Added `getClientRequests()` → `GET /client/requests` |

---

## Validation

| Check | Command | Result |
|-------|---------|--------|
| TypeScript | `npx tsc --noEmit` | ✅ 0 errors |

---

## Deferred Items

| Item | Priority | Notes |
|------|----------|-------|
| Full display name in welcome header | P2 | Requires profile endpoint; current fix uses email prefix |
| Mobile Google Calendar management | P1 | Web portal only; notice card added |
| Mobile staff/client/user administration | P2 | Web portal only; notice card added |
| Client profile data linkage verification for `brearockwell@gmail.com` | Immediate | If appointments still not visible after this fix, escalate to data correction |

---

## Follow-Up Actions Required

1. **New TestFlight build required.** These code changes are not live until a new `eas build` produces a new build (e.g., `1.0.0 (2)`) and Matthew uploads it to TestFlight for re-testing.
2. **Verify `brearockwell@gmail.com` appointments appear** after the new build is installed. If not, run a read-only DynamoDB investigation to check client profile linkage.
3. **Do not approve Gate C/D/external testers** until the new build is validated.
