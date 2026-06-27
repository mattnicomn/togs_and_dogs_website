# Release 19F: Second-Tenant Owner Cognito User Planning and Approval Gate

**Status:** Planning
**Date:** 2026-06-26
**Priority:** High (next step for tenant isolation validation)
**Scope:** Plan safe Cognito user creation for test_tenant_alpha owner without executing it

---

## 1. Existing Cognito User/Group Model

### Required User Attributes

| Attribute | Type | Required? | Purpose |
|-----------|------|-----------|---------|
| `email` (username) | Standard | Yes | Login identifier |
| `email_verified` | Standard | Yes (set to true) | Prevents verification email loop |
| `custom:company_id` | Custom (String) | Yes (for strict mode) | Routes user to correct tenant |

### Groups

| Group | Role | Access |
|-------|------|--------|
| `owner` | Tenant owner/admin | Full business admin access for their tenant |
| `admin` | Tenant admin | Same as owner (currently equivalent) |
| `staff` | Staff member | Schedule, visits, completion |
| `client` | Client/pet owner | Client portal view |
| `platform_admin` | usmissionhero operator | Cross-tenant platform management |

### Required Group for New Tenant Owner

**`owner`** — grants business admin access scoped to `custom:company_id`

### Groups That MUST NOT Be Used

| Group | Why Not |
|-------|---------|
| `platform_admin` | Reserved for usmissionhero operators only. NEVER assign to tenant owners. |
| `staff` | Wrong role — owner needs full admin access |
| `client` | Wrong role — owner needs admin capabilities |

### Temporary Password / Reset Flow

- Create user with temporary password (`--permanent false`)
- User must change password on first login (Cognito `FORCE_CHANGE_PASSWORD` state)
- Password provided to Matthew privately — NEVER in docs/chat/repo
- After first login, user sets own permanent password

### Email Verification

- Set `email_verified = true` at creation time (admin-created user)
- This prevents Cognito from sending a verification email
- The user still gets the temporary-password reset flow on first login

---

## 2. Approved Future Owner-User Pattern

| Field | Value | Notes |
|-------|-------|-------|
| Username/email | `<owner-email-provided-privately>` | Matthew provides at approval time |
| `custom:company_id` | `test_tenant_alpha` | Matches tenant metadata |
| Group membership | `owner` | Business admin access |
| NOT in group | `platform_admin` | Never for tenant owners |
| Password | Set by Matthew privately | Not documented |
| Email verified | `true` | Skip verification email |
| Account status | Enabled | Active on creation |

### CLI Template (For AG to Output During Execution)

```powershell
# Create user:
aws cognito-idp admin-create-user ^
  --user-pool-id <POOL_ID> ^
  --username <OWNER_EMAIL> ^
  --temporary-password <TEMP_PASSWORD> ^
  --user-attributes Name=email,Value=<OWNER_EMAIL> Name=email_verified,Value=true Name=custom:company_id,Value=test_tenant_alpha ^
  --message-action SUPPRESS ^
  --profile usmissionhero-website-prod

# Add to owner group:
aws cognito-idp admin-add-user-to-group ^
  --user-pool-id <POOL_ID> ^
  --username <OWNER_EMAIL> ^
  --group-name owner ^
  --profile usmissionhero-website-prod
```

**`--message-action SUPPRESS`** prevents Cognito from sending a welcome email. Matthew communicates credentials privately.

---

## 3. Approval Gates Before User Creation (19G)

| # | Gate | Matthew Confirms |
|---|------|------------------|
| G1 | Owner email address (provided privately, not in docs) | "Use [address]" |
| G2 | Creation method: AG executes CLI, or Matthew creates in Console | Choice |
| G3 | Temporary password approach: Matthew sets, or uses generated | Choice |
| G4 | Email suppression: do not send Cognito welcome email | "Agreed — SUPPRESS" |
| G5 | Group: `owner` only (NOT platform_admin) | "Confirmed" |
| G6 | Login test scope (Matthew logs in manually to verify) | "Will test" |
| G7 | Rollback plan: disable user if access is wrong | "Understood" |
| G8 | Explicit "Approved: create the Cognito user" | Final go-ahead |

