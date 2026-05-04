# Admin Bulk Workflow Actions Release

**Release Date:** April 25, 2026  
**Commit:** e728e63  
**Production URL:** https://toganddogs.usmissionhero.com/admin  
**CloudFront Invalidation:** IE09OBGMOWXSSD3N850WNYZKRW

## Summary

Added safe bulk workflow actions to the Togs & Dogs admin visits list. Admin users can now select visible visit records and move them through supported workflow phases in bulk.

## Features Added

- Row-level multi-select checkboxes
- Select visible checkbox for filtered records
- Bulk workflow action toolbar
- Bulk status/phase dropdown
- Confirmation modal before applying updates
- Partial success/failure handling
- Responsive styling for desktop and mobile use

## Supported Bulk Status Options

- Requested / Intake
- New Request
- Approved
- Scheduled
- In Progress
- Completed
- Cancelled
- Archived

## Safety Controls

- No bulk hard-delete functionality added
- `Deleted` is not exposed as a bulk option
- Archive uses existing soft-delete/archive behavior
- Bulk updates apply only to selected visible records
- Existing individual row actions remain unchanged

## Validation

- Frontend build completed successfully
- Production admin visits list loads correctly
- Row checkboxes and select-visible behavior validated
- Bulk toolbar and confirmation modal validated
- Bulk status transition validated
- Bulk archive confirmation validated
- Individual actions and archive filters validated
- Mobile/responsive layout validated

## Files Changed

- `web/src/components/AdminDashboard.jsx`
- `web/src/Admin.css`

## Infrastructure Impact

No authentication, backend infrastructure, Terraform, Cognito, or CloudFront configuration changes were made.
