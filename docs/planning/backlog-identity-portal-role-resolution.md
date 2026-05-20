# Backlog: Identity Portal Role Resolution Guardrail

## Priority: Medium
## Status: Planned (not started)
## Discovered During: Release 6B Phase 1 validation

## Problem Statement

The Client Portal frontend (`ClientPortal.jsx`) allows `owner`, `admin`, and `client` roles to access the portal UI. However, the backend `resolve_client_identity()` function in `src/backend/common/auth.py` only resolves client profiles for users with `role == 'client'`. This creates a confusing experience:

- An admin/owner who has a linked client profile sees "Your portal account is not yet linked to a client profile" in the portal
- The Admin Dashboard's Client Management correctly shows the profile as "linked" (reads `cognito_sub` directly)
- The mismatch is between what the Admin UI shows and what the Client Portal can resolve

## Root Cause

```python
# src/backend/common/auth.py — resolve_client_identity()
if get_effective_role(event) != 'client':
    return None  # Short-circuits for owner/admin/staff
```

## Proposed Resolution Options

### Option A: Block admin/owner from Client Portal with clear message
- In `ClientPortal.jsx`, detect `owner`/`admin` role and show:
  "You are logged in as an administrator. Admin accounts cannot access the client portal. Please use a dedicated client login."
- Simplest, no backend change needed

### Option B: Allow explicit resolution for admin/owner when deliberately linked
- Modify `resolve_client_identity()` to also resolve for `owner`/`admin` roles
- Requires careful design to avoid mixing admin and client contexts
- May need a "viewing as client" mode toggle

### Option C: Hybrid
- Allow admin/owner to view their own client bookings in a read-only mode
- Do not allow admin/owner to submit new requests from the client portal
- Show a banner: "Viewing as linked client profile"

## Guardrails to Add

1. **Warn before linking protected accounts:** When using "Link Login Account" in Client Management, warn if the target Cognito user is in the `owner`, `admin`, or `Staff` group.
2. **Prevent auto-created client profiles for admin/staff emails:** The `auto_create_or_link_client_profile()` function should check if the email belongs to an existing admin/staff Cognito user before creating a client profile.
3. **UI consistency:** Do not show "Linked" badge in Admin Client Management unless the persisted fields match what the Client Portal actually uses for resolution.

## Files Involved
- `src/backend/common/auth.py` — `resolve_client_identity()`
- `web/src/components/ClientPortal.jsx` — role check and error display
- `src/backend/handlers/admin_handler.py` — link-cognito endpoint
- `src/backend/common/client_profile.py` — auto_create_or_link_client_profile

## Dependencies
- None (standalone improvement)
- Should NOT be bundled with notification releases

## Acceptance Criteria
- Admin/owner accounts get a clear, non-confusing experience when accessing /my-bookings
- No accidental client profile creation for admin/staff emails without explicit confirmation
- Admin UI "linked" badge accurately reflects what the portal can resolve
