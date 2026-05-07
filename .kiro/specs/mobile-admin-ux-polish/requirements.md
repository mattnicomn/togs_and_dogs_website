# Requirements Document

## Introduction

This feature improves the mobile usability, visual polish, navigation clarity, and owner-friendly language of the Tog & Dogs operations portal. The portal is used by Ryan (a non-technical pet care business owner) to manage bookings, staff, and clients. Changes are frontend-only, incremental, and production-safe. No backend APIs, DynamoDB schema, Cognito configuration, or RBAC logic will be modified.

## Glossary

- **Portal**: The Tog & Dogs operations web application hosted at toganddogs.usmissionhero.com
- **Admin_Dashboard**: The authenticated admin view where Ryan manages requests, staff, and clients
- **Request_List**: The filterable list of service requests and intake records within the Admin Dashboard
- **Record_Modal**: The detail overlay that opens when Ryan clicks on a specific request or record
- **Staff_Management**: The admin section for creating, editing, and managing staff login access
- **Client_Management**: The admin section for creating, editing, and managing client login access
- **Scheduler**: The calendar/timeline view showing upcoming scheduled visits
- **Client_Portal**: The client-facing view where customers see their own bookings
- **Status_Label**: The human-readable text displayed for a backend workflow status value
- **Access_Action**: A button or control that modifies a user's login access (disable, enable, reset password)
- **Mobile_Viewport**: A screen width of approximately 390px (iPhone-sized)
- **Tablet_Viewport**: A screen width of approximately 768px
- **Desktop_Viewport**: A screen width of approximately 1440px
- **Owner**: Ryan, the business owner who operates the portal daily
- **Protected_Account**: An admin or owner account that must not be accidentally modified by other admins

---

## Requirements

### Requirement 1: Mobile-Responsive Admin Dashboard Layout

**User Story:** As the Owner, I want the Admin Dashboard to be fully usable on my phone, so that I can manage my business while away from my desk.

#### Acceptance Criteria

1. WHEN the Portal is viewed at Mobile_Viewport width, THE Admin_Dashboard SHALL display all navigation elements, stat cards, and action buttons within the viewport width without horizontal scrolling.
2. WHEN the Portal is viewed at Mobile_Viewport width, THE Admin_Dashboard SHALL stack stat cards in a single column layout with all text rendered at a minimum font size of 14px.
3. WHEN the Portal is viewed at Mobile_Viewport width, THE Admin_Dashboard header SHALL collapse navigation items into a compact layout where no label is overlapped, truncated, or clipped by adjacent elements.
4. WHEN the Portal is viewed at Tablet_Viewport width, THE Admin_Dashboard SHALL display stat cards in a two-column grid with a minimum spacing of 8px between all interactive elements.
5. WHEN the Portal is viewed at Mobile_Viewport width, THE Admin_Dashboard SHALL render all interactive elements (buttons, links, toggles) with a minimum tap target size of 44x44 pixels.

---

### Requirement 2: Mobile-Responsive Request List

**User Story:** As the Owner, I want the Request List to be readable and usable on my phone, so that I can review and act on requests from anywhere.

#### Acceptance Criteria

1. WHEN the Portal is viewed at Mobile_Viewport width, THE Request_List SHALL display each record as a stacked card rather than a wide table row.
2. WHEN the Portal is viewed at Mobile_Viewport width, THE Request_List SHALL display client name, pet name, status chip, and service dates at a minimum font size of 14px, wrapping text to additional lines rather than truncating or causing horizontal overflow.
3. WHEN the Portal is viewed at Mobile_Viewport width, THE Request_List action buttons SHALL have a minimum tap target size of 44x44 pixels and a minimum spacing of 8px between adjacent tap targets.
4. WHEN the Portal is viewed at Mobile_Viewport width, THE Request_List filter panel SHALL collapse into a dropdown or toggle activated by a visible control, and SHALL display an indicator of the number of active filters when the panel is collapsed.
5. WHEN the Portal is viewed at Mobile_Viewport width, THE Request_List SHALL display a minimum of 3 cards in the visible area without requiring scrolling past the filter controls.

---

### Requirement 3: Mobile-Responsive Record Modal

**User Story:** As the Owner, I want record detail modals to work properly on my phone, so that I can view and act on individual records without layout issues.

#### Acceptance Criteria

