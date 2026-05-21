# Backlog: Repeat Customer Profile Booking

## Priority: Medium
## Status: Planned

## Problem
Existing/returning clients cannot submit new booking requests from the client portal because:
1. The client portal requires `resolve_client_identity()` to return a valid `client_id`
2. `resolve_client_identity()` only works for `role == 'client'` (admin/owner blocked)
3. Even for real client-role users, the portal booking path (`POST /client/requests`) requires an approved client profile with `portal_enabled: True`

## Current Workaround
- Admin creates requests on behalf of clients via the public intake form
- Or admin uses the Admin Dashboard to manage bookings directly

## Desired Behavior
1. Returning client logs into portal
2. Client sees their booking history
3. Client can submit a new visit request (creates a VISIT_BOOKING, not CUSTOMER_INTAKE)
4. Request appears in admin queue for approval/scheduling

## Prerequisites
- Client portal identity resolution must work (backlog item)
- Client must have `portal_enabled: True` on their profile
- Client must have completed initial onboarding (M&G, etc.)

## Files Involved
- `web/src/components/ClientPortal.jsx` — booking submission UI
- `src/backend/handlers/intake_handler.py` — VISIT_BOOKING creation path
- `src/backend/common/auth.py` — `resolve_client_identity()`

## Effort: 4-8 hours
## Depends On: Client Portal Identity Resolution
