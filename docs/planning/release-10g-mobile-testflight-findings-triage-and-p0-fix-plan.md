# Release 10G: Mobile TestFlight Findings Triage & P0 Fix Plan

**Status:** Planning / Triage
**Priority:** High (P0 fixes needed before external testing)
**Risk to Production:** Low (mobile-only fixes)
**Terraform Required:** No
**Backend Changes:** Likely needed for client appointment investigation
**Scope:** Triage findings, plan P0 mobile fixes, defer product roadmap items

---

## 1. TestFlight Validation Results Summary

| Area | Status | Details |
|------|--------|---------|
| **TestFlight install** | ✅ Pass | Build 1.0.0 (1) installed from TestFlight |
| **App launch** | ✅ Pass | No crash, login screen renders |
| **Staff login** (`mattnicomn10@yahoo.com`) | ✅ Pass | Schedule loads, upcoming visits visible |
| **Admin login** (`mattnicomn10@gmail.com`) | ✅ Pass | Dashboard loads |
| **Client login** (`brearockwell@gmail.com`) | ⚠️ Partial | Logs in but sees no appointments |
| **Login error handling** | ❌ Fail | Wrong password shows no error feedback |
| **Password reset flow** | ❌ Missing | No forgot-password option visible |
| **Admin Google Calendar** | ❌ Missing | No connect option in mobile app |
| **Admin user management** | ❌ Missing | No staff/client management in mobile |
| **Welcome header personalization** | ❌ Bug | Shows "Ryan" instead of current user's name |

---

## 2. Pass/Fail by Role

### Staff: `mattnicomn10@yahoo.com`

| Check | Result |
|-------|--------|
| Login | ✅ Pass |
| Schedule renders | ✅ Pass |
| No visits today | ✅ Correct (none assigned) |
| Upcoming visits shown | ✅ Pass |
| Overall | ✅ **PASS** |

### Admin: `mattnicomn10@gmail.com`

| Check | Result |
|-------|--------|
| Login | ✅ Pass |
| Dashboard loads | ✅ Pass |
| Google Calendar connect | ❌ Not available (web-only feature) |
| User/staff/client management | ❌ Not available (web-only feature) |
| Welcome shows "Ryan" not actual name | ❌ Bug |
| Overall | ⚠️ **PASS with issues** |

### Client: `brearockwell@gmail.com`

| Check | Result |
|-------|--------|
| Login | ✅ Pass |
| Dashboard / bookings | ❌ Shows no appointments (expects to see some) |
| Wrong password error | ❌ No error feedback shown |
| Password reset | ❌ No flow available |
| Overall | ❌ **FAIL — needs investigation** |

---

## 3. Priority Classification

### P0 — Fix Before External Testing (Release 10H)

| # | Issue | Impact | Complexity |
|---|-------|--------|-----------|
| 1 | **Login error feedback missing** | User thinks app is broken when wrong password entered | Low — add error state display |
| 2 | **Forgot password / reset flow missing** | Users can't recover access; requires Matthew intervention | Medium — add Cognito `forgotPassword` flow |
| 3 | **Client appointments not showing** | Client user sees empty dashboard — may be data/linkage issue | Medium — requires investigation |
| 4 | **Welcome header shows "Ryan" hardcoded** | Confusing for all non-Ryan users | Low — use actual authenticated user name/email |

### P1 — Follow-Up After External Testing (Release 10I+)

| # | Issue | Impact | Notes |
|---|-------|--------|-------|
| 5 | Admin Google Calendar connect not in mobile | Admin must use web for calendar setup | Document as "use web for this" or add future link |
| 6 | Admin user/staff/client management not in mobile | Admin must use web for profile management | Large scope — defer, document web handoff |

### P2 — Deferred / Web-Only

| # | Issue | Notes |
|---|-------|-------|
| 7 | Google Calendar management | Web feature, mobile shows status only |
| 8 | Staff/Client profile CRUD | Web feature, complex forms |
| 9 | Bulk operations | Web-only by design |
| 10 | Data export | Web-only by design |

---

## 4. Root-Cause Investigation: Missing Client Appointments

### Possible Causes

