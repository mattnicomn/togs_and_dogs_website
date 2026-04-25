# Release Note: Admin Workflow Remediation

**Deployment Date/Time**: 2026-04-25 17:05:49 EDT  
**Status**: Production Live  
**URL**: [https://toganddogs.usmissionhero.com/admin](https://toganddogs.usmissionhero.com/admin)  
**Branch**: `fix/admin-workflow-remediation` (Merged into `main`)

## 1. Infrastructure Summary
- **Frontend S3 Bucket**: `togs-and-dogs-prod-toganddogs-hosting`
- **CloudFront Distribution ID**: `E35L00QPA2IRCY`
- **API Endpoint**: `https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod`
- **Backend Deployment**: Automated Terraform packaging (`backend.zip`) updating 8 Lambda handlers:
  - `intake`, `admin`, `review`, `assign`, `job`, `google-auth`, `pet`, `cancellation`.

## 2. Feature & Fix Summary

### Workflow & Lifecycle
- **Status Normalization**: Standardized all status codes (`PENDING_REVIEW` to `DELETED`) and UI labels across the platform.
- **Intake Automation**: Automated the `PROFILE_CREATED` transition when a pet profile is first saved for an intake request.
- **Manual M&G Verification**: Added a manual "Verify M&G" bypass to the workflow, allowing admins to unblock approvals without requiring client-side interaction.
- **Care Card Management**: Integrated direct lifecycle status management into the Care Card, allowing admins to override status and add audit notes.

### Scheduler Repair
- **Date-Based Filtering**: Fixed the Master Scheduler to use the actual `start_date` for visits. Day View and Week View now show the correct appointments for the selected timeframe.
- **Quick Filters**: Fully functional sidebar filters for Staff, Status, and Intake stages.
- **Queue Visibility**: `PROFILE_CREATED` and `READY_FOR_APPROVAL` records are now prioritized in the scheduler sidebar for assignment.

### Record Persistence & Security
- **Soft Delete/Archive**: Implemented `DELETED` and `ARCHIVED` behaviors. "Delete" now marks records as deleted rather than purging them, ensuring audit logs remain intact.
- **Restoration**: Enabled restoration logic from terminal states (Cancelled/Archived/Deleted) back to active intake status.
- **Clean Production Build**: Removed all debug console logs and ensured local development proxies do not affect the production runtime.

## 3. Smoke Test Results
| Test Case | Result | Notes |
| :--- | :--- | :--- |
| Admin Dashboard Load | PASS | Zero latency/load issues. |
| Scheduler Date Toggle | PASS | Day/Week views accurately reflect scheduled data. |
| Quick Filters | PASS | Filters isolate visits as expected. |
| Status Transition (Intake -> Scheduled) | PASS | Full lifecycle path verified. |
| CloudFront Cache Invalidation | PASS | "/*" path invalidated; latest build is active. |

## 4. Remaining Limitations & Next Steps
- **M&G Automation**: Currently requires manual verification via the "Verify M&G" button if the client has not completed the automated flow.
- **Recommended Next Validation**: Walk through the "New Request -> Approve -> Assign Staff" flow with Ryan to confirm the business-level user experience is fully aligned with operational needs.
