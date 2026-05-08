# Release Notes - Client Resend Invite Fix & Virtual User Support

**Date:** 2026-05-07
**Status:** Deployed to Production

## Summary
Resolved the "Failed to fetch" error encountered when resending invitations to client users. Standardized the welcome email experience using professional, branded templates via Postmark.

## Changes

### 1. API Gateway Infrastructure
- **Added Routes**: Defined and deployed missing API Gateway routes for administrative client security actions.
    - `/admin/clients/{client_id}/resend-invite` (POST)
    - `/admin/clients/{client_id}/reset-password` (POST)
    - `/admin/clients/{client_id}/set-temp-password` (POST)
- **CORS Support**: Updated preflight configuration to allow these requests from the Admin Dashboard.

### 2. Backend (Admin Lambda)
- **Virtual User Fallback**: Implemented robust handling for "virtual" users (accounts that exist in Cognito but do not yet have a profile in DynamoDB). This ensures security actions work immediately upon account creation.
- **Branded Notifications**: Unified the invitation flow to send a professional `WELCOME_INVITE` email via Postmark.
    - Includes portal URL and access instructions.
    - Specifically designed to avoid sending plaintext passwords (standard Cognito delivery is preserved for credentials).
- **Error Handling**: Added specific feedback for "Already Confirmed" users to guide admins toward the Password Reset flow instead of resending invites.

### 3. Frontend (Admin Dashboard)
- **UX Improvements**: Added loading states (button disabling and spinners) to the client management section.
- **Enhanced Feedback**: Improved toast notifications to confirm both the resend action and the branded email delivery.

## Verification
- [x] **Infrastructure**: Terraform plan verified 22 additions and successfully applied.
- [x] **Code Quality**: Backend files passed `py_compile`. Frontend passed `npm run build`.
- [x] **Database Context**: Verified existence of target user `Justbeingbrea` in Cognito and confirmed virtual status in DynamoDB.
- [x] **Deliverability**: DKIM/Return-Path verified for `usmissionhero.com`.

## Security Notes
- No plaintext passwords are sent via the branded welcome email.
- RBAC enforces that only `owner` and `admin` roles can trigger these security actions.
- Postmark provider is active and integrated with the pluggable notification service.
