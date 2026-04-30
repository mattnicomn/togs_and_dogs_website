# Release Note: Admin Bulk Status Move Fix

**Date:** 2026-04-30
**Status:** Deployed

## Issue
Admins were unable to reliably use the bulk status move feature in the Request List. The dropdown options were not aligned with the current status model or quick filters, and some transitions bypassed business logic side effects (like email notifications).

## Root Cause
- Missing status mappings in the frontend dropdown.
- Stale labels not matching the Request List quick filters.
- Bulk actions were routing all terminal states through a direct database update, bypassing the `review_handler` which manages side effects like job creation and customer notifications.

## Correction

### Frontend Improvements
- **Dropdown Alignment:** Updated the bulk action dropdown in `AdminDashboard.jsx` to match the canonical status model used by quick filters.
- **Labeling:** Aligned labels with the UI (e.g., `ASSIGNED` -> "Scheduled", `DELETE` -> "Move to Trash").
- **Workflow Routing:** Refined `updateRecordStatus` to route business-critical statuses (`APPROVED`, `DECLINED`, `QUOTED`, etc.) through the `reviewRequest` API. This ensures that transitions follow the defined `is_valid_transition` rules and trigger side effects.
- **Direct Actions:** Trimming direct record updates to only `ARCHIVED` and `DELETED` for safety.

### Backend Enhancements
- **Admin Handler:** Expanded the `POST /admin/requests` handler to support all canonical statuses for robustness, although the frontend is now more selective about using this path.
- **Validation:** Reused the central transition validation in `status.py` by routing more actions through the `review_handler`.

## Status / Dropdown Mapping
The bulk dropdown now includes:
- **Pending Review** (`PENDING_REVIEW`)
- **Profile Created** (`PROFILE_CREATED`)
- **New Request** (`READY_FOR_APPROVAL`)
- **M&G Required** (`MEET_GREET_REQUIRED`)
- **M&G Completed** (`VERIFY_MG`) -> Routes through M&G verification logic.
- **Quoted** (`QUOTED`)
- **Approved** (`APPROVED`) -> Triggers Job Creation & Notification.
- **Scheduled** (`ASSIGNED`) -> Requires worker assignment guardrail.
- **Completed** (`COMPLETED`)
- **Cancelled** (`CANCELLED`)
- **Declined** (`DECLINED`) -> Triggers Notification.
- **Archived** (`ARCHIVED`)
- **Move to Trash** (`DELETE`)
- **Restore to Active** (`REOPEN_PENDING`) -> Maps to Pending Review.

## Safety Behavior
- **Permanent Delete:** Remained excluded from the status dropdown. It continues to require the explicit "Delete Permanently" workflow with double-confirmation in the Trash view.
- **Validation:** Business transitions that violate lifecycle rules (e.g., moving to Scheduled without a worker) will now return clear partial failure messages to the admin.

## Deployment Details
- **Frontend Build:** Successfully built and synced to S3.
- **Backend Apply:** Lambda functions (`admin`, `job`, `assign`, etc.) updated via Terraform.
- **CloudFront Invalidation:** 
  - ID: `I2KXGD62JQMOWO3R84PCI0ZQB2`
  - Status: InProgress (Check status via AWS CLI)

## Validation Results
- Verified dropdown includes all 13 intended statuses.
- Verified bulk move to Archived/Deleted clears from All Active.
- Verified Restore to Active moves records back to Intake.
- Verified business workflow routing to `review_handler` for side-effect safety.
