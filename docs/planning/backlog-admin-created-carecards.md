# Backlog: Admin-Created CareCards / Visits

## Priority: Medium
## Status: Planned

## Problem
Currently, all service requests must be submitted through the public intake form or the client portal. There is no way for an owner/admin/staff to create a CareCard or visit directly from the Admin Dashboard on behalf of a client.

This is a problem for:
- Offline or non-tech-savvy clients who call/text to book
- Staff who need to quickly schedule a visit without going through the public form
- Admin who wants to create a booking linked to an existing client/pet profile

## Desired Behavior
1. Owner/admin opens Admin Dashboard
2. Clicks "New Visit" or "Create CareCard"
3. Selects existing client profile (or creates inline)
4. Selects existing pet(s) from that client's profile
5. Fills in: service type, date/time, notes
6. Submits → creates a VISIT_BOOKING request in APPROVED or PENDING_REVIEW status
7. Request appears in the normal workflow (assignable, schedulable, notifiable)
8. Audit trail records who created it and when

## Key Requirements
- Must link to existing client profile (CLIENT# record) where possible
- Must link to existing pet records (PET# records) where possible
- Must set `workflow_type = VISIT_BOOKING` (not CUSTOMER_INTAKE)
- Must preserve full audit trail
- Must trigger appropriate notifications (REQUEST_RECEIVED to admin, or skip if admin is creating)
- Must NOT force staff through the public Service Request form
- Must NOT require the client to have portal access or Cognito login

## Distinction from Other Backlog Items
- **This is NOT the same as "CareCard pet loading failures"** (that's a rendering bug)
- **This is NOT the same as "repeat customer booking"** (that's client-portal-initiated)
- This is an **admin-initiated creation flow** for operational convenience

## Proposed Implementation
1. New button in Admin Dashboard: "+ New Visit" (visible to owner/admin)
2. Modal or inline form with client selector, pet selector, service fields
3. Backend: new endpoint or reuse intake handler with `source: 'admin_created'` flag
4. Skip M&G/quote requirements for admin-created visits (or make configurable)
5. Auto-set status to APPROVED (admin is creating it, no review needed)

## Files Likely Involved
- `web/src/components/AdminDashboard.jsx` — new UI button/modal
- `src/backend/handlers/intake_handler.py` or new handler — creation logic
- `web/src/api/client.js` — new API call

## Effort: 6-10 hours
## Depends On: Nothing (standalone feature)