1. WHEN the Record_Modal is opened at Mobile_Viewport width, THE Portal SHALL display the modal as a full-screen overlay with a close button that has a minimum tap target size of 44x44 pixels and is positioned at the top-right corner of the modal.
2. WHEN the Record_Modal is opened at Mobile_Viewport width, THE Portal SHALL stack all form fields and action buttons vertically with a minimum of 12px spacing between each element, and action buttons SHALL have a minimum tap target size of 44x44 pixels.
3. WHEN the Record_Modal is opened at Mobile_Viewport width, THE Portal SHALL allow the modal content to scroll vertically without the background page scrolling.
4. WHEN the Record_Modal is opened at Mobile_Viewport width, THE Portal SHALL display all modal content without horizontal scrolling or overflow beyond the viewport edges.

---

### Requirement 4: Mobile-Responsive Staff and Client Management

**User Story:** As the Owner, I want Staff Management and Client Management screens to work on my phone, so that I can manage team and client access on the go.

#### Acceptance Criteria

1. WHEN the Staff_Management section is viewed at Mobile_Viewport width, THE Portal SHALL display each staff member as a card in a single-column layout with name, access level, and status visible at a minimum font size of 14px without horizontal scrolling, and all interactive elements on the card SHALL have a minimum tap target size of 44x44 pixels.
2. WHEN the Client_Management section is viewed at Mobile_Viewport width, THE Portal SHALL display each client as a card in a single-column layout with name, email, and access status visible at a minimum font size of 14px without horizontal scrolling, and all interactive elements on the card SHALL have a minimum tap target size of 44x44 pixels.
3. WHEN an Access_Action button is tapped at Mobile_Viewport width, THE Portal SHALL display the confirmation dialog fully within the viewport without clipping or extending beyond screen edges, with dialog action buttons having a minimum tap target size of 44x44 pixels and a visible close or cancel control to dismiss the dialog.

---

### Requirement 5: Mobile-Responsive Scheduler

**User Story:** As the Owner, I want the Scheduler to be usable on my phone, so that I can check upcoming visits while in the field.

#### Acceptance Criteria

1. WHEN the Scheduler is viewed at Mobile_Viewport width, THE Portal SHALL display scheduled visits in a vertically scrollable list format rather than a wide timeline that requires horizontal scrolling.
2. WHEN the Scheduler is viewed at Mobile_Viewport width, THE Portal SHALL display the date, time, client name, pet name, and assigned staff for each visit without truncation.
3. WHEN the Scheduler is viewed at Mobile_Viewport width, THE Portal SHALL display visits in chronological order with the nearest upcoming visit appearing first.
4. IF no visits are scheduled for the selected date range at Mobile_Viewport width, THEN THE Portal SHALL display an empty-state message indicating that no visits are scheduled.
5. WHEN the Scheduler is viewed at Mobile_Viewport width, THE Portal SHALL ensure all tappable visit entries and navigation controls have a minimum tap target size of 44x44 pixels.

---

### Requirement 6: Owner-Friendly Status Labels

**User Story:** As the Owner, I want status labels to use plain business language, so that I can understand what stage each request is in without technical knowledge.

#### Acceptance Criteria

1. WHEN the record is a VISIT_BOOKING workflow type, THE Portal SHALL display the status label "New Request" for backend status values PENDING_REVIEW and NEEDS_REVIEW.
2. THE Portal SHALL display the status label "Needs Meet & Greet" for backend status values MEET_GREET_REQUIRED and NEEDS_MG.
3. THE Portal SHALL display the status label "Needs Price Quote" for backend status value QUOTE_NEEDED.
4. WHEN the record is a VISIT_BOOKING workflow type, THE Portal SHALL display the status label "Approved / Ready to Schedule" for backend status values APPROVED and BOOKED.
5. THE Portal SHALL display the status label "Scheduled with Staff" for backend status values ASSIGNED, JOB_CREATED, and SCHEDULED.
6. THE Portal SHALL display the status label "Visit Completed" for backend status value COMPLETED.
7. THE Portal SHALL display the status label "Saved for Records" for backend status values ARCHIVED and ARCHIVE.
8. THE Portal SHALL display the status label "Trash" for backend status values DELETED, DELETE, and TRASH.
9. WHEN the record is a CUSTOMER_INTAKE workflow type, THE Portal SHALL display the status label "New Registration" for backend status values PENDING_REVIEW and NEEDS_REVIEW, and the status label "Approved Client" for backend status values APPROVED and BOOKED.
10. IF the Portal receives a backend status value that is not listed in criteria 1–9, THEN THE Portal SHALL display the raw backend status value formatted with underscores replaced by spaces and in title case.
11. THE Portal SHALL preserve all backend status values unchanged when writing to the API or DynamoDB, ensuring that label mapping is applied only at the display layer.

