# Release Notes: Authenticated User Profile Dropdown

**Date**: 2026-05-01
**Environment**: Production (`usmissionhero-website-prod`)
**Commit**: `c6aebae`
**CloudFront Invalidation**: `IEOOEW0H8CC268YNAVY1ETFKJX`

## Feature Overview
Added a top-right authenticated user profile dropdown to the Tog and Dogs portal to provide users with visibility into their active session, role, and company context.

### Changes Included
- **New Component**: `UserProfile.jsx` handles the display of user details and the dropdown menu.
- **Trigger Display**: 
    - Shows user display name (if available) or email address.
    - On small screens, collapses to a compact avatar icon.
- **Dropdown Content**:
    - **User Info**: Full name and email address.
    - **Role Badge**: Visual indicator of the user's role (Admin, Owner, Staff, or Client).
    - **Company Branding**: "Tog and Dogs" confirmed as the active context.
    - **Sign Out**: Actionable link to the existing logout flow.
- **Accessibility**:
    - Accessible labels and ARIA attributes.
    - Closes automatically when clicking outside the dropdown.
    - Keyboard-friendly trigger.

### Scope & Constraints
- **Authenticated Views Only**: The dropdown appears only in the `AdminDashboard` and `ClientPortal` when a valid session exists.
- **Non-Scope**: Full profile editing is not included in this update.

## Test Results
- **Frontend Build**: `npm run build` - SUCCESS.
- **Unauthenticated State**: Verified that public pages (`/`, `/book`) do not display the profile dropdown.
- **Authenticated State**: Verified that `AdminDashboard` and `ClientPortal` correctly display user info and role badges.
- **Sign Out**: Confirmed that the "Sign out" action correctly clears the session and redirects/reloads as expected.

## Deployment Details
- **Repository**: Pushed to `origin/main`.
- **Hosting**: Synced build assets to `togs-and-dogs-prod-toganddogs-hosting` S3 bucket.
- **CDN**: Triggered full invalidation on CloudFront distribution `E35L00QPA2IRCY`.

---
*For questions regarding this deployment, contact the dev team or refer to the DECISIONS_LOG.md.*
