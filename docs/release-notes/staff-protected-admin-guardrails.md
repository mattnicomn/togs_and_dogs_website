# Protected Admin Guardrails

## Summary
Implements security guardrails to prevent accidental deletion, disabling, or unlinking of platform administration accounts and the currently logged-in user's own profile. This addresses the recent incident where the primary admin account was accidentally disabled.

## Key Changes
- **Protected Accounts**: Hardcoded protection for `admin@toganddogs.com` and Cognito sub `74b86488-1011-7029-bb6d-dad984e1463c`.
- **Self-Protection**: Prevent users from disabling or deleting their own accounts.
- **Backend Enforcement**: 
    - Block `DELETE` and `PATCH` actions (`disable`, `unlink`, `delete_profile`, `delete_cognito`) for protected accounts.
    - Log blocked attempts as `BLOCKED_PROTECTED_ACCOUNT_ACTION`.
    - Prevent changing login email/identity for protected profiles.
- **Frontend UI Enhancements**:
    - "Protected Platform Admin" label for identified accounts.
    - Dangerous buttons are hidden or disabled for protected and self profiles.
    - "Email" field renamed to "Contact Email" for protected profiles, with the login identity shown as read-only.
- **Default Assignability**: Administrative roles (`owner`, `admin`) now default to `is_assignable: false` upon creation.

## Verification
- Backend tests for RBAC and purge safety passed.
- Frontend build succeeded.
- Manual logic verification for protected account detection.
