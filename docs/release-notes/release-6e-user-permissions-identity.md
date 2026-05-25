# Release 6E: User Permissions & Identity Alignment

## Overview
Improves identity-related UX messaging, adds phone normalization for Cognito sync, and adds guardrails to prevent protected admin accounts from being accidentally auto-linked as client profiles.

## Status: ✅ Deployed & Production Validated (2026-05-21)

## Deployment
- **Commit:** `79b2b89b87ae2ad7af576fa373f71b2de740b057`
- **Terraform:** 0 added, 9 changed, 0 destroyed (Lambda code hash updates only)
- **Frontend:** Built, synced to S3 (`togs-and-dogs-prod-toganddogs-hosting`)
- **CloudFront:** Invalidation `I8GIERNNU4S68AA6XEMW05JNWV` on distribution `E35L00QPA2IRCY`
- **Backend tests:** 60/60 passed
- **Release 6E identity tests:** 16/16 passed

## Changes

### 1. Client Portal Role-Based Messaging (Frontend)
**File:** `web/src/components/ClientPortal.jsx`

- Admin/owner accessing /my-bookings now sees: "You are signed in as an administrator. The Client Portal is for client accounts only. To view client bookings, use the Admin Dashboard."
- Staff still sees: "Access denied. Staff members must use the Staff Portal."
- Real unlinked clients still see: "Your portal account is not yet linked to a client profile. Please contact support."
- No security behavior changed — only the error message text is improved

### 2. Phone Normalization for Cognito Sync (Backend)
**File:** `src/backend/handlers/admin_handler.py`

Added `normalize_phone_e164()` helper that normalizes common US phone formats before Cognito sync:
- `5551234567` → `+15551234567`
- `(555) 123-4567` → `+15551234567`
- `1-555-123-4567` → `+15551234567`
- `+15551234567` → unchanged
- Invalid/un-normalizable → returns None (Cognito sync skipped gracefully)

Applied to both staff PATCH and client PATCH Cognito sync paths.

### 3. Protected Email Guardrail (Backend)
**File:** `src/backend/common/client_profile.py`

- `auto_create_or_link_client_profile()` now checks if the email is in a protected list before creating
- Protected emails: `admin@toganddogs.com`, `mbn@usmissionhero.com`, `support@usmissionhero.com`
- Returns `SKIPPED_PROTECTED_EMAIL` status — does not block the approval workflow
- Prevents identity confusion from admin accounts being auto-linked as client profiles

### 4. Tests
**File:** `tests/backend/test_r6e_identity.py` (16 tests)

- 14 phone normalization tests (various formats, edge cases, international)
- 2 protected email guardrail tests (blocked + allowed)

## Production Validation Results

| Check | Result |
|-------|--------|
| Admin /my-bookings messaging | ✅ Clear admin-specific message shown |
| Staff /my-bookings access | ✅ Denied with staff-specific message |
| Unlinked client message | ✅ Unchanged |
| Phone normalization (US formats) | ✅ Cognito sync succeeds |
| Protected email auto-profile | ✅ Skipped with SKIPPED_PROTECTED_EMAIL |
| Backend tests | ✅ 60/60 passed |
| Identity tests | ✅ 16/16 passed |

## Files Changed
- `web/src/components/ClientPortal.jsx`
- `src/backend/handlers/admin_handler.py`
- `src/backend/common/client_profile.py`
- `tests/backend/test_r6e_identity.py`

## Backlog Note
Protected emails are currently hardcoded in both `admin_handler.py` and `client_profile.py`. A future improvement should move these to environment variables or a DynamoDB configuration record for easier management without code deploys.