| # | Hypothesis | How to Verify |
|---|-----------|---------------|
| 1 | **Client email/profile not linked in Cognito** | Check `resolve_client_identity()` — does the client's Cognito `sub` or email match a CLIENT# profile? |
| 2 | **client_id mismatch** | The mobile app's client API path (`/client/requests`) uses `resolve_client_identity()` → if no match, returns empty |
| 3 | **Appointments exist but under different client_id** | Query DynamoDB for REQ# records with `client_email = brearockwell@gmail.com` |
| 4 | **Case sensitivity** | Cognito email may be `BreaRockwell@gmail.com` but records stored with lowercase |
| 5 | **Portal not enabled** | `portal_enabled` flag on client profile may be false |
| 6 | **Company/tenant mismatch** | Client profile's `company_id` doesn't match API company resolution |
| 7 | **Requests exist but in terminal status** | All bookings for this client may be COMPLETED/ARCHIVED/CANCELLED |

### Investigation Steps (For AG — After Matthew Approves)

1. Query DynamoDB: find CLIENT# profile where email matches `brearockwell@gmail.com`
2. Check profile: `cognito_sub`, `portal_enabled`, `is_active`, `company_id`
3. Query REQ# records with matching `client_id` — check statuses
4. Check Cognito user attributes: `sub`, `email`, `email_verified`
5. Compare with what `resolve_client_identity()` would resolve for this user's JWT

---

## 5. Fix Details: P0 Items

### Fix 1: Login Error Feedback

**Current:** Wrong password → no visible feedback (button may briefly disable then reset)
**Expected:** Red error message: "Incorrect email or password. Please try again."

**Implementation:** In `LoginScreen.tsx`, display the error message from Cognito's `authenticateUser` `onFailure` callback. The error object has a `message` field.

### Fix 2: Forgot Password Flow

**Current:** No password reset option visible on login screen.
**Expected:** "Forgot password?" link → email input → Cognito sends reset code → user enters code + new password.

**Implementation:**
- Add "Forgot Password?" link below login button
- New screen: `ForgotPasswordScreen.tsx`
- Uses Cognito SDK: `cognitoUser.forgotPassword()` → `cognitoUser.confirmPassword(code, newPassword)`
- Navigation: Login → Forgot Password → Confirm Reset → Login

### Fix 3: Investigate Client Appointments

**Current:** `brearockwell@gmail.com` sees no appointments.
**Expected:** Should see their bookings if linked correctly.

**Implementation:** AG investigates DynamoDB + Cognito linkage (read-only). May be a backend identity resolution issue, or the client simply has no active bookings.

### Fix 4: Welcome Header Personalization

**Current:** `DashboardScreen.tsx` shows hardcoded "Welcome back, Ryan"
**Expected:** "Welcome back, {user_email}" or "Welcome back, {display_name}" from the auth context.

**Implementation:** In `DashboardScreen.tsx`, replace hardcoded "Ryan" with `user` from `useAuth()` hook (which contains the email). Or resolve display name from the Cognito session claims.

---

## 6. Product Roadmap Backlog (Deferred — NOT Release 10H)

### Multi-Business / SaaS Architecture (Release 11+)

| Item | Description | Phase |
|------|-------------|-------|
| Multi-business landing zone | App shows list of businesses the owner manages | 11A |
| Tenant/package/tier model | Business owners select their purchased service tier | 11B |
| Self-service provisioning | New business owner signs up → gets their own tenant | 11C |
| Branding/logo/naming support | Each tenant has custom logo and business name | 11C |
| AI-assisted onboarding | ML helps configure services, scheduling, pricing | 12+ |
| Video visit evidence | Staff records visit clips for client verification | 12+ |
| Payment/subscription/billing | Stripe or similar for business owner subscriptions | 11D |
| Access gating by tier | Feature availability based on subscription level | 11D |

**These items are explicitly deferred.** The current app serves a single business (Tog & Dogs). Multi-tenant architecture is a separate strategic initiative that should be planned after Ryan validates the single-tenant workflow.

---

## 7. Recommendation

### Immediate (Release 10H)

Fix the 4 P0 items:
1. Login error feedback (mobile-only, LoginScreen.tsx)
2. Forgot password flow (mobile-only, new screen + Cognito SDK)
3. Investigate client appointments (read-only DynamoDB/Cognito check)
4. Fix welcome header (mobile-only, DashboardScreen.tsx)

**Estimated effort:** 2-4 hours for AG implementation.

### After P0 Fixes

- Rebuild TestFlight (same `eas build + eas submit` flow)
- Re-validate with Matthew
- When clean: proceed to Gate D (add Ryan as External TestFlight tester)

### Deferred

- Multi-tenant architecture → Release 11 planning
- Admin management features → remain web-only
- Google Calendar mobile connect → document "use web for this"
- Billing/payment → separate initiative
- Video/AI → far future

