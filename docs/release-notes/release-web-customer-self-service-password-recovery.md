# Web Customer Self-Service Password Recovery

## 1. Status

- **Status:** ✅ **PRODUCTION FRONTEND DEPLOYED / SAFE SMOKE PASS / COGNITO E2E PASS**
- **Date:** 2026-08-15
- **Implementation commit:** `c85a7860c706f38ab2da7998fb7ee8621e8fcfa6`
- **Independent review:** Kiro `IMPLEMENTATION_CORRECT` / `READY_FOR_WEB_FORGOT_PASSWORD_COMMIT_DECISION`
- **V2 RC commit:** `4c7975d3bf9cd0ed84b0348015197034b9127dba`
- **Independent pre-deployment review:** PASS (146/146 tests, build PASS)
- **Cognito E2E:** PASSWORD_RECOVERY_COGNITO_E2E_PASS (Matthew manual validation)

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

## 5. Production Deployment

### Deployment Details

- **Production baseline before:** `ed7a01f5530e22219b430d961156599dd381fd64`
- **Deployed V2 RC:** `4c7975d3bf9cd0ed84b0348015197034b9127dba`
- **Independent pre-deployment review:** PASS (146/146 tests, build PASS)
- **Deployment type:** Frontend-only (no backend, Lambda, Terraform, or API Gateway)
- **S3 bucket:** `s3://togs-and-dogs-prod-toganddogs-hosting`
- **CloudFront distribution:** `E35L00QPA2IRCY`
- **CloudFront invalidation:** `I3RWSM6SQK81OWOK1SR22J3PDE` (Completed)
- **Live assets:** `index-BtB1oa0E.js`, `index-BroXJAxV.css`

### Safe Smoke Results

| Check | Result |
|-------|--------|
| Login page loads | ✅ PASS |
| Forgot Password link visible | ✅ PASS |
| Recovery UI opens | ✅ PASS |
| Local validation works | ✅ PASS |
| Back to Sign In works | ✅ PASS |
| Browser errors | ✅ None |

### NOT Performed

- Cognito verification message NOT sent (no real email/SMS triggered)
- Password NOT changed for any account
- No backend deployment
- No Terraform apply
- No API Gateway change

### Rollback

Restore previous assets `index-Cbij9TXy.js` + `index-B_Bar5e4.css` to S3 and issue a new CloudFront invalidation.

### Cognito E2E Validation

Matthew manually validated the complete password recovery flow against the live user pool:

| Step | Result |
|------|--------|
| Forgot Password request | ✅ Succeeded |
| Cognito verification email | ✅ Received |
| Verification code entry | ✅ Accepted |
| New password set | ✅ Succeeded |
| Subsequent login | ✅ Succeeded |

**Disposition:** PASSWORD_RECOVERY_COGNITO_E2E_PASS

### Remaining UX Improvement

The Cognito-generated verification email is functionally correct but generically branded (sent from `no-reply@verificationemail.com` with minimal context). A branded password-recovery email using Cognito Custom Email Sender + Postmark delivery is planned but not yet implemented.

**Next implementation:** Cognito Custom Email Sender Lambda + KMS + Postmark — PLANNED / NOT IMPLEMENTED / NOT DEPLOYED.