---

### Requirement 7: Owner-Friendly Staff Management Language

**User Story:** As the Owner, I want staff management actions described in plain language, so that I understand exactly what each button does without needing technical knowledge.

#### Acceptance Criteria

1. THE Staff_Management section SHALL display the label "Access Level" instead of "Role" for the staff permission field.
2. THE Staff_Management section SHALL display the action label "Turn Off Login Access" instead of "Disable user" for the deactivation control.
3. THE Staff_Management section SHALL display the action label "Restore Login Access" instead of "Enable user" for the reactivation control.
4. THE Staff_Management section SHALL display the action label "Set Temporary Password" instead of "Set Temp Pass" for the temporary password control.
5. THE Staff_Management section SHALL display the action label "Send Password Reset Email" instead of "Send Reset" for the password reset control.
6. THE Staff_Management section SHALL not display the terms "Cognito" or "User Pool" in any user-facing text, including labels, buttons, messages, tooltips, placeholder text, and error messages.
7. THE Staff_Management section SHALL visually group login identity fields (email) separately from profile detail fields (display name, phone, notes) using a distinct section heading for each group and a visible divider or spacing between them.
8. THE Staff_Management section SHALL display helper text adjacent to the login identity group that indicates the email address is used for signing in, and helper text adjacent to the profile details group that indicates these fields are for display purposes only and do not affect login.

---

### Requirement 8: Owner-Friendly Client Management Language

**User Story:** As the Owner, I want client management actions described in plain language, so that I can manage client access confidently.

#### Acceptance Criteria

1. THE Client_Management section SHALL display the action label "Turn Off Login Access" instead of "Disable user" for the deactivation control.
2. THE Client_Management section SHALL display the action label "Restore Login Access" instead of "Enable user" for the reactivation control.
3. THE Client_Management section SHALL display the action label "Set Temporary Password" instead of "Set Temp Pass" for the temporary password control.
4. THE Client_Management section SHALL display the action label "Send Password Reset Email" instead of "Send Reset" for the password reset control.
5. THE Client_Management section SHALL not display the terms "Cognito" or "User Pool" in any user-facing label, button, tooltip, confirmation dialog, or error message.
6. THE Client_Management section SHALL group login identity fields (email) and profile detail fields (display name, phone, address, notes) into visually distinct sections, each with its own section heading, separated by whitespace or a divider.
7. THE Client_Management section SHALL display helper text beneath the login identity section heading that communicates that the email address is used for signing in and cannot be changed without affecting login access.

---

### Requirement 9: Protected Account Guardrails

**User Story:** As the Owner, I want to be prevented from accidentally breaking my own admin account or other protected accounts, so that I do not lock myself out of the system.

#### Acceptance Criteria

1. WHEN the Owner views a Protected_Account in Staff_Management, THE Portal SHALL disable the "Turn Off Login Access", "Set Temporary Password", "Send Password Reset Email", and any profile deletion controls for that account.
2. WHEN the Owner views a Protected_Account in Staff_Management, THE Portal SHALL display a "Protected Platform Admin" label adjacent to the account name that is visible without scrolling or expanding additional panels.
3. WHEN the Owner views their own account in Staff_Management, THE Portal SHALL disable the "Turn Off Login Access" and any profile deletion controls for that account.
4. IF the Owner attempts to invoke a disabled action on a Protected_Account or their own account, THEN THE Portal SHALL display a message indicating why the action is blocked (protected account or self-account) and SHALL NOT execute the action.

---

### Requirement 10: Improved Confirmation Messages

**User Story:** As the Owner, I want confirmation dialogs to clearly explain what will happen, so that I can make informed decisions before taking action.

#### Acceptance Criteria

1. WHEN the Owner triggers an Access_Action, THE Portal SHALL display a confirmation dialog that names the affected person by display name and describes the specific change to their access state (e.g., "Turn off login access for Sarah Jones — she will not be able to sign in until access is restored").
2. WHEN the Owner triggers a destructive action (disable access, delete record, purge record), THE Portal SHALL display a confirmation dialog that describes the outcome, states whether the action is reversible or permanent, and requires the Owner to click a distinct "Confirm" button to proceed.
3. IF the Owner dismisses or cancels a confirmation dialog, THEN THE Portal SHALL close the dialog without executing the action and without modifying any data.
4. WHEN the Owner triggers a bulk action on 2 or more records, THE Portal SHALL display the count of affected records and the action that will be applied to all of them, and require explicit confirmation before executing the action.

