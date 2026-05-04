# Staff Profile Sync and Account Security Controls

## Summary
Resolved the staff profile synchronization issue where profile edits were not persisting across Cognito sessions. Introduced new administrative account security controls for staff management.

## Key Changes
- **Source of Truth Hardening**:
    - DynamoDB is now explicitly the authoritative source for staff `display_name`, `phone`, and operational fields.
    - Fixed a bug where form data was discarded during Cognito user linking; form values are now correctly preserved and merged into the DynamoDB profile.
- **Cognito Attribute Sync**:
    - Added best-effort synchronization of `display_name` to Cognito's `name` attribute.
    - Added best-effort synchronization of `phone` to Cognito's `phone_number` attribute (requires E.164 format).
    - Failed Cognito syncs no longer block profile saves and instead return a non-blocking warning to the UI.
- **Account Security Module**:
    - Added "Reset Password" action to trigger a recovery email for staff members.
    - Added "Set Temporary Password" action allowing admins to set a one-time password that requires a change on the user's next login.
    - UI enhancements to staff cards to expose security actions for linked Cognito users.

## Files Modified
- `src/backend/handlers/admin_handler.py`: Updated linking logic, added Cognito sync, and added security routes.
- `web/src/api/client.js`: Added API wrappers for new security actions.
- `web/src/components/AdminDashboard.jsx`: Updated staff card UI and save notification logic.

## Validation Results
- Backend logic updated to prioritize DynamoDB.
- Cognito sync failure handling verified via warning propagation.
- Password management routes implemented and integrated.
