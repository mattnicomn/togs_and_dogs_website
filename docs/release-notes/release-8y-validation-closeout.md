# Release 8Y: Mobile Per-Visit / Per-Day Completion Workflow Closeout

## 1. Release Purpose
Implementation of the Per-Visit / Per-Day Completion Workflow for multi-day bookings. This allows staff sitters to complete individual daily visits (child `JOB#` records) and write notes specific to that date (capped at 500 characters). The parent booking (`REQ#`) remains in `ASSIGNED` state until the final child job is completed, at which point the parent request automatically rolls up to `COMPLETED`.

## 2. Key Commits
* **Planning**: `e5c69d2 docs: plan release 8y mobile per visit completion`
* **Main Implementation**: `416209a feat(mobile): support per-visit completion workflow`
* **Stabilization**: `14de35b fix(admin): cascade primary job assignment for multi-day bookings`

## 3. Files Changed Across Release
* **Backend**:
  * [admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py)
  * [assignment_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/assignment_handler.py)
  * [test_r8y_per_visit_completion.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r8y_per_visit_completion.py)
  * [test_r7g_assignment_multiday.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r7g_assignment_multiday.py)
* **Terraform**:
  * [main.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/modules/api/main.tf)
* **Mobile**:
  * [index.ts](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/types/index.ts)
  * [client.ts](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/api/client.ts)
  * [ScheduleScreen.tsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/screens/ScheduleScreen.tsx)
  * [RequestDetailScreen.tsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/screens/RequestDetailScreen.tsx)

## 4. Backend Behavior
* **New Endpoint**: `POST /admin/job/complete`.
* **Staff Ownership Enforcement**: Sitters can only complete child jobs assigned to them.
* **Per-visit updates**: Completes specific child `JOB#` records in DynamoDB, setting `status = COMPLETED`, updating `completed_at` / `completed_by`, and adding visit notes.
* **Character limits**: Rejects notes exceeding 500 characters with a 400 Bad Request.
* **Idempotency**: Requests to complete already-completed jobs return successfully with an appropriate response, without altering timestamps.
* **Auto-rollup**: Sibling jobs are checked on completion. The parent request is automatically rolled up to `COMPLETED` only when all child jobs are marked complete.

## 5. Mobile Behavior
* **Date Mapping**: Staff schedule screen maps selected schedule dates to correct child `job_id` values based on their parallel index sequence.
* **Visit Details**: Detail screen displays the active date using a "Target Visit Date" banner.
* **Completion Details**: Marking complete targets only the selected date. The completed date immediately disappears from the Upcoming view, while remaining incomplete dates stay visible.
* **Parent Persistence**: The parent request remains active and listed in the upcoming schedule until all dates have been individually completed.

## 6. Terraform & API Gateway Deployment
* **API Resources**: Added `/admin/job` and `/admin/job/complete` resources to AWS API Gateway.
* **Method Integration**: Configured POST method with Cognito authorization.
* **CORS Support**: Added mock integration for OPTIONS request to support CORS.
* **Deployments**: API Gateway stage updated and Lambda packages deployed to AWS.

## 7. Assignment Cascade Stabilization
* **Root Cause**: The Admin web dashboard assigns by primary job ID. The handler originally expected a parent request ID for cascading, causing assignments to only assign the first child job while leaving other dates in `JOB_CREATED` and unassigned.
* **Fix**: The assignment handler now checks if a multi-day booking assignment request targets the primary child job. If so, it cascades the assignment to all child jobs.
* **Granularity**: Assigning an explicit non-primary child job ID directly remains granular to that specific job.

## 8. Validation Checklist & Results
* **Targeted unit tests**: Pass (5/5).
* **Full backend suite**: Pass (308/308).
* **Terraform validate**: Pass.
* **TypeScript compilation (`npx tsc --noEmit`)**: Pass.
* **Expo Doctor compatibility**: Pass (18/18 checks).
* **Production Validation (Jun 19–21 booking `REQ#cd211318-aa72-4bfc-829c-f450e6ffe6c2`)**:
  * Assignment cascade triggered successfully; all 3 child jobs assigned to `mattnicomn10@yahoo.com`.
  * iOS preview build `58efd764-f170-4d6e-801c-7a1a7e76a2af` installed and validated.
  * Jun 20 visit completed successfully from the preview build.
  * Jun 20 child job status updated to `COMPLETED` with `completed_by = mattnicomn10@yahoo.com` and visit notes (`"Jun 20 per-visit test"`).
  * Sibling jobs (Jun 19 and Jun 21) remain `ASSIGNED`.
  * Parent request remains `ASSIGNED`.

## 9. Guardrails & Compliance
* **No Postmark side effects**: The per-visit completion API does not trigger email notifications.
* **No Google Calendar side effects**: The per-visit completion does not call calendar sync.
* **No client-facing notifications**: No customer notifications are dispatched for partial completions.
* **Zero manual production modifications**: No manual DynamoDB data modification was performed (except API-driven reassignment and mobile completion validation).
* **No web frontend changes**: Web code remained untouched.

## 10. Deferred Items
* Web admin per-child completion display polish.
* Optional final-rollup manual validation if desired later.
* Cleanup/archiving of test bookings.
