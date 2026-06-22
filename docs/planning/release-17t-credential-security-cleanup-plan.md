# Release 17T: Credential Security Cleanup Plan

**Status:** Planning — Awaiting Matthew Manual Execution
**Date:** 2026-06-21
**Priority:** High (security prerequisite for external testing and second-tenant creation)
**Scope:** Manual Cognito password rotation checklist for Matthew

---

## 1. Purpose

A shared/default development password was exposed in chat during earlier development. Before Ryan testing, second-tenant creation, or broader user onboarding can proceed, all Cognito users that may still be using that password must be reset.

**This is a manual Matthew action — not a code or infrastructure change.**

---

## 2. Affected User Categories

Matthew should review all Cognito users and identify any that may still use the exposed shared password:

| Category | Likely Affected? | Action |
|----------|-----------------|--------|
| Admin/owner test accounts | ⚠️ Possible | Reset if using shared password |
| Staff test accounts | ⚠️ Possible | Reset if using shared password |
| Client test accounts | ⚠️ Possible | Reset if using shared password |
| Matthew's primary admin account | ⚠️ Check | Reset if using shared password |
| Platform admin account | ⚠️ Check | Reset if using shared password |
| Legacy development accounts (no longer used) | ⚠️ Possible | Disable or reset |
| Real client accounts (if any exist) | Unlikely | Verify not using shared password |

**Do NOT list specific usernames or emails in repo documentation.**

---

## 3. Manual AWS Console Cleanup Steps

### Step 1: Open Cognito User Pool

1. Open AWS Console → Cognito → User Pools
2. Select the production user pool
3. Navigate to "Users" tab

### Step 2: Review User List

1. Review all users in the pool
2. For each user, assess whether they were created with the shared/default development password
3. Focus on accounts created during early development/testing phases

### Step 3: Force Password Reset

For each affected user:

1. Select the user
2. Choose "Reset password" or "Force change password"
3. **Preferred method:** Use "Admin set user password" with a unique temporary password + require change on next login
4. **Alternative:** Use "Send reset email" if the user has a valid email and should self-reset
5. Record privately (NOT in repo) which users were reset

### Step 4: Handle Legacy/Unused Accounts

For accounts that are no longer needed:
- **Option A:** Disable the account (preferred — reversible)
- **Option B:** Delete only if Matthew is certain it's unused and has no linked data
- Do NOT delete accounts without verifying they have no active DynamoDB references

### Step 5: Verify Platform Admin Access

After resets:
- Confirm Matthew can still log in with the primary admin account
- Confirm Matthew can still access `/admin` (business dashboard)
- Confirm Matthew can still access `/platform-admin` (platform console)
- Confirm staff test account login works (with new password)

---

## 4. Optional AWS CLI Approach

If Matthew prefers CLI over Console:

```powershell
# Force password reset (requires user to change on next login):
aws cognito-idp admin-reset-user-password ^
  --user-pool-id <USER_POOL_ID> ^
  --username <USERNAME> ^
  --profile usmissionhero-website-prod

# Or set a temporary password requiring change:
aws cognito-idp admin-set-user-password ^
  --user-pool-id <USER_POOL_ID> ^
  --username <USERNAME> ^
  --password <NEW_TEMPORARY_PASSWORD> ^
  --permanent false ^
  --profile usmissionhero-website-prod

# Disable an unused account:
aws cognito-idp admin-disable-user ^
  --user-pool-id <USER_POOL_ID> ^
  --username <USERNAME> ^
  --profile usmissionhero-website-prod

# List all users (to review):
aws cognito-idp list-users ^
  --user-pool-id <USER_POOL_ID> ^
  --profile usmissionhero-website-prod
```

### CLI Safety Notes

- Replace `<USER_POOL_ID>` with the actual pool ID (do NOT commit the ID)
- Replace `<USERNAME>` with each affected user
- Replace `<NEW_TEMPORARY_PASSWORD>` with a strong unique value (do NOT commit)
- Do NOT store passwords in scripts, logs, or repo
- Do NOT pipe output to files that might be committed
- Use `--permanent false` so user must change on first login

---

## 5. Verification Checklist

After Matthew completes all resets:

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | All affected users have been reset | Matthew's private record | ✅ Confirmed |
| 2 | No user remains on the exposed shared password | Matthew's assessment | ✅ Confirmed |
| 3 | Matthew platform_admin login works | Log in via web | ✅ Access restored |
| 4 | Matthew admin dashboard works | Navigate to /admin | ✅ Normal operation |
| 5 | Staff test account login works (with new password) | Log in via mobile/web | ✅ After password change |
| 6 | No tokens/secrets captured in repo/chat | Review | ✅ Clean |
| 7 | Cognito user pool is not modified beyond password resets | Verify no group/attribute changes | ✅ |

---

## 6. Documentation Boundary

### What SHOULD Be Documented in Repo (Closeout)

- ✅ Date credential cleanup was completed
- ✅ Number of users affected (count only)
- ✅ Categories reset (e.g., "2 test accounts reset, 1 disabled")
- ✅ Verification checklist results (pass/fail)
- ✅ Statement that no shared/default passwords remain active

### What MUST NOT Be Documented in Repo

- ❌ Usernames
- ❌ Email addresses
- ❌ Old or new passwords
- ❌ Temporary passwords
- ❌ Cognito user pool ID
- ❌ Raw `list-users` output
- ❌ Screenshots of Cognito Console
- ❌ Auth tokens or session data
- ❌ The exposed password value

---

## 7. Execution Flow

| Step | Actor | Action |
|------|-------|--------|
| 1 | Kiro | 17T planning document (this — done) |
| 2 | Matthew | Review checklist, identify affected users privately |
| 3 | Matthew | Execute password resets via AWS Console or CLI |
| 4 | Matthew | Verify login still works for all needed accounts |
| 5 | Matthew | Report completion to Kiro/AG (safe summary only) |
| 6 | Kiro/AG | Create 17U closeout documenting completion safely |

---

## 8. Recommended Release Sequence After 17T

| Release | Scope | Owner |
|---------|-------|-------|
| **17T** | Credential cleanup plan (this document) | ✅ Kiro (done) |
| **17U** | Credential cleanup closeout (Matthew reports safe summary) | Kiro |
| **17V** | Tenant provisioning runbook / seed tool design | Kiro |
| **17W** | Tenant provisioning implementation | AG |
| **17X** | Second-tenant dry run | AG + Matthew |
| **17Y** | Second-tenant UI/mobile isolation validation | AG |
| **18A** | Ryan testing re-entry gate | Kiro |

---

## 9. What This Document Does NOT Authorize

- ❌ Resetting passwords (Matthew does this manually after reviewing)
- ❌ Code changes
- ❌ Terraform/AWS infrastructure changes
- ❌ Cognito group/attribute changes
- ❌ DynamoDB writes
- ❌ Frontend/mobile deployment
- ❌ Stripe/Postmark changes
- ❌ Creating a second tenant
- ❌ Adding Ryan/testers

This is a planning checklist. Matthew executes manually at his discretion.