---

### Requirement 11: Navigation and Visual Hierarchy Improvements

**User Story:** As the Owner, I want the portal layout to be clean and easy to scan, so that I can find what I need quickly without feeling overwhelmed.

#### Acceptance Criteria

1. THE Admin_Dashboard SHALL group related action buttons (e.g., status-change actions together, access actions together) with a minimum of 8px spacing between buttons within a group and a minimum of 24px spacing or a visible divider between unrelated button groups.
2. THE Admin_Dashboard SHALL use a visual hierarchy where primary actions use a filled/solid button style and secondary actions use an outlined or text-only button style, and destructive actions use a distinct warning style, consistent with the button style rules defined in Requirement 12.
3. THE Admin_Dashboard sidebar filter labels SHALL use plain business language matching the owner-friendly status labels defined in Requirement 6.
4. WHEN the Portal is viewed at Mobile_Viewport width, THE Admin_Dashboard SHALL display only the client name, pet name, status label, and next service date per record, hiding supplementary metadata such as creation timestamps, internal IDs, and audit fields.
5. WHEN the Portal is viewed at Mobile_Viewport width, THE Admin_Dashboard action button groups SHALL remain accessible via a collapsed menu or secondary tap rather than being removed entirely.

---

### Requirement 12: Theme and Visual Consistency

**User Story:** As the Owner, I want the portal to look like a friendly pet care business tool rather than a technical admin console, so that it feels approachable and professional.

#### Acceptance Criteria

1. THE Portal SHALL use consistent spacing, font sizes, border radii, and color values across all cards, buttons, modals, and form elements, such that every instance of the same element type uses identical visual properties throughout the application.
2. THE Portal SHALL use a warm, clean color palette drawn from soft blues, greens, and warm neutrals, and SHALL NOT use high-saturation neon colors, pure black (#000000) backgrounds, or monochrome gray-only schemes.
3. THE Portal SHALL use consistent button styles where primary actions share one visually prominent style, secondary actions share a visually subdued style, and destructive actions use a distinct warning style that is visually distinguishable from both primary and secondary styles without relying on color alone.
4. THE Portal SHALL ensure all text meets a minimum contrast ratio of 4.5:1 against its background for readability, and all interactive components (buttons, links, form controls) meet a minimum contrast ratio of 3:1 against adjacent colors.
5. THE Portal SHALL use a minimum body text font size of 14px and a minimum interactive element label font size of 14px across all viewport sizes.
6. THE Portal SHALL display visible focus indicators on all interactive elements when navigated via keyboard, and SHALL display hover state changes on all clickable elements when using a pointer device.

---

### Requirement 13: No Backend or Schema Changes

**User Story:** As the development team, I want this feature to be frontend-only, so that we do not risk breaking production APIs, data, or authentication.

#### Acceptance Criteria

1. THE Portal SHALL not modify any backend Lambda function, API Gateway endpoint, Step Function definition, or infrastructure-as-code template (CloudFormation, SAM) that provisions these resources.
2. THE Portal SHALL not modify the DynamoDB table schema, Global Secondary Indexes (StatusIndex, WorkerIndex), or access patterns defined in the data model.
3. THE Portal SHALL not modify the Cognito User Pool configuration, triggers, or authentication flow.
4. THE Portal SHALL not modify RBAC permission boundaries (Admin, Staff, Owner, Client access levels remain functionally identical).
5. THE Portal SHALL preserve all existing functionality; no feature, button, or workflow available in the production deployment at the time development begins shall be removed or made unreachable.
6. WHEN a pull request is submitted for this feature, THE Portal's changeset SHALL contain modifications only to frontend source files, frontend configuration files, and static assets; zero changes to backend source files, Lambda handlers, API definitions, or infrastructure templates shall be present in the diff.

---

### Requirement 14: Build Verification

**User Story:** As the development team, I want all changes to pass the build step, so that we can deploy safely to production.

#### Acceptance Criteria

1. WHEN the changeset is ready for merge, THE Portal project SHALL exit with code 0 when `npm run build` is executed from the `web/` directory.
2. WHEN the changeset is ready for merge, THE Portal project SHALL produce no new lint warnings from `npm run lint` (executed from the `web/` directory) compared to the warning count on the target branch prior to the changes.
