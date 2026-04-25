# Togs & Dogs Brand Alignment Release

**Release Date**: April 25, 2026
**Production URL**: [https://toganddogs.usmissionhero.com/](https://toganddogs.usmissionhero.com/)
**Final Main Commit**: `189ab0f6b37087ebf39fc83e0a43e9a57d2d2b9e`

## Purpose
The objective of this release was to align the US Mission Hero-operated operations portal with the public Togs & Dogs marketing brand ([toganddogs.com](https://toganddogs.com/)). This ensures a cohesive user experience for clients transitioning from the public site to the scheduling and intake platform.

## Scope
This was a **frontend-only** theme and style update. No infrastructure, backend logic, or data models were modified.

## Files Changed
- `web/src/index.css`
- `web/src/Admin.css`
- `web/src/Portal.css`
- `web/src/App.css`
- `web/src/components/Home.jsx`
- `web/src/components/PortalGateway.css`

## Validation Completed
- [x] **Build Verification**: `npm run build` passed with optimized production assets.
- [x] **Lint Verification**: `npm run lint` passed for all modified components.
- [x] **Route Verification**: Production routes for `/`, `/book`, and `/admin` verified live.
- [x] **Console Audit**: Browser console verified clean in the production environment.
- [x] **Responsive Check**: Layouts validated across Mobile, Tablet, and Desktop breakpoints.
- [x] **Privacy Hardening**: Removed external Google Fonts dependency; replaced with local system font stacks (Georgia/Segoe UI).
- [x] **Safety Check**: Confirmed no changes to Terraform, Lambda handlers, Cognito, Route 53, or CloudFront configurations.

## Deployment Details
- **Deployment Bucket**: `togs-and-dogs-prod-toganddogs-hosting`
- **CloudFront Invalidation ID**: `I7ACA9Y9R7QJE1P09CMKMDNEFQ`

## Follow-up Recommendations
- **Asset Alignment**: Consider updating favicon and logo assets to match the exact SVG/PNG variants used on the public site.
- **Email Branding**: Align automated SES email templates with the new portal color scheme (Cream/Gold).
- **Client Signoff**: Request final visual approval from Ryan to ensure the brand tone meets business expectations.
