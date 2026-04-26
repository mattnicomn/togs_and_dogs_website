# Release Note: Admin Lifecycle Action Visibility Fix

- **Date**: 2026-04-26
- **Release Name**: Admin Lifecycle Action Visibility Fix
- **Production URL**: [https://toganddogs.usmissionhero.com/admin](https://toganddogs.usmissionhero.com/admin)
- **Deployed Commit**: `e8c770f`
- **S3 Bucket**: `togs-and-dogs-prod-toganddogs-hosting`
- **CloudFront Distribution**: `E35L00QPA2IRCY`
- **Invalidation ID**: `I44G1RZR6RRFCEX7YJIU1SWH0Q`

## Summary of Issue Fixed
- **Problem**: Cancelled active records were incorrectly showing "Restore" along with "Archive" and "Delete" buttons, leading to UI confusion and potential workflow errors.
- **Solution**: The UI now strictly separates workflow status from lifecycle state. Action visibility is now conditional based on whether a record is active, archived, or deleted.

## Validation Summary
- **Cancelled Active Records**: Verified they do not show the "Restore" action. Only "Archive" and "Move to Trash" are visible.
- **Archived Records**: Verified they show "Restore to Active" and "Move to Trash", but not "Archive".
- **Trash / Deleted Records**: Verified they show "Restore to Active" and do not show "Archive".
- **All Active Filter**: Verified that archived/deleted records are excluded, while cancelled active records are correctly included.
- **Regression Check**: Scheduler tab and bulk actions remain stable and functional.

## Files Changed
- `web/src/components/AdminDashboard.jsx`
- `web/src/Admin.css`
