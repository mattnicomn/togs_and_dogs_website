# Release Notes: Client Portal Booking Visibility

Objective: Enhance the client-facing portal to provide transparent, status-driven booking visibility while ensuring strict RBAC security.

## Summary of Changes

### 1. Enhanced Lifecycle Visibility
Implemented clear, user-friendly status labels in the `ClientPortal` to replace internal technical status codes.
- **Pending Review**: Your request is being reviewed.
- **Meet & Greet Required**: Ryan will follow up to schedule a meet & greet.
- **Quote Needed**: A quote is being prepared for your review.
- **Approved**: Your request has been approved. Ryan will follow up to confirm final scheduling details.
- **Scheduled**: Your visit is scheduled.
- **Completed**: This visit has been completed.
- **Cancelled**: This request has been cancelled.
- **Cancellation Pending**: Your cancellation request is being reviewed.

### 2. Detailed Booking Information
For all requests, clients can now see:
- **Service Date**: Clearly displayed in a dedicated date box.
- **Service Type**: e.g., Dog Walking, Pet Sitting.
- **Pet Names**: Visible on each booking card.
- **Time Windows**: Preferred visit windows or specific times are displayed.
- **Assigned Staff**: When a visit is **Scheduled**, the assigned staff's display name is visible (e.g., "👤 Ryan").

### 3. Messaging & Feedback
Added specific messaging for each state to guide the client on what to expect next (e.g., "Ryan will follow up to confirm final scheduling details").

### 4. Security & RBAC Guardrails
- **Redaction**: Strictly enforced backend redaction ensures that internal staff IDs, emails, pricing notes, and admin-only fields remain hidden from the client portal.
- **Access Control**: Confirmed that client users are restricted from the `/admin` path and can only view their own request records.
- **Data Shaping**: The backend `sanitize_booking_for_role` helper was updated to selectively expose `worker_name` while keeping `worker_id` and other sensitive fields private.

## Verification
- **Backend Compilation**: Passed for all relevant handlers and common modules.
- **Frontend Build**: Successfully generated production bundle via `vite build`.
- **RBAC Validation**: Verified that client roles are redirected from `/admin` and only see their own records via scoped API scans.

## Technical Details
- **Backend Persistence**: `worker_name` is now persisted during the assignment workflow to ensure it is available for client-side display without requiring additional lookups.
- **Commit Reference**: 72ed22a
