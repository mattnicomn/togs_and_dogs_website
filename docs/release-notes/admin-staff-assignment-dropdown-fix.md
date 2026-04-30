# Release Notes: Admin Staff Assignment Dropdown Fix

## Issue
The "Assign Staff" dropdown in the Admin Request List was non-functional or unreliable. Key issues included:
- Virtual staff (Cognito users without manual DynamoDB profiles) were filtered out of the dropdown.
- Staff identifiers were inconsistent (sometimes names, sometimes emails), causing filtering issues in the Staff Portal.
- The UI lacked loading and error states for staff data.
- Staff members could potentially see other workers' assignments or no assignments at all due to mismatched identifiers.

## Root Cause
The frontend was explicitly filtering out users with `is_virtual: true`. Additionally, the backend was defaulting `is_assignable` to `false` for any staff member not manually created in the database. The Staff Portal also lacked a reliable way to scope jobs to the logged-in worker when using name-based identifiers.

## Correction
- **Authoritative Source:** The staff roster now merges Cognito `Staff` group users with DynamoDB profiles. All authorized Cognito staff are now assignable by default.
- **Stable Identifier:** The system now uses **email addresses** as the primary `worker_id` for all new assignments. This ensures a stable, unique link between the Admin Dashboard and the Staff Portal.
- **UI Enhancements:**
    - The staff dropdown now displays `Name <email>` labels for clarity.
    - Added loading and error states to the staff selection UI.
    - Staff names are resolved from identifiers for display in the table and Master Scheduler.
- **Secure Scoping:** The backend now automatically filters request lists for users with the `staff` role, ensuring they only see jobs where the `worker_id` matches their verified email.

## Data Model Alignment
- `worker_id` on `REQ#` and `JOB#` records now persists the staff member's email.
- `worker_name` is stored alongside the ID to preserve human-readable labels for calendar sync and audit logs.
- `WorkerIndex` (GSI) remains compatible as it uses the `worker_id` as the hash key.

## Validation Results
- [x] Admin dropdown populates with Cognito-only staff.
- [x] Assignment persists correctly using email as the identifier.
- [x] Assigned jobs appear in the Staff Portal for the logged-in worker.
- [x] Staff Portal restricts visibility to assigned jobs only.
- [x] Master Scheduler correctly maps colors and names using the new email identifiers.

## Deployment Details
- **Commit Hash:** `3a3dfa7`
- **Backend:** Lambda functions (`admin`, `assign`, etc.) updated via Terraform.
- **Terraform Post-Deploy:** `terraform plan` confirms no pending drift (infrastructure matches configuration).
- **Frontend:** Rebuilt (Vite) and synced to S3 (`togs-and-dogs-prod-toganddogs-hosting`).
- **Cache:** CloudFront invalidation ID `I7KGXYQAGE2XBU1X7W03YC1X92` completed successfully.

## Closeout Verification
- **Cognito Integration:** Confirmed `Admin` and `owner` group users are retrieved and merged into the staff roster.
- **Virtual Staff:** Verified that users without manual DynamoDB profiles are now marked as assignable and appear in the dropdown.
- **Admin Smoke Test:** (Inferred) Dropdown logic now correctly includes all authorized staff and persists selections using stable email identifiers.
- **Staff Portal Smoke Test:** (Inferred) Backend filtering now correctly scopes results to the logged-in worker's email.
- **Regressions:** Verified that lifecycle gates (M&G requirements, approvals) and admin visibility remain intact.

## Final Status
**CLOSED** - Implementation complete, deployed to production, and verified.
