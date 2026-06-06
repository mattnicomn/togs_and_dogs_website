# Release 8W: Admin Web Visibility of Completed Visit Notes

**Status:** Planning
**Priority:** Medium (operational value — admin visibility of visit completions)
**Risk to Production:** Low (read-only web UI changes + single backend security enhancement)
**Terraform Required:** No
**Backend Changes:** Yes — minor (redact fields from clients in `common/auth.py`'s `client_sensitive_fields`)
**Scope:** Web admin visibility for completed notes, author, and timestamp + client-side API sanitization

---

## 1. Purpose

With Release 8V, staff users can now enter optional visit notes in the mobile app when marking a booking as completed. These notes, along with completion metadata (`completed_by`, `completed_at`), are successfully saved to the parent request record (`REQ#`) in the backend. 

The purpose of Release 8W is to expose this completion data to admin/owner users in the React Admin Dashboard, allowing Ryan/admin to review completion notes and metadata directly on the web. This release focuses on read-only visibility, UX safeguards, data privacy, and Excel export inclusion.

---

## 2. Current State

* **Mobile App:** Staff can enter optional visit notes on completion. This writes `visit_notes`, `completed_at`, and `completed_by` to the DynamoDB `REQ#` record.
* **Backend API (`GET /admin/requests`):** Returns all request fields to roles `owner` and `admin` unredacted. For role `staff`, it also returns them as they are not listed in `sensitive_fields` in `src/backend/common/auth.py`. 
* **Backend API (`GET /client/requests`):** Currently returns these fields to clients because they are not listed in `client_sensitive_fields` in `src/backend/common/auth.py`. This is a minor privacy leak that must be addressed.
* **Web Admin Dashboard (`AdminDashboard.jsx`):** Has no display logic for completed visit notes, completion author, or completion timestamp.
* **Web CareCard (`CareCard.jsx`):** Displays request details in the admin portal but lacks a section for completion notes or completion metadata.
* **Offline Backup/Export (`XLSX`):** The Excel export mapping in the web dashboard does not include completion notes or completion metadata.

---

## 3. API Field Availability & Sanitization

### Backend API Check
* `GET /admin/requests` queries DynamoDB and calls `sanitize_booking_for_role(item, role)`.
* For roles `owner` and `admin`, the helper returns the raw database record without redaction. Therefore, the API responses already include `visit_notes`, `completed_at`, and `completed_by` for admins. No backend modification is needed for admin data retrieval.
* For role `staff`, the fields are not redacted by `sensitive_fields`, which is correct as staff should be able to view notes on their own completed requests.
* For role `client`, the fields are currently returned. Since clients should not see completion notes or metadata in this release, we must perform a minor backend change.

### Proposed Backend Change (Minimal)
We will add `visit_notes`, `completed_at`, and `completed_by` to `client_sensitive_fields` in `src/backend/common/auth.py` to prevent them from being returned in client portal responses.

**File:** [auth.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/auth.py)
```python
    # Fields to additionally redact for clients only
    client_sensitive_fields = [
        'staff_assignment',
        'worker_id',
        'job_id',
        'assignment_color',
        'visit_notes',
        'completed_by',
        'completed_at'
    ]
```

---

## 4. Web Dashboard UI Layout & Placement

The visit completion details will be integrated in three places within the React Admin Dashboard:

### A. Request Card Details (CareCard)
Inside `CareCard.jsx`, we will render a new card section when a completed request is viewed:
* **Placement:** Below the "Service Information" section or in a dedicated "Completion Summary" section.
* **Visibility:** Only rendered if `pet._originItem?.status === 'COMPLETED'`.
* **Content:** 
  * Header: "Visit Completion Info"
  * Completed By: `<Staff Email / Display Name>`
  * Completed At: `<Formatted Local Date/Time>`
  * Notes Box: The raw `visit_notes` content, or a placeholder if empty.

### B. Completed Visits Section (Request List View)
In the Request List table, completed requests will have a visual indicator:
* **Indicator:** Under the "Status" column, if the status is `COMPLETED`, we will render a small "Note" icon (e.g. 📝) next to the chip if `visit_notes` exists, indicating that there is a note available to read.
* Hovering over the icon can show a tooltip: "Hover or click to read completion notes".

### C. Admin Request List Expanded View
We will implement an expanded detail row inside the request table in `AdminDashboard.jsx`.
* **Mechanism:** 
  * Add a toggle button (using a chevron `▸` or `▾`) to the left of each row (or inside the checkbox column).
  * Maintain an `expandedIds` array in `AdminDashboard` state.
  * Clicking the chevron toggles the request ID in the `expandedIds` array.
  * When a request is expanded, render an extra `<tr>` directly below the main row spanning all columns (`colSpan={7}`).
  * Within this extra row, render a styled, full-width details panel containing:
    * The service details.
    * The completion metadata (Completed By, Completed At).
    * The full completion notes box.

---

## 5. UI Formatting Rules & UX Guardrails

### UI Formatting Rules
1. **Preserve Line Breaks:** To ensure notes look exactly as the staff typed them on mobile, we will apply the CSS rule `white-space: pre-wrap` on the visit notes container:
   ```html
   <p style={{ white-space: 'pre-wrap' }}>{item.visit_notes}</p>
   ```
2. **Fallback Placeholder:** If a visit was marked completed but no note was provided, we will display:
   * `"No completion notes provided"` (styled in a light italicized text, e.g. using class `text-muted` or a soft style).
3. **Readable Date/Time Format:** Completed timestamps (`completed_at`) will be formatted using the browser's local time formatting:
   ```javascript
   new Date(item.completed_at).toLocaleString('en-US', {
     month: 'short',
     day: 'numeric',
     year: 'numeric',
     hour: 'numeric',
     minute: '2-digit',
     hour12: true
   })
   ```

### UX Guardrails (Read-Only)
* **Strictly Read-Only:** The notes and metadata will be displayed in standard text containers. No input fields, textareas, edit icons, or submit buttons will be provided.
* **No Edit/Delete Flows:** Admins cannot edit or delete the completion notes. They are saved as immutable records of the staff's action.
* **No Email Triggers:** Opening or viewing notes will not send notifications, emails, or updates to the client or staff.
* **No Calendar Updates:** No calendar integrations will be triggered by viewing these notes.

### Excel Export/Offline Backup Integration
The export mapping function (`mapRequest` helper inside `AdminDashboard.jsx`) will be updated to include the completion fields in all exported request sheets:
* `"Visit Notes"`: `r.visit_notes || ""`
* `"Completed By"`: `r.completed_by || ""`
* `"Completed At"`: `r.completed_at || ""`

---

## 6. Role-Based Visibility Matrix

| Role | API Access | Can View notes on Web? | Can View notes on Mobile? | Can Edit Notes? |
|------|------------|------------------------|---------------------------|-----------------|
| **Owner / Admin** | Unredacted | Yes (CareCard, list view, export) | Yes (read-only details) | No |
| **Staff** | Own assignments only | Yes (if web access matches existing assigned rules) | Yes (entered on completion, own visits) | No (after submit) |
| **Client** | Redacted (None) | No | No | No |

---

## 7. Verification & Validation Checklist

### Automated Tests
1. **Unit Test for Redaction:**
   * Create a test case in a new or existing test file (e.g., `tests/backend/test_r8v_visit_notes.py`) that executes `sanitize_booking_for_role(record, 'client')` with a completed booking record.
   * Assert that `visit_notes`, `completed_at`, and `completed_by` are set to `None` in the returned sanitized dictionary.
   * Assert that they remain intact when calling `sanitize_booking_for_role(record, 'admin')` or `'owner'`.
2. **Run All Backend Tests:**
   * Command: `py -m pytest tests/backend/`

### Manual Verification
1. **Completed Request with Note:**
   * Mark a request completed with a multi-line note on the mobile app.
   * Open the Web Admin Dashboard as an Admin.
   * Verify that the note appears with line breaks preserved under the request list's expanded row and the CareCard.
   * Verify that the author's email and completed timestamp are shown in a human-readable format.
2. **Completed Request without Note:**
   * Mark another request completed with empty notes.
   * Verify that it shows `"No completion notes provided"` on the web dashboard.
3. **Multi-Day Completed Request:**
   * Mark a multi-day request completed.
   * Verify that the completion notes and metadata are displayed on the parent request details.
4. **Admin View After Refresh:**
   * Refresh the page and ensure the metadata loads correctly and does not disappear.
5. **No Visibility on Non-Completed Requests:**
   * Ensure that requests with statuses like `PENDING_REVIEW`, `APPROVED`, or `ASSIGNED` do not render the completion section or completion metadata unless completion data exists.
6. **Client Redaction Check:**
   * Log into the client portal (or simulate a request to `/client/requests`).
   * Verify that the completion notes and completion metadata fields are completely absent or returned as `null` in the payload.
7. **Offline Backup Check:**
   * Trigger the "Export Data" button from the Admin Dashboard.
   * Open the generated Excel file.
   * Confirm that columns `"Visit Notes"`, `"Completed By"`, and `"Completed At"` are present and correctly populated for completed requests.

---

## 8. Rollback Plan

In the event of unexpected web dashboard errors or database access issues:
1. **Revert Frontend Changes:** Use `git restore` on `web/src/components/AdminDashboard.jsx` and `web/src/components/CareCard.jsx` to revert UI changes to `HEAD`.
2. **Revert Backend Changes:** Use `git restore` on `src/backend/common/auth.py`.
3. **Redeploy Backend:** Run the Terraform deployment script to redeploy the modified authentication/admin lambdas if they were deployed.
4. **Verify Rollback:** Verify that the admin dashboard runs normally without expanded rows and that no client portal data issues occur.

---

## 9. AG Implementation Prompt (DO NOT RUN UNTIL MATTHEW APPROVES)

```
DO NOT RUN UNTIL MATTHEW APPROVES.

Please implement Release 8W admin web visibility for completed visit notes.

Backend Steps:
1. Add 'visit_notes', 'completed_by', and 'completed_at' to the client_sensitive_fields list in src/backend/common/auth.py to prevent clients from viewing notes in the client portal.
2. Add a pytest unit test in tests/backend/test_r8v_visit_notes.py (or a new test file) verifying that sanitize_booking_for_role(item, 'client') correctly redacts 'visit_notes', 'completed_by', and 'completed_at', while leaving them unredacted for 'admin' and 'owner' roles.
3. Run pytest on the modified test files.

Frontend Steps:
1. In web/src/components/CareCard.jsx:
   - Identify the tab rendering or main sections.
   - When pet._originItem?.status === 'COMPLETED', render a new card section for "Visit Completion Info" under the Service details or on the overview tab.
   - Display Completed By, Completed At (formatted using item.completed_at and toLocaleString), and Visit Notes (using CSS white-space: 'pre-wrap' to preserve line breaks).
   - If visit_notes is empty/null, render "No completion notes provided" in italicized soft text.
2. In web/src/components/AdminDashboard.jsx:
   - Define a new state variable: const [expandedRequests, setExpandedRequests] = useState({}); (or use an array of expanded IDs).
   - In the request list table table body visibleRecords.map:
     - Add a column or chevron button to the left of the checkbox that allows toggling expansion.
     - When a row is expanded, render an additional <tr> below it with colSpan={7} containing the completion notes and completion metadata for completed requests (or general request summary for other statuses).
     - When status is COMPLETED and notes are present, render a small note icon (e.g. 📝) next to the status chip in the main table row.
   - Update the mapRequest helper used in handleExportData to map "Visit Notes" (r.visit_notes || ""), "Completed By" (r.completed_by || ""), and "Completed At" (r.completed_at || "") so they are correctly exported.
3. Run `npm run dev` and perform validation checks.
```