---

## 8. Proposed Release 10H Scope (For AG)

```
Release 10H — Mobile P0 Fixes (Login Error, Forgot Password, Welcome Header)

Files to modify:
- mobile/src/screens/LoginScreen.tsx (error display + forgot password link)
- mobile/src/screens/ForgotPasswordScreen.tsx (NEW — reset flow)
- mobile/src/screens/DashboardScreen.tsx (fix hardcoded "Ryan")
- mobile/src/auth/cognito.ts (add forgotPassword + confirmPassword functions)
- mobile/src/navigation/AuthNavigator.tsx (add ForgotPassword route)

Investigation (read-only, no changes):
- Query DynamoDB for brearockwell@gmail.com client profile
- Check client_id linkage and appointment status
- Report findings before proposing a fix

Backend changes: None expected (unless investigation reveals a bug)
Web changes: None
Terraform: None
```

---

## 9. AG Implementation Prompt Draft (Release 10H)

**⚠️ DO NOT RUN UNTIL MATTHEW APPROVES**

```
AG — implement Release 10H: Mobile P0 Fixes.

Mobile-only changes unless investigation reveals a backend issue.

=== Fix 1: Login Error Feedback ===

In mobile/src/screens/LoginScreen.tsx:
- Display error message from Cognito onFailure callback
- Show red error text below the password field: "Incorrect email or password."
- Clear error on next login attempt
- Handle common Cognito error codes:
  - NotAuthorizedException → "Incorrect email or password."
  - UserNotFoundException → "No account found with this email."
  - UserNotConfirmedException → "Account not confirmed. Check your email."

=== Fix 2: Forgot Password Flow ===

a) Add to mobile/src/auth/cognito.ts:
   - forgotPassword(email): calls cognitoUser.forgotPassword()
   - confirmForgotPassword(email, code, newPassword): calls cognitoUser.confirmPassword()

b) Create mobile/src/screens/ForgotPasswordScreen.tsx:
   - Step 1: Enter email → send reset code
   - Step 2: Enter code + new password → confirm reset
   - Success: navigate back to login with "Password reset successful" message

c) Update mobile/src/navigation/AuthNavigator.tsx:
   - Add ForgotPasswordScreen to the auth stack

d) In LoginScreen.tsx:
   - Add "Forgot Password?" link below the login button

=== Fix 3: Investigate Client Appointments ===

READ-ONLY investigation. Do NOT modify data.

1. Query DynamoDB for CLIENT# profile matching email "brearockwell@gmail.com"
2. Report: client_id, cognito_sub, portal_enabled, is_active, company_id
3. Query REQ# records with that client_id → report statuses
4. Check if the mobile /client/requests API path would resolve this user
5. Report findings. Do NOT fix until Matthew reviews.

=== Fix 4: Welcome Header ===

In mobile/src/screens/DashboardScreen.tsx:
- Replace hardcoded "Welcome back, Ryan" with dynamic user info
- Use: const { user } = useAuth();
- Display: "Welcome back, {user}" (user is the email from auth context)
- If display_name is available from Cognito claims, prefer that

=== Validation ===

- npx tsc --noEmit
- npx expo start --port 8082
- Test: wrong password → error message shown
- Test: Forgot Password flow end-to-end
- Test: Dashboard shows actual user email, not "Ryan"
- Report: client investigation findings

Do NOT modify backend, web, Terraform, or AWS.
Do NOT run EAS build or EAS submit (separate approval needed for new TestFlight build).

Return: files changed, TypeScript result, test observations, client investigation findings.
```

---

## 10. Approval Gates

| Gate | Action | Approver |
|------|--------|----------|
| **Gate 1** | Approve Release 10H mobile P0 fixes | Matthew |
| **Gate 2** | Approve client investigation findings + fix (if backend) | Matthew |
| **Gate 3** | Approve new EAS build + TestFlight upload after fixes | Matthew |
| **Gate 4** | Approve Gate D — add Ryan as external tester | Matthew (future) |

---

## 11. What This Document Does NOT Authorize

- ❌ Modifying mobile code
- ❌ Modifying backend code
- ❌ Running EAS build or submit
- ❌ Adding TestFlight testers
- ❌ Modifying App Store Connect
- ❌ Modifying DynamoDB data
- ❌ Changing AWS/Terraform/production

Planning and triage only. Each fix requires separate explicit approval.
