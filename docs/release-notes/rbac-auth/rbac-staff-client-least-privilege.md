# Release Note: Staff and Client RBAC Least-Privilege Enforcement

## Issue
Users in the `Staff` and `Client` Cognito groups had excessive visibility and access to the Admin Dashboard. Specifically, Staff users could view the full Request List and potentially access Staff/Client Management tabs, while Client users could access the `/admin` login page and internal dashboard if they bypassed the intended portal routes. This violated the principle of least privilege and posed a risk of unauthorized data exposure.

## Correction
We have implemented strict Role-Based Access Control (RBAC) across both the frontend and backend to enforce the correct permission boundaries.

### Frontend Improvements
- **Capability Model**: Introduced a capability-based permission model in the `AdminDashboard` to manage access flags (`canViewRequestList`, `canManageStaff`, etc.) based on the user's role.
- **Tab Visibility**: Restricted visibility of the "Request List", "Staff Management", and "Client Management" tabs to `owner` and `admin` roles only.
- **Route Protection**:
    - **Clients**: Automatically redirected from the `/admin` route to the client portal (`/my-bookings`).
    - **Staff**: Forced to the "Scheduler" view if they attempt to navigate to or remain on a restricted view (e.g., via state persistence or manual manipulation).
- **Navigation**: Cleaned up the header navigation to only render buttons for authorized views.

### Backend Authorization
- **API Hardening**: Updated `admin_handler.py` to enforce role checks on restricted endpoints:
    - `GET /admin/staff`: Restricted to `owner` and `admin`.
    - `GET /admin/clients`: Restricted to `owner` and `admin`.
    - `GET /admin/requests` (specific status queries): Restricted to `owner` and `admin`.
- **Data Isolation**: Staff users continue to be restricted to viewing only their assigned jobs in the "Scheduler" (ALL) view.
- **Error Handling**: Forbidden access attempts now return a clear `403 Forbidden` response.

## RBAC Behavior Summary

| View / Action | Owner / Admin | Staff | Client |
| :--- | :---: | :---: | :---: |
| **Scheduler** | Full Access | Assigned Only | No Access |
| **Request List** | Full Access | Hidden / 403 | No Access |
| **Staff Management** | Full Access | Hidden / 403 | No Access |
| **Client Management** | Full Access | Hidden / 403 | No Access |
| **Portal / My Bookings** | Full Access | Full Access | Full Access |
| **Admin APIs** | Authorized | Restricted | Denied |

## Scope
- **Frontend**: Admin Dashboard route and tab logic.
- **Backend**: Authorization checks in the `admin` Lambda handler.
- **Auth**: Cognito group normalization and parsing logic.

## Deployment Details
- **Build**: `npm run build` verified.
- **S3 Sync**: Deployment of `web/dist` to S3.
- **CloudFront Invalidation**: Created for distribution `E35L00QPA2IRCY`.
- **Lambda Update**: Authorization logic updated in `admin` handler.

## Verification
- Verified Admin access to all tabs.
- Verified Staff restriction to Scheduler-only view.
- Verified Client redirection from `/admin` to `/my-bookings`.
- Verified 403 responses for unauthorized API calls.
