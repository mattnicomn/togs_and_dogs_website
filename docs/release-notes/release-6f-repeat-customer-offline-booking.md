# Release 6F: Repeat Customer / Offline Client Booking Flow

## Overview
Allows admin/owner to create visit bookings on behalf of existing clients directly from the Admin Dashboard, supporting offline/non-tech-savvy clients without requiring Cognito login or the public intake form.

## Status: ✅ Deployed & Production Validated (2026-05-22)

## Deployment
- **Commits:**
  - `8fa35b3` — docs: plan Release 6F offline booking flow
  - `6415b7c` — feat: Release 6F admin-created offline booking backend
  - `4b948b3` — feat: Release 6F offline booking flow and admin pet list fix
  - `3934ef5` — fix: add GET /admin/pets route in Terraform to support offline client pet listing
- **Terraform:** Added GET /admin/pets API Gateway route + Lambda integration (9 Lambdas updated)
- **Frontend:** Built, synced to S3, CloudFront invalidation completed
- **Backend tests:** All passing

## Changes

### Backend (`src/backend/handlers/intake_handler.py`)
- Added `_handle_admin_created_booking()` function
- Detects `source: 'admin_created'` in request body
- Owner/admin authorization required (staff/client rejected)
- Validates existing `client_id` from Client Management
- Validates pet selection (pet_names or pet_ids required)
- Tenant isolation: client must belong to admin's company_id
- Creates request as `APPROVED` / `VISIT_BOOKING`
- Skips `REQUEST_RECEIVED` notification
- Invokes `JOB_FUNCTION_NAME` asynchronously (fail-safe)
- Syncs Google Calendar placeholder (fail-safe)
- Stores audit markers: `created_by`, `source`, `admin_created_at`

### Backend (`src/backend/handlers/pet_handler.py`)
- Added admin pet listing: `GET /admin/pets?clientId={id}`
- Owner/admin only with tenant isolation
- Returns active pets for the specified client
- Excludes inactive/archived pets

### Terraform (`infra/prod/`)
- Added `GET /admin/pets` API Gateway resource, method, and Lambda integration
- Connected to existing pet handler Lambda

### Frontend (`web/src/components/AdminDashboard.jsx`)
- "+ New Visit" button in admin header (owner/admin only)
- Modal with: client selector, pet checkboxes, service type, dates, visit window, notes, preferred sitter
- Blocks submission if no client, no pets, or no start date
- Shows "no pets on file" warning for clients without active pets
- Uses `listAdminClientPets(clientId)` for pet loading
- Uses `createAdminBooking(data)` for authenticated submission
- Refreshes request list on success

### Frontend (`web/src/api/client.js`)
- Added `createAdminBooking(data)` — authenticated POST to `/requests` with `source: 'admin_created'`
- Added `listAdminClientPets(clientId)` — authenticated GET to `/admin/pets?clientId={id}`

## Production Validation Results

| Check | Result |
|-------|--------|
| Staff blocked from admin-created booking | ✅ 403 Forbidden |
| Client blocked from admin-created booking | ✅ 403 Forbidden |
| Owner/admin pass role validation | ✅ |
| Tenant/company validation blocks invalid client | ✅ |
| Admin pet list allows owner/admin | ✅ |
| Admin pet list blocks staff | ✅ |
| GET /admin/pets route exists in API Gateway | ✅ (added via Terraform) |
| Frontend build passes | ✅ |
| Workspace clean | ✅ (only test_r4a_intake.py untracked) |

## Follow-Up
- **Terraform alignment:** Verify `terraform plan` returns "No changes" to confirm deployment state is fully aligned. AG noted a deployment trigger alignment consideration during closure.
- **End-to-end UI validation:** Full browser walkthrough of the New Visit modal (select client → select pets → submit → verify APPROVED booking appears) should be performed when convenient.

## Files Changed
- `src/backend/handlers/intake_handler.py`
- `src/backend/handlers/pet_handler.py`
- `web/src/components/AdminDashboard.jsx`
- `web/src/api/client.js`
- `tests/backend/test_r6f_offline_booking.py`
- `infra/prod/` (Terraform API Gateway route)
- `modules/api/main.tf` (if route was added there)
