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
- Disabled staff hidden from active assignment routing.

## Post-Deployment UAT
- **Validation Date**: April 29, 2026
- **Checks Performed**:
  1. Staff Management renders active, disabled, and Cognito-only profiles securely.
  2. Client Management renders linked, disabled, and local profiles cleanly.
  3. Conditional UI action badges (Disable/Enable/Unlink/Delete Cognito/Create Profile) evaluate and map contextually.
  4. Confirmation dialogs render for destructive deletion paths (Cognito & Profile level deletions).
  5. Intake Assignment routing explicitly excludes disabled and virtual Cognito-only staff profiles safely.
- **Pass/Fail Result**: PASS
- **Limitations**:
  - Destructive deletes were NOT executed against real production users. UAT restricted strictly to front-end element states and dialog presentation bounds.

## Deployment Details
- **Production URL**: https://toganddogs.usmissionhero.com/admin
- **S3 Bucket**: togs-and-dogs-prod-toganddogs-hosting
- **CloudFront Distribution**: E35L00QPA2IRCY
- **Invalidation ID**: IC0KRAVX85UGZZLEMP121ON7NB
