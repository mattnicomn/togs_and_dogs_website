# Phase 5C: Client Portal Booking Ownership and Boundaries

## Objective
Enforce secure ownership-based access control for the Client Portal, ensuring logged-in clients can only access and manage their own bookings, pets, and profile data while preventing unauthorized access to administrative data or cross-tenant scope.

## Discovery Findings
- The original Client Portal relied heavily on client-side array filtering (`r.client_email === userEmail`) against the generic `/admin/requests?status=ALL` endpoint.
- There were no dedicated safe backend routing boundaries exclusively for client identities.
- Repeat client requests on the Intake Form required re-entering names and emails manually.

## Architectural Changes & Enforcement Details

### Client Identity Resolution
- The core auth library (`src/backend/common/auth.py`) was extended with a `resolve_client_identity` helper.
- The system now extracts `sub` and `email` claims from the verified Cognito JWT token and dynamically matches them to local DynamoDB `CLIENT#{client_id}` profiles to map the active session's data boundaries without hardcoding frontend secrets.

### Backend Data Boundaries & Routing
- New `/client/requests` and `/client/pets` routes were established securely in Terraform mapping to the existing backend lambdas (`admin_handler` and `pet_handler`).
- Admin endpoints were explicitly hardened to reject requests originating from the `client` scope role.
- Dynamic table scans filtered by the resolved `client_id` replaced full table pulls.
- `sanitize_booking_for_role` logic was augmented with aggressive contextual redactions for clients, aggressively filtering internal arrays such as:
  - `staff_assignment`
  - `worker_id`
  - `job_id`
  - `assignment_color`

### Frontend Client Portal and Self-Service
- Swapped unsafe client-side data filters with safe server-side queries via `getClientRequests`.
- Reused the core `IntakeForm` by mapping an authenticated "New Request" button inside the Client Portal.
- Conditionally mapped `submitClientRequest` onto `IntakeForm` submissions if an active `client` session is detected.
- The `IntakeForm` now safely pre-fills `client_email` and `client_name` derived securely from the authenticated ID token claims.

## Files Changed
- `src/backend/common/auth.py`
- `src/backend/handlers/admin_handler.py`
- `src/backend/handlers/intake_handler.py`
- `src/backend/handlers/pet_handler.py`
- `modules/api/main.tf`
- `web/src/api/client.js`
- `web/src/components/ClientPortal.jsx`
- `web/src/components/IntakeForm.jsx`

## Deployment Evidence
- **CloudFront Distribution**: `E35L00QPA2IRCY`
- **Invalidation ID**: `IF4OOLWC7IWF7IWV76E6L6WMT2`
- **Status**: Completed

## Validations Performed
- Validated new API routes in Terraform.
- Validated fallback mappings for new request submissions auto-linking user tokens to pre-existing DynamoDB profiles.
- Validated redaction maps applied natively over `GET /client/*` requests stripping staff/admin metadata payloads.

## Known Limitations & Phase 5D Follow-Up
- Currently, pets must be mapped back to their clients statically. Phase 5D should expand self-service management for individual pet medical/logistics data via the Portal.
- Clients can cancel bookings in certain states but cannot modify existing ones. Phase 5D could expose an 'Edit Booking' capability.

## Production Verification
- **Tests Performed:**
  - Automated simulation verifying `GET /client/requests`, `POST /client/requests`, `GET /client/pets`.
  - Admin endpoint isolation assertions (`GET /admin/staff`, `GET /admin/requests`).
- **Pass/Fail Results:**
  - Client Isolation: PASS (Client endpoints isolate successfully).
  - Cross-Role Rejection: PASS (Clients accessing admin paths return 403 Forbidden).
  - Repeat Client Pre-population: PASS.
- **Defects Found:** None.
- **CloudFront Invalidation Status:** Completed (`IF4OOLWC7IWF7IWV76E6L6WMT2`).
- **Terraform Drift:** None.

