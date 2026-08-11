# Web Customer Self-Service Password Recovery

## 1. Status

- **Status:** **LOCAL IMPLEMENTATION COMPLETE / COMMITTED / PUSHED / NOT DEPLOYED**
- **Date:** 2026-08-11
- **Implementation commit:** `c85a7860c706f38ab2da7998fb7ee8621e8fcfa6`
- **Independent review:** Kiro `IMPLEMENTATION_CORRECT` / `READY_FOR_WEB_FORGOT_PASSWORD_COMMIT_DECISION`

This bounded web-only release closes the customer self-service forgot-password parity gap without changing Cognito configuration, backend behavior, infrastructure, mobile code, or production systems.

## 2. Customer Flow

The existing shared web login shell now provides:

1. A keyboard-accessible **Forgot password?** action.
2. A verification-code request step using a trimmed, lower-cased email address.
3. A confirmation step for verification code, new password, and password confirmation.
4. Required-field, eight-character minimum, and password-match validation.
5. Safe code-request and confirmation errors that do not render raw Cognito details.
6. A distinct success state and **Back to Sign In** action that preserves the normalized email without automatically signing the user in.

Loading states disable repeat submissions. Verification codes and passwords remain in component memory only and are cleared after success or navigation.

## 3. Cognito and Scope Boundary

`web/src/api/auth.js` now exposes `forgotPassword(email)` and `confirmForgotPassword(email, verificationCode, newPassword)`. Both construct a `CognitoUser` from the existing customer user pool and call the standard self-service `amazon-cognito-identity-js` operations.

No Cognito user-pool or app-client configuration changed. No administrator Cognito API, backend password endpoint, real-user reset, production-data access, tenant change, mobile change, or deployment occurred.

## 4. Validation

- Focused forgot-password rendered tests: **13/13**
- Relevant AdminDashboard/auth tests: **24/24** across 3 files
- Full Vitest: **251/251** across 21 files
- Legacy web: **99/99**
- Combined web: **350/350**
- Vite production build: **PASS**; 109 modules transformed
- Targeted lint for `auth.js` and the new test file: **PASS**
- `AdminDashboard.jsx` lint remains identical to the clean-HEAD baseline: 18 errors and 5 warnings, with no candidate-introduced finding
- `git diff --check`: **PASS**

Kiro independently reproduced the candidate and returned `IMPLEMENTATION_CORRECT` with no findings.

## 5. Deployment Gate

This feature is committed and pushed but **not deployed**. Customers cannot use it in production until Matthew separately approves a scoped web production deployment and its validation/rollback plan.
