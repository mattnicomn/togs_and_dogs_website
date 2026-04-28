# Release Notes: Homepage Role Entry Separation

## Issue
The portal gateway homepage combined the client and admin workflows into a single ambiguous action label.

## Resolution
Expanded the structural entry options into three standalone selectors:
- **Request Pet Care** (`/book`)
- **My Bookings** (`/my-bookings`)
- **Staff Portal** (`/admin`)

## Verification Guidelines
- S3 Sync completed.
- CloudFront invalidated securely.

## Scope Bounds Confirmation
We confirm **zero infrastructural drift**:
- No authentication mapping schema adjustments.
- No database entities or API mutations.

Production Context: https://toganddogs.usmissionhero.com/