---

## 4. Safe Creation Sequence (Release 19G)

| Step | Action | Writes? |
|------|--------|---------|
| 1 | Pre-check: `TENANT#test_tenant_alpha / METADATA` exists in DynamoDB | Read-only |
| 2 | Pre-check: no existing user with this email in Cognito | Read-only |
| 3 | Matthew provides owner email + temporary password privately | N/A |
| 4 | AG (or Matthew) executes `admin-create-user` CLI command | ✅ Cognito write |
| 5 | AG (or Matthew) executes `admin-add-user-to-group` (owner) | ✅ Cognito write |
| 6 | Verify: user exists with correct attributes | Read-only |
| 7 | Verify: user is in `owner` group only | Read-only |
| 8 | Verify: user is NOT in `platform_admin` | Read-only |
| 9 | Report safe summary (no credentials in output) | Documentation |

### What Is NOT Done During 19G

- ❌ No login test (Matthew does this manually in 19H)
- ❌ No booking/client/pet creation
- ❌ No Google Calendar setup
- ❌ No Stripe/payment setup
- ❌ No App Store/mobile changes

---

## 5. Post-Creation Validation (Release 19H)

After user exists, Matthew manually validates:

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | Login as test_tenant_alpha owner | Browser → login page | Completes password change, sees dashboard |
| 2 | `/admin` loads | Browser | Empty dashboard (no data yet for this tenant) |
| 3 | No tog_and_dogs data visible | Visual check | Zero requests, zero staff, zero clients |
| 4 | Platform Admin still shows both tenants | Login as Matthew/platform_admin | Both tog_and_dogs and test_tenant_alpha visible |
| 5 | Tenant-resolution alarms remain OK | CloudWatch | No fallback/failed events |
| 6 | `ENTITLEMENT_ALLOWED` logged for test_tenant_alpha | CloudWatch admin logs | Entry present on login/dashboard load |
| 7 | Export is blocked (starter tier) | Attempt GET /admin/export-data | 403 (entitlement denied) |
| 8 | Google Calendar connect blocked (starter) | Attempt GET /admin/auth/google | 403 |
| 9 | Logout works | Click logout | Returns to login |

---

## 6. Rollback / Disable Strategy

| Scenario | Action |
|----------|--------|
| User accesses wrong tenant data | Disable user immediately in Cognito Console |
| User is in wrong group | Remove from group via Console/CLI |
| User needs full removal | Disable (do not delete unless separately approved) |
| Strict-mode alarm fires | Investigate; do NOT disable strict mode unless Matthew explicitly approves global rollback |
| tog_and_dogs access is affected | Should not be — investigate without modifying strict mode |

### Disable Commands (If Needed)

```powershell
aws cognito-idp admin-disable-user ^
  --user-pool-id <POOL_ID> ^
  --username <OWNER_EMAIL> ^
  --profile usmissionhero-website-prod
```

---

## 7. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **19F** | Cognito user planning + approval gate (this document) | ✅ Kiro (done) |
| **19G** | Matthew approval + Cognito user creation execution | Matthew + AG |
| **19H** | Manual login test + tenant isolation validation | Matthew |
| **19I** | Entitlement denial-path validation (starter tier) | AG + Matthew |
| **19J** | Second-tenant operational readiness closeout | Kiro |

---

## 8. What This Document Does NOT Authorize

- ❌ Creating Cognito users
- ❌ Generating or documenting passwords
- ❌ Modifying Cognito groups
- ❌ Modifying tenant metadata
- ❌ DynamoDB writes
- ❌ Terraform/AWS changes
- ❌ Code changes or deployment
- ❌ Stripe/Postmark/payment changes
- ❌ Google Calendar changes
- ❌ Mobile/EAS/TestFlight/App Store changes
- ❌ Ryan/tester additions
- ❌ Changing TENANT_RESOLUTION_MODE

This is a planning document. User creation (19G) requires Matthew's explicit approval at all 8 gates.
