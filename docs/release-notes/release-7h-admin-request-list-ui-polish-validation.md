# Release 7H: Admin Request List Multi-Day Date Display Polish - Validation Closeout

**Release:** 7H  
**Commit Hash:** `ea7234d`  
**Deployment Target:** Production Frontend (S3 / CloudFront)  
**CloudFront Invalidation ID:** `I92UD2C8YA3A5LG8IZRL355DLJ`  

## Scope
- Frontend-only change applied to `web/src/components/AdminDashboard.jsx`.
- Replaced raw ISO date rendering in the Request List table with a dedicated `formatVisitDates` helper function.

## Behavior Validated
- Admin Request List now correctly displays multi-day visits in human-readable formats:
  - **Consecutive Dates:** Rendered as a compact range (e.g., “Jun 9–13, 2026”).
  - **Non-Consecutive Dates:** Rendered as a compact comma-separated list (e.g., “Jun 9, Jun 11, Jun 13, 2026”).
  - **Long Non-Consecutive Selections:** Truncated nicely with a “+N more” badge (e.g., “Jun 9, Jun 11, Jun 13 +2 more”).
  - **Backwards Compatibility:** Legacy records with only `start_date` and `end_date` fall back to the friendly range formatter securely.

## Guardrails Confirmed
- **NO** changes made to backend lambda handlers, notification templates, or API clients.
- **NO** changes made to Terraform infrastructure configurations.
- **NO** changes made to production data or database payloads.
- **NO** modifications to existing untracked scratch/log files. 
