# Release Notes: User Access Lifecycle Management (Phase 5B)

## Issue
Ryan needed the ability to manage staff and client Cognito portal access directly from the Admin Dashboard, removing operational dependencies on manual Cognito administration.

## Scope
- Admin Portal actions for User Access Lifecycle Management.
- Granular administrative modifications (Disable, Enable, Unlink, Delete).

## Backend Changes
- Updated `src/backend/handlers/admin_handler.py` to support `action` parameters across standard `PATCH` routes.
- Provided automatic safeguards for localized consistency.

## Frontend Changes
- Modified `web/src/components/AdminDashboard.jsx` to map custom lifecycle modifications securely.

## IAM Changes
- Extended Cognito resources with `AdminDeleteUser` and `AdminListGroupsForUser`.

## Safety Controls
- Destructive actions require explicit confirmation blocks.
