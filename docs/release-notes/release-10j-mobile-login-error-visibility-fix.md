# Release 10J — Mobile Login Error Visibility Fix

**Status:** ✅ Implementation Complete — Pending New TestFlight Build  
**Date:** 2026-06-12  
**Priority:** P0 — User-blocking login experience regression  
**Risk:** Low — minimal, surgical change to two files; no backend changes  
**Scope:** Mobile auth flow only

---

## Background

During Release 10I Gate C internal TestFlight validation (`1.0.0 (2)` on Matthew's iPhone 15 Pro), the wrong-password login error was confirmed to be **invisible**. The login form silently reset to blank email and password fields with no error message shown to the user. All other fixes from 10H were validated as passing.

---

## Root Cause Analysis

### The Bug

`AuthContext.tsx` `login()` function called `setIsLoading(true)` at the start of every login attempt.

### Why It Caused the Form to Reset

`AppNavigator.tsx` watches the global `isLoading` flag from `AuthContext`:

```tsx
// AppNavigator.tsx (line 180)
if (isLoading) {
  return (
    <View style={styles.loadingContainer}>
      <ActivityIndicator size="large" color={COLORS.primary} />
    </View>
  );
}
if (!isAuthenticated) {
  return <AuthNavigator />;   // ← contains LoginScreen
}
```

When `setIsLoading(true)` was called:
1. `AppNavigator` rendered the full-screen spinner **instead of** `AuthNavigator`
2. This **unmounted** `AuthNavigator` and `LoginScreen` entirely
3. All local React state in `LoginScreen` was **destroyed** — `email`, `password`, `error`

When the Cognito call failed and `setIsLoading(false)` was called:
4. `AppNavigator` re-rendered `AuthNavigator` → `LoginScreen` **remounted fresh**
5. All state was gone — empty fields, no error message

The `LoginScreen.handleLogin` catch block correctly called `setError(getFriendlyAuthError(e))`, but the component had already been unmounted and remounted before that line could update any visible state.

### Why `isLoading` Exists in AuthContext

`isLoading` is only appropriate for the **initial bootstrap phase** — the `bootstrapAsync()` useEffect that checks for a stored token on app launch. During that phase, showing a spinner instead of the login screen is correct (prevents a flash of the login screen before session restoration completes). It was never intended to be used during an active login attempt.

---

## Fix

### File 1: `mobile/src/auth/AuthContext.tsx`

**Change:** Removed all `setIsLoading(true/false)` calls from the `login()` function.

The `login()` function now only:
- Calls `cognitoSignIn()` and awaits the result
- On success: updates `user` and `role` state (triggering the authenticated nav)
- On failure: throws the error back to the caller (`LoginScreen.handleLogin`)

`LoginScreen` already manages its own local `isLoading` state for the button spinner — that is the correct location for this UI concern.

```tsx
// Before (BROKEN): caused LoginScreen to unmount on every login attempt
const login = async (email, password) => {
  setIsLoading(true);       // ← unmounts LoginScreen → destroys local state
  try { ... }
  catch (error) {
    setIsLoading(false);    // ← LoginScreen remounts fresh → error never shows
    throw error;
  }
};

// After (FIXED): isLoading stays false throughout the login attempt
const login = async (email, password) => {
  // isLoading is bootstrap-only — do NOT set it here
  try { ... }
  catch (error) {
    throw error;            // ← LoginScreen stays mounted → setError() works
  }
};
```

### File 2: `mobile/src/screens/LoginScreen.tsx`

**Change:** In the `handleLogin` catch block, added `setPassword('')` before `setError()`.

- **Email field** is preserved — so the user only needs to re-type the password
- **Password field** is cleared — security best practice on auth failure
- **Error message** now displays correctly since the component stays mounted

```tsx
// Before
} catch (e: any) {
  setError(getFriendlyAuthError(e));
}

// After
} catch (e: any) {
  setPassword('');   // clear password for security, preserve email for UX
  setError(getFriendlyAuthError(e));
}
```

---

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `mobile/src/auth/AuthContext.tsx` | Removed `setIsLoading(true/false)` from `login()` | -4 lines |
| `mobile/src/screens/LoginScreen.tsx` | Added `setPassword('')` and comment in `handleLogin` catch | +3 lines |

---

## Validation

### TypeScript
```
npx tsc --noEmit
```
**Result:** ✅ 0 errors, 0 warnings

### Code Review — Correct Behaviour After Fix

| Scenario | Expected Behaviour | Verified |
|----------|--------------------|---------|
| Wrong password entered | Error message appears: *"Incorrect email or password. Please try again."* Email field preserved. Password field cleared. | ✅ By code review |
| Empty fields submitted | Error message: *"Please enter your email and password."* | ✅ By code review |
| Correct login | User/role state updates → AppNavigator routes to correct tab | ✅ By code review |
| Forgot password link | Still reachable via `switchToForgotPassword()` in `LoginScreen` | ✅ By code review |
| App launch (bootstrap) | `isLoading` starts `true` during `bootstrapAsync`, spinner shows, then routes correctly | ✅ By code review — `isLoading` logic unchanged in `useEffect` |
| Logout | `isLoading` still set in `logout()` — logout spinner still works | ✅ By code review — `logout()` unchanged |

---

## No Regressions Introduced

- `isLoading` in `AuthContext` continues to work correctly for:
  - **Bootstrap phase** (session restore on app launch) — unchanged
  - **Logout** — unchanged; `setIsLoading(true/false)` in `logout()` is correct because it's fine to unmount the app during logout
- The `login()` simplification does not affect successful login routing — `setUser()` and `setRole()` still trigger `AppNavigator` to transition to the correct authenticated view

---

## Guardrail Confirmations

| Guardrail | Status |
|-----------|--------|
| No EAS build run | ✅ Confirmed |
| No EAS submit run | ✅ Confirmed |
| No testers invited | ✅ Confirmed |
| No App Store Connect / TestFlight changes | ✅ Confirmed |
| No AWS / Terraform / S3 / CloudFront / Cognito / Postmark / Google Calendar changes | ✅ Confirmed |
| No production data modified | ✅ Confirmed |
| No web/backend production changes | ✅ Confirmed |
| No features outside approved 10J scope | ✅ Confirmed |

---

## Next Steps

A **new EAS iOS production build** is required to get this fix onto TestFlight. This should be planned as Release 10K (Gate A build + Gate B submit).

### Expected TestFlight validation for 10K build:

1. Install new build on iPhone 15 Pro via TestFlight
2. Enter a **wrong password** on the login screen
3. Verify: friendly error message appears, email field stays populated, password field is blank
4. Verify: "Forgot password?" link is still visible and functional
5. Verify: correct password for any user logs in successfully
