# Release 9E Validation Closeout — Ryan Production Readiness Dry Run

## 1. Release Purpose
The purpose of Release 9E is to perform a controlled, end-to-end operational dry run of the entire pet care workflow on the live production environment. This dry run simulates the dashboard and booking lifecycle from the perspective of the Administrator (Ryan), the Sitter (Staff), and the Client to guarantee complete system readiness prior to structured user testing.

## 2. Reference Commits
* **Planning Commit**: `0e8e355 docs: plan release 9e ryan readiness dry run`

## 3. Execution Scope & Safety Guardrails
* **Scope**: Controlled operational validation only.
* **No Code Changes**: No application code modified.
* **No Deployments**: No new backend Lambdas or web client packages deployed.
* **No Terraform**: No infrastructure alterations.
* **No Mobile Builds**: Restrained to simulated PWA browser workflows; no EAS updates or mobile binary builds.
* **Data Hygiene**: Used clearly labeled test data only. Cleanup executed via approved admin archive controls (no DynamoDB manual purges or direct database edits).
* **Controlled Side Effects**: Google Calendar sync and Postmark emails triggered intentionally for dry-run verification only.

## 4. Roles and Test Accounts
* **Administrator**: `admin@toganddogs.com` (Ryan/Admin role)
* **Client / Test Intake Identity**: `brearockwell@gmail.com` (Client ID: `client_1697162f`, Pet: `Joey Rockwell`)
* **Staff / Sitter**: `mattnicomn10@yahoo.com` (Staff Test User)

## 5. Scenarios Executed
1. **Scenario A (Single-day)**: standard intake, Meet & Greet verification, approval, assignment, sitter completion with notes, admin dashboard check, and archiving.
2. **Scenario B (Multi-day)**: 3-day job creation, batch assignment, Day 1 completion, partial progress check (1/3 completed, parent request remains ASSIGNED), and archiving.
3. **Scenario C (Test Booking)**: intake submission, marking parent request as Test Booking, verifying database test flags, and archiving.
4. **Scenario D (Archive/Unarchive)**: 3-day job creation, assignment, Day 1 completion, archiving (active jobs archived, completed preserved, calendar events deleted), unarchiving (active restored to ASSIGNED, calendar events recreated), and final cleanup.
5. **Daily Dispatch Export**: fetched export payload from the Lambda API and verified Excel sheet formatting and filters while Scenarios A and B were active.

---

## 6. Created Records Log

| Scenario | Request ID (PK: REQ#...) | Job ID(s) (PK: JOB#...) | Notes |
| :--- | :--- | :--- | :--- |
| **Scenario A** | `d1203b59-9e32-4a49-b4d5-96feee48200a` | `b754e667-1f6d-4494-b16f-c27aec5127bf` | 1 child job; fully completed. |
| **Scenario B** | `fe93195f-2a88-4b71-8e42-572008472a21` | `2303c990-30c3-4a99-a37b-0233847afc78`<br>`d0e4846b-7ef3-4156-878d-a12cbb548349`<br>`2dd07ee0-d53a-4c8d-9251-761eb82fc5ee` | 3 child jobs; Job 1 completed, Jobs 2/3 active. |
| **Scenario C** | `f622134b-85f8-4e99-966b-e784275073ba` | *None* | Marked test and archived before approval as designed. |
| **Scenario D** | `f8ce7f6b-948a-4d80-8d91-292b84351ca8` | `da821a2f-7501-4ee7-9bb7-956b912bf428`<br>`c61424d0-0d69-4f2e-8f67-4cbf29295d93`<br>`d78d84bf-dc60-4c61-af96-ce6c89c3f24f` | 3 child jobs; Job 1 completed, Jobs 2/3 restored. |

---

## 7. Validation Results

### 7.1. Workflow Verification (Pass/Fail: PASS)
* **Intake & Terms**: Public intake request creation and Terms/Privacy acceptance logic passed.
* **Meet & Greet Verification**: Transition to `MG_COMPLETED` using the `/admin/review` endpoint and `VERIFY_MEET_GREET` pseudo-status succeeded.
* **Approval & Child Jobs**: Transition from `MG_COMPLETED` to `APPROVED` succeeded, triggering async child job creation.
* **Staff Assignment**: Sitter assignment and cascade of status to child jobs updated status to `ASSIGNED` correctly.
* **Staff schedule visibility**: Sitter logged in and viewed assigned visits.
* **Per-visit completion**: Sitter submitted visit notes and marked visits `COMPLETED`.
* **Admin Dashboard visibility**: Admin verified completed visit counts (`1/1` for Scenario A, `1/3` for Scenario B) and viewable visit feedback notes.
* **Test booking controls**: Marking as test successfully set the `is_test_booking = True` flag in DynamoDB.
* **Archive/Unarchive lifecycle**: 
  * Archiving Scenario D correctly kept the completed visit `COMPLETED` while setting active visits to `ARCHIVED`.
  * Unarchiving Scenario D correctly restored active visits to `ASSIGNED` while preserving completed visits as `COMPLETED`.

### 7.2. Integration Verification (Pass/Fail: PASS)
* **Postmark Emails**: Transactional messages were observed/logged as expected and dispatched only to the test accounts.
* **Google Calendar sync**:
  * Scenario A calendar event successfully synchronized (Event ID: `ropkttgbpmfi8mvmuul7iue3p8`).
  * Scenario D calendar event for active jobs was correctly deleted upon archiving, and recreated upon unarchiving.
  * No unexpected calendar deletions or creations occurred.

### 7.3. Daily Dispatch Export Validation (Pass/Fail: PASS)
* **Sheet Order**: Workbook sheet order matches:
  1. `Daily Dispatch` (First worksheet)
  2. `Export Summary`
  3. `All Requests`
* **Content Filters**: Confirmed that Scenario A and Scenario B active/completed visits were included in the export.
* **Exclusions**: Confirmed that Scenario C (test booking) and archived records were excluded from the Daily Dispatch sheet.
* **Sorting**: Confirmed that rows were sorted by Date, then Sitter Name, then time window order.

### 7.4. Cleanup (Pass/Fail: PASS)
* All dry-run request and job records were archived via the admin lifecycle controls to ensure clean database state.
* Completed visit records and notes were preserved, and future active events were canceled. No purges or destructive deletes were performed.

---

## 8. Operational Lessons and Findings
* **Meet & Greet Blocker**: Requests submitted without pre-linked pet profiles default to requiring a Meet & Greet. This is a design constraint, not a bug. The dry run confirms the correct operational flow is: 
  `Intake Submission` $\rightarrow$ `VERIFY_MEET_GREET (transitions to MG_COMPLETED)` $\rightarrow$ `Approval` $\rightarrow$ `Assignment`.
* **Date Configuration**: Scenario dates were shifted forward by one day (Scenario A/C to tomorrow, Scenario B/D starting the day after tomorrow) to avoid same-day visit window conflicts.

---

## 9. Final Recommendations
* **Status**: **PASS** (100% of validation scenarios completed successfully).
* **Git Status**: Clean.
* **Release 9F**: Not required.
* **Recommendation**: **Ryan is fully ready for structured testing.**

---

## 10. Deferred & Future Improvements
* Creating a dedicated testing script/checklist specifically for Ryan's live operational tests.
* Adding a user-friendly UI hint/tooltip in the Admin Dashboard explaining that the Meet & Greet must be verified before approval.
* Strengthening client-pet prelinking validation during public intake submission.
* Supporting staff-specific offline dispatch sheet exports.
* Creating an HTML print preview layout for dispatch sheets directly in the browser dashboard.
