# Release 6E: User Permissions & Identity Alignment — Plan

## Status: ✅ DEPLOYED & PRODUCTION VALIDATED (2026-05-21)

**Commit:** `79b2b89b87ae2ad7af576fa373f71b2de740b057`
**Deployment:** Terraform 9 Lambdas updated + Frontend S3/CloudFront
**Tests:** 60/60 backend tests passed, 16/16 identity tests passed
**Validation:** Admin messaging, phone normalization, and protected email guardrail all confirmed working

## Objective
Clarify and harden the identity model across Cognito, DynamoDB profiles, and the Admin/Client portals. Prevent accidental data overwrites, protect admin accounts, and support offline clients.

## Current Identity Model (As Implemented)

### Source of Truth

| Data | Source of Truth | Sync Direction |
|------|----------------|----------------|
| `display_name`, `phone`, `notes` | DynamoDB (STAFF#/CLIENT# record) | DynamoDB → Cognito (one-way push) |
| `email` (login identifier) | Cognito | Written to DynamoDB on creation/link |
| Login status (`UserStatus`) | Cognito | Read-only enrichment into DynamoDB |
| Group membership (role) | Cognito | Read-only; DynamoDB `role` field is informational |
| `cognito_sub` | Cognito | Written to DynamoDB on creation/link |
| `portal_enabled` | DynamoDB | Not synced to Cognito |

### Role Priority (Both Frontend & Backend)
```
owner > admin > staff > client > unknown
```

### Access Matrix (Current)

| Route/Feature | Owner | Admin | Staff | Client |
|---------------|-------|-------|-------|--------|
| Admin Dashboard | ✅ | ✅ | Scheduler only | ❌ |
| Request List | ✅ | ✅ | ❌ | ❌ |
| Staff Management | ✅ | ✅ | ❌ | ❌ |
| Client Management | ✅ | ✅ | ❌ | ❌ |
| Data Export | ✅ | ✅ | ❌ | ❌ |
| Client Portal (/my-bookings) | ✅ (blocked by resolver) | ✅ (blocked by resolver) | ❌ (explicit block) | ✅ |
| Public Intake Form | ✅ | ✅ | ✅ | ✅ |

### Protected Account Guardrails (Current)
- Hardcoded: `PROTECTED_SUBS = ["74b86488-1011-7029-bb6d-dad984e1463c"]`
- Hardcoded: `PROTECTED_USERNAMES = ["admin@toganddogs.com", "mbn@usmissionhero.com"]`
- Blocks: DELETE, disable, unlink, delete_profile, delete_cognito, role change, email change
- Self-protection: cannot disable/delete your own account
- Audit-logged when blocked

---

## Confirmed: Cognito Does NOT Overwrite DynamoDB

**Finding:** There is NO code path that reads Cognito attributes and writes them back to DynamoDB profiles. The sync is strictly one-directional:
- DynamoDB `display_name` → Cognito `name` attribute (best-effort push on PATCH)
- DynamoDB `phone` → Cognito `phone_number` (best-effort push on PATCH, E.164 only)

**The reported "Cognito overwriting website-edited fields" is NOT happening in the current code.** If display names appear to revert, the likely cause is:
1. The staff list merge showing `cu['Username']` (Cognito username = email) for "virtual" profiles that haven't been linked to a DynamoDB profile yet
2. Or a stale browser cache showing old data

---

## Issues to Address

### Issue 1: Client Portal Blocked for Owner/Admin
- **Current:** `resolve_client_identity()` returns None for non-client roles
- **Impact:** Owner/admin with linked client profiles can't use /my-bookings
- **Fix options:** (a) Show clear message, (b) Allow resolution for explicitly linked accounts
- **Recommendation:** Option (a) for now — clear message explaining admin accounts can't use client portal

### Issue 2: Offline Clients Without Cognito Login
- **Current:** Supported via "profile_only" creation mode (no Cognito user created)
- **Status:** Already working. `cognito_status = "not_linked"`, `portal_enabled = False`
- **No code change needed** — just document the workflow

### Issue 3: Phone Number Normalization
- **Current:** Cognito sync only pushes phone if it matches E.164 format
- **Impact:** Non-E.164 phones (e.g., "555-1234") are stored in DynamoDB but not synced to Cognito
- **Recommendation:** Add frontend validation/formatting before save, or normalize on backend before Cognito push

### Issue 4: Staff Access Scope
- **Current:** Staff can view Scheduler but not Request List, Staff Management, or Client Management
- **Status:** Already enforced via `capabilities` object
- **No code change needed** — already correct

### Issue 5: Virtual Staff Profiles
- **Current:** Cognito users without DynamoDB profiles appear as "virtual" with `display_name = Username` (email)
- **Impact:** These show email as the display name until linked to a real profile
- **Recommendation:** Document as expected behavior. Admin should link virtual profiles to create proper display names.

---

## Target Identity Model (Recommended)

### No Architecture Changes Needed
The current model is sound:
- DynamoDB is the profile data store (display_name, phone, notes, business fields)
- Cognito is the auth provider (login, password, groups, session)
- Sync is one-directional (DynamoDB → Cognito for name/phone only)
- Protected accounts are guarded

### Recommended Improvements (Release 6E Scope)

| Improvement | Type | Effort |
|-------------|------|--------|
| Clear message for admin/owner on /my-bookings | Frontend | 30 min |
| Phone normalization helper (E.164) | Frontend + Backend | 1-2 hrs |
| Document identity model in project-control | Docs | 30 min |
| Warn before linking protected email to client profile | Backend | 1 hr |
| Add `is_protected` check to client auto-profile creation | Backend | 30 min |

---

## Phased Implementation Plan

### Phase 1: Documentation & Client Portal Message (Low Risk)
1. Add identity model documentation to `docs/project-control/`
2. In `ClientPortal.jsx`: detect owner/admin role and show clear message instead of "not linked" error
3. No backend changes

**Files:** `web/src/components/ClientPortal.jsx`, docs
**Effort:** ~1 hour

### Phase 2: Phone Normalization (Low Risk)
1. Add phone formatting helper (strip non-digits, add +1 if 10 digits)
2. Apply on staff/client PATCH before Cognito sync
3. Optionally add frontend input mask

**Files:** `src/backend/handlers/admin_handler.py`, optionally `web/src/components/AdminDashboard.jsx`
**Effort:** ~2 hours

### Phase 3: Protected Email Guardrails (Medium Risk)
1. Before auto-creating client profile (`client_profile.py`): check if email belongs to a protected admin/staff account
2. Before "Link Login Account": warn if target Cognito user is in owner/admin/Staff group
3. Add audit log entry for blocked auto-link attempts

**Files:** `src/backend/common/client_profile.py`, `src/backend/handlers/admin_handler.py`
**Effort:** ~2 hours

### Phase 4: Deferred / Future
- Full client portal access for admin/owner (requires careful design)
- Multi-tenant company_id from Cognito custom claims
- Staff scheduling view restrictions (only see own assignments)
- Cognito attribute sync improvements

---

## AG Validation Plan

### Phase 1
1. Log in as owner → navigate to /my-bookings → confirm clear message (not confusing "not linked" error)
2. Log in as staff → confirm /my-bookings is blocked with "Staff must use Staff Portal"
3. Log in as client → confirm /my-bookings works normally

### Phase 2
1. Edit a staff profile phone to "555-1234" → confirm it's normalized before Cognito sync
2. Edit to "+15551234567" → confirm it syncs to Cognito correctly

### Phase 3
1. Submit intake with `mbn@usmissionhero.com` → confirm auto-profile creation is blocked/warned
2. Attempt "Link Login Account" with a protected admin email → confirm warning shown

---

## Risks / Blockers

| Risk | Mitigation |
|------|-----------|
| Phase 1 message change could confuse existing admin users | Make message clear and actionable |
| Phone normalization could reject valid international formats | Only normalize US numbers; pass through others |
| Protected email check could block legitimate dual-role users | Allow with explicit admin confirmation |

---

## What Should Remain Deferred
- Full admin/owner client portal access (complex design implications)
- Multi-tenant Cognito custom claims
- Staff-only scheduling view restrictions
- Cognito → DynamoDB reverse sync (not needed, current model is correct)
- Route-level protection in App.jsx (current component-level checks are sufficient)
