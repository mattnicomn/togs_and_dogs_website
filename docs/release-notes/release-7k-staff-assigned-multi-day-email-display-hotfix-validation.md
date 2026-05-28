# Release 7K: STAFF_ASSIGNED Multi-Day Email Display Hotfix - Validation Closeout

**Date:** May 28, 2026  
**Release Phase:** 7K  
**Status:** PASSED  
**Commit Hash:** `d0cb877`  
**Deployment Target:** Production Backend (AWS Lambda via Terraform)  

## Scope
- Resolution of the notification context mismatch where child `JOB` records triggered `STAFF_ASSIGNED` and `VISIT_SCHEDULED` emails with single-day formatting.
- Implemented an in-memory parent request context resolver inside `src/backend/common/notifications/service.py`:
  - When the notification record is a child `JOB`, it queries the parent request `REQ` record from DynamoDB.
  * In-memory merges the parent request's overall scheduling fields: `selected_dates`, `end_date`, `start_date`, and `job_ids`.
  * Protects the invocation using a fail-open structure so parent lookup failures log warnings but never block event dispatches.

---

## Behavior Validated (Controlled Production Test)

A controlled test run was executed on production using the new multi-day request `7bd7a028-c16a-488e-9280-92a05426aca1` (Status: ASSIGNED, client: Justbeingbrea, pets: Joey Rockwell).

### 1. In-Memory Context Merging
- The assignment transaction triggered notifications with the child JOB record `JOB#fa4b6af8-190e-4b10-9c11-0008454be544` (which lacks scheduling dates in the database).
- The context resolver successfully loaded parent request `REQ#7bd7a028-c16a-488e-9280-92a05426aca1` in-memory.
- Copied `selected_dates` (`['2026-06-09', '2026-06-11', '2026-06-13']`) and parent date boundaries into the template context.
- Verified the templates rendered the full multi-day date format correctly: **Jun 9, Jun 11, Jun 13, 2026**.

### 2. Postmark Delivery Success
- The DynamoDB notification ledger verified that both notifications were successfully routed and sent with zero errors:
  - **`STAFF_ASSIGNED`:** Message ID `64cf2f03-2070-4c56-bcdf-ff239779e982` (delivered to worker `mattnicomn10@gmail.com` at `18:25:12 UTC`).
  - **`VISIT_SCHEDULED`:** Message ID `c373542d-e9fd-443d-8664-46464cdfd241` (delivered to client `brearockwell@gmail.com` at `18:25:12 UTC`).

### 3. Duplicate Prevention & Errors
- CloudWatch logs for `togs-and-dogs-prod-assign` stream `2026/05/28/[$LATEST]a3653273e7b34075a03ff57eda6bd10c` verify that both notifications were triggered **exactly once** for the transaction.
- Checked the logs and DynamoDB indexes; confirmed zero `failed` notifications, unhandled exceptions, or database lookup errors during the transaction.

---

## Guardrails Checked & Confirmed
- Direct request notifications (like approvals/cancellations) are completely unaffected.
- Lookups are fail-open, ensuring backend safety.
- Verified that all temporary query and verification scripts were removed.

Release 7K is **ACCEPTED** and **CLOSED**.
