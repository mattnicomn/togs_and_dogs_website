# Tasks

## Backend Implementation
- [x] Refactor `admin_handler.py` to generalize account security routes
- [x] Implement `POST /admin/clients/onboard`
- [x] Implement client-specific security routes (`resend-invite`, `reset-password`, `set-temp-password`, `link-cognito`)
- [x] Update `PATCH /admin/clients/{id}` to support lifecycle actions
- [x] Harden `PATCH /admin/staff/{id}` guardrails (role downgrade prevention)

## Frontend Implementation
- [x] Update `web/src/api/client.js` with new client access management calls
- [x] Update `web/src/components/AdminDashboard.jsx` access status logic
- [x] Update Client Management UI in `AdminDashboard.jsx` (Form & Cards)
- [x] Align Staff Management UI in `AdminDashboard.jsx` (Labels & Indicators)
- [x] Refactor event handlers in `AdminDashboard.jsx`

## Verification & Documentation
- [x] Run `npm run build`
- [x] Update release notes
- [x] Final git commit & push
- [x] Production Deployment (Terraform & S3 Sync)
- [x] CloudFront Invalidation
- [x] Production Smoke Test
