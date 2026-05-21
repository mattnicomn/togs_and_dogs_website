# Backlog: User Permissions & Identity Guardrails

## Priority: Medium
## Status: Planned

## Items

### 1. Client Portal Identity Resolution
- **File:** `docs/planning/backlog-identity-portal-role-resolution.md` (already created)
- **Issue:** Admin/owner accounts can't use client portal because `resolve_client_identity()` only resolves for `role == 'client'`
- **Impact:** Blocks testing and creates confusing UX for linked admin accounts

### 2. Admin/Staff Email Protection on Auto-Profile Creation
- **Issue:** `auto_create_or_link_client_profile()` can create client profiles for admin/staff emails
- **Impact:** Creates identity confusion (same email = admin login + client profile)
- **Fix:** Check if email belongs to an existing admin/staff Cognito user before auto-creating

### 3. Protected Account Linking Warning
- **Issue:** "Link Login Account" in Client Management doesn't warn when linking a protected admin/owner account
- **Impact:** Creates the portal resolution mismatch described in item 1
- **Fix:** Show warning in Admin UI before linking protected accounts to client profiles

## Related Decisions
- Do NOT modify `resolve_client_identity()` as part of notification releases
- Identity changes require their own dedicated release with careful testing
