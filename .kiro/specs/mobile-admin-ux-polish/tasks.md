# Implementation Plan: Mobile Admin UX Polish

## Overview

Frontend-only improvements to the Tog & Dogs operations portal for mobile usability, owner-friendly language, and visual polish. All changes target CSS files and JSX components within `web/src/`. No backend, DynamoDB, Cognito, or RBAC changes. Each task group ends with a build verification step.

## Tasks

- [x] 1. Mobile CSS/layout improvements
  - [x] 1.1 Add mobile breakpoint for Admin Dashboard stat cards and header
    - Add `@media (max-width: 480px)` rules to `web/src/Admin.css` for `.admin-stats-grid` (single-column layout, 12px gap)
    - Add tablet breakpoint `@media (min-width: 481px) and (max-width: 768px)` for two-column stat cards with 8px gap
    - Add mobile header/nav compact layout rules to `web/src/App.css` (no label overlap, no truncation)
    - Add minimum tap target size (44x44px, 12px+ padding) for all buttons/links at mobile viewport in `web/src/Admin.css`
    - Ensure minimum 14px font size for stat card text at mobile viewport
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 1.2 Add mobile card layout for Request List
    - Add `@media (max-width: 480px)` rules to `web/src/Admin.css` to convert `.request-table` rows into stacked cards (hide thead, flex-column tbody tr)
    - Ensure client name, pet name, status chip, and service dates display at 14px+ with text wrapping (no truncation, no horizontal overflow)
    - Add 44x44px minimum tap targets and 8px spacing between action buttons at mobile viewport
    - _Requirements: 2.1, 2.2, 2.3, 2.5_

  - [x] 1.3 Add mobile filter panel collapse for Request List
    - In `web/src/components/AdminDashboard.jsx`, add a toggle button to show/hide the filter panel at mobile viewport
    - Display active filter count badge on the toggle button when filters are applied and panel is collapsed
    - Add corresponding CSS in `web/src/Admin.css` for the collapsed filter panel and toggle control
    - _Requirements: 2.4_

  - [x] 1.4 Add mobile responsive layout for Scheduler
    - In `web/src/components/MasterScheduler.jsx`, add conditional rendering for mobile viewport: vertically scrollable list instead of wide timeline
    - Display date, time, client name, pet name, and assigned staff for each visit without truncation
    - Display visits in chronological order with nearest upcoming first
    - Add empty-state message when no visits are scheduled for the selected date range
    - Add 44x44px tap targets for visit entries and navigation controls at mobile viewport
    - Add corresponding CSS in `web/src/Admin.css` or inline within the component
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 1.5 Build verification — mobile CSS/layout
    - Run `npm run build` from `web/` directory — must exit with code 0
    - Run `npm run lint` from `web/` directory — must produce no new warnings
    - _Requirements: 14.1, 14.2_

- [x] 2. Record modal mobile usability
  - [x] 2.1 Implement full-screen mobile modal and scroll lock
    - Add `@media (max-width: 480px)` rules to `web/src/Admin.css` for `.modal-content`: width 100%, height 100dvh, border-radius 0, overflow-y auto
    - Add close button positioning at top-right with 44x44px tap target and `position: sticky; top: 0`
    - In `web/src/components/AdminDashboard.jsx`, add `useEffect` scroll lock logic: set `document.body.style.overflow = 'hidden'` and `position: fixed` when modal opens, restore on close/unmount
    - Ensure modal content scrolls vertically without background page scrolling
    - Ensure no horizontal overflow within the modal at mobile viewport
    - Stack all form fields and action buttons vertically with 12px+ spacing, 44x44px action button tap targets
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [x] 2.2 Apply full-screen mobile treatment to CareCard modal
    - In `web/src/components/CareCard.jsx`, apply the same scroll lock pattern (useEffect with body overflow/position)
    - Add `@media (max-width: 480px)` rules to `web/src/Portal.css` for CareCard overlay: full-screen, close button 44x44px at top-right
    - Ensure vertical stacking and no horizontal overflow at mobile viewport
    - _Requirements: 3.1, 3.3, 3.4_

  - [x] 2.3 Build verification — modal changes
    - Run `npm run build` from `web/` directory — must exit with code 0
    - Run `npm run lint` from `web/` directory — must produce no new warnings
    - _Requirements: 14.1, 14.2_

- [x] 3. Staff/client management wording and layout
  - [x] 3.1 Update Staff Management labels and remove Cognito terminology
    - In `web/src/components/AdminDashboard.jsx`, replace "Role" label with "Access Level" for staff permission field
    - Replace "Disable Access" / "Disable user" with "Turn Off Login Access"
    - Replace "Enable Access" / "Enable user" with "Restore Login Access"
    - Replace "Set Temp Pass" with "Set Temporary Password"
    - Replace "Send Reset" with "Send Password Reset Email"
    - Replace all user-facing instances of "Cognito" and "User Pool" (e.g., "Onboard New Cognito User" → "Create Login & Profile", "Cognito Only" → "Login Only", "Link Cognito Login" → "Link Login Account", "Delete Cognito User" → "Delete Login Account")
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 3.2 Add field grouping and helper text to Staff Management
    - In `web/src/components/AdminDashboard.jsx`, restructure staff edit/create form into two visual groups:
      - Group 1 "Login Identity": email field, helper text "This email address is used for signing in."
      - Group 2 "Profile Details": display name, phone, notes fields, helper text "These fields are for display purposes only and do not affect login."
    - Add section headings (`<h4>`) and 24px spacing between groups
    - Add CSS for field group styling in `web/src/Admin.css`
    - _Requirements: 7.7, 7.8_

  - [x] 3.3 Update Client Management labels and remove Cognito terminology
    - In `web/src/components/AdminDashboard.jsx`, replace client action labels:
      - "Disable user" → "Turn Off Login Access"
      - "Enable user" → "Restore Login Access"
      - "Set Temp Pass" → "Set Temporary Password"
      - "Send Reset" → "Send Password Reset Email"
    - Remove all user-facing "Cognito" and "User Pool" references in client management section
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 3.4 Add field grouping and helper text to Client Management
    - In `web/src/components/AdminDashboard.jsx`, restructure client edit/create form into two visual groups:
      - Group 1 "Login Identity": email field, helper text "This email address is used for signing in and cannot be changed without affecting login access."
      - Group 2 "Profile Details": display name, phone, address, notes fields
    - Add section headings and visual separation (24px spacing or divider)
    - _Requirements: 8.6, 8.7_

  - [x] 3.5 Add mobile responsive card layout for Staff and Client lists
    - Add `@media (max-width: 480px)` CSS in `web/src/Admin.css` for staff/client list items: single-column card layout, name/access level/status visible at 14px+, 44x44px tap targets on all interactive elements
    - Ensure confirmation dialogs display fully within viewport at mobile width with 44x44px dialog buttons and visible cancel control
    - _Requirements: 4.1, 4.2, 4.3_

  - [x] 3.6 Build verification — staff/client management
    - Run `npm run build` from `web/` directory — must exit with code 0
    - Run `npm run lint` from `web/` directory — must produce no new warnings
    - _Requirements: 14.1, 14.2_

- [x] 4. Confirmation dialog improvements
  - [x] 4.1 Replace window.confirm with modal-based confirmation dialogs
    - In `web/src/components/AdminDashboard.jsx`, identify all `window.confirm()` calls in staff/client action handlers
    - Replace each with the existing modal overlay pattern (`modal-overlay` + `modal-content`) using component state to control visibility
    - Each confirmation dialog must include: person's display name, plain-language description of the action, reversibility statement, distinct "Confirm" button, and a "Cancel" button
    - Dismissing or canceling must close the dialog without executing the action
    - _Requirements: 10.1, 10.2, 10.3_

  - [x] 4.2 Add bulk action confirmation dialog
    - In `web/src/components/AdminDashboard.jsx`, ensure bulk actions on 2+ records display a confirmation dialog showing the count of affected records and the action to be applied
    - Require explicit "Confirm" click before executing bulk actions
    - _Requirements: 10.4_

  - [x] 4.3 Add protected account guardrails
    - In `web/src/components/AdminDashboard.jsx`, disable "Turn Off Login Access", "Set Temporary Password", "Send Password Reset Email", and delete controls for protected accounts (matching `PROTECTED_SUBS` or `PROTECTED_EMAILS`)
    - Display "Protected Platform Admin" label adjacent to protected account names
    - Disable "Turn Off Login Access" and delete controls for the current user's own account
    - If a disabled action is attempted, display a message explaining why it is blocked
    - Use both `disabled` attribute and `pointer-events: none` CSS
    - _Requirements: 9.1, 9.2, 9.3, 9.4_

  - [x] 4.4 Build verification — confirmation dialogs
    - Run `npm run build` from `web/` directory — must exit with code 0
    - Run `npm run lint` from `web/` directory — must produce no new warnings
    - _Requirements: 14.1, 14.2_

- [x] 5. Status label and helper text improvements
  - [x] 5.1 Update getStatusLabel function for owner-friendly labels
    - In `web/src/components/AdminDashboard.jsx`, update the `getStatusLabel()` function to return:
      - `PENDING_REVIEW` / `NEEDS_REVIEW` (VISIT_BOOKING) → "New Request"
      - `MEET_GREET_REQUIRED` / `NEEDS_MG` → "Needs Meet & Greet"
      - `QUOTE_NEEDED` → "Needs Price Quote"
      - `APPROVED` / `BOOKED` (VISIT_BOOKING) → "Approved / Ready to Schedule"
      - `ASSIGNED` / `JOB_CREATED` / `SCHEDULED` → "Scheduled with Staff"
      - `COMPLETED` → "Visit Completed"
      - `ARCHIVED` / `ARCHIVE` → "Saved for Records"
      - `DELETED` / `DELETE` / `TRASH` → "Trash"
      - `PENDING_REVIEW` / `NEEDS_REVIEW` (CUSTOMER_INTAKE) → "New Registration"
      - `APPROVED` / `BOOKED` (CUSTOMER_INTAKE) → "Approved Client"
    - Add fallback: unknown statuses formatted as title case with underscores replaced by spaces
    - Ensure label mapping is display-only — no changes to values sent to API
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9, 6.10, 6.11_

  - [x] 5.2 Update sidebar filter labels to use owner-friendly status names
    - In `web/src/components/AdminDashboard.jsx`, update the sidebar filter options to display the same owner-friendly labels from `getStatusLabel`
    - _Requirements: 11.3_

  - [x] 5.3 Build verification — status labels
    - Run `npm run build` from `web/` directory — must exit with code 0
    - Run `npm run lint` from `web/` directory — must produce no new warnings
    - _Requirements: 14.1, 14.2_

- [x] 6. Visual hierarchy, theme consistency, and accessibility
  - [x] 6.1 Add button hierarchy and action grouping styles
    - In `web/src/Admin.css`, define consistent button styles: primary (filled/solid), secondary (outlined/text-only), destructive (warning style distinguishable without color alone)
    - Add spacing rules: 8px between buttons within a group, 24px or visible divider between unrelated groups
    - In `web/src/components/AdminDashboard.jsx`, apply appropriate button classes to action buttons
    - _Requirements: 11.1, 11.2, 12.3_

  - [x] 6.2 Add mobile metadata hiding and collapsed action menus
    - In `web/src/components/AdminDashboard.jsx`, at mobile viewport show only client name, pet name, status label, and next service date per record
    - Hide supplementary metadata (creation timestamps, internal IDs, audit fields) at mobile viewport via CSS or conditional rendering
    - Ensure action button groups remain accessible via a collapsed menu or secondary tap (not removed entirely)
    - _Requirements: 11.4, 11.5_

  - [x] 6.3 Add focus indicators, hover states, and contrast fixes
    - In `web/src/index.css`, add `:focus-visible` styles with 3px solid outline and 2px offset for all interactive elements
    - Add hover state changes for all clickable elements
    - Verify and fix `--text-muted` color to meet 4.5:1 contrast ratio (darken from `#8a8a86` to approximately `#6a6a66` if needed)
    - Ensure minimum 14px body text and interactive element label font size across all viewports
    - _Requirements: 12.4, 12.5, 12.6_

  - [x] 6.4 Ensure consistent spacing, border-radius, and color palette
    - In `web/src/index.css` and `web/src/Admin.css`, audit and normalize CSS custom properties for consistent spacing, border-radius, and colors across cards, buttons, modals, and form elements
    - Ensure warm color palette (soft blues, greens, warm neutrals) — no neon, no pure black backgrounds, no gray-only schemes
    - _Requirements: 12.1, 12.2_

  - [x] 6.5 Build verification — visual hierarchy and accessibility
    - Run `npm run build` from `web/` directory — must exit with code 0
    - Run `npm run lint` from `web/` directory — must produce no new warnings
    - _Requirements: 14.1, 14.2_

- [x] 7. Documentation and final build validation
  - [x] 7.1 Create release notes document
    - Create `docs/release-notes/admin-dashboard/mobile-admin-ux-polish.md` summarizing all changes: mobile responsive layouts, owner-friendly labels, confirmation dialog improvements, protected account guardrails, accessibility improvements
    - _Requirements: 13.5 (preserving existing functionality documentation)_

  - [x] 7.2 Final build check and git diff summary
    - Run `npm run build` from `web/` directory — must exit with code 0
    - Run `npm run lint` from `web/` directory — must produce no new warnings
    - Verify git diff contains ONLY changes to files under `web/src/` and `docs/` — zero backend file changes
    - Summarize the changeset: files modified, lines added/removed, requirements coverage
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.6, 14.1, 14.2_

- [x] 8. Checkpoint — Final review
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- No test framework is configured in this project (no vitest, jest, or similar). Per project constraints, no new testing framework will be introduced for this UX polish pass.
- Lint is configured via eslint (`npm run lint`) and must be run after each task group.
- All changes are frontend-only: only files under `web/src/` will be modified (plus one release notes doc).
- The existing CSS approach (plain CSS with custom properties) is preserved — no new UI frameworks.
- `AdminDashboard.jsx` is ~3000 lines. Changes are targeted label/text updates and minor JSX restructuring — no large-scale refactoring or file splitting.
- Each build verification task is a checkpoint to catch regressions early.
- Do NOT deploy — stop after final build validation and git diff summary.

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["1.3", "1.4"] },
    { "id": 2, "tasks": ["1.5"] },
    { "id": 3, "tasks": ["2.1", "2.2"] },
    { "id": 4, "tasks": ["2.3"] },
    { "id": 5, "tasks": ["3.1", "3.3"] },
    { "id": 6, "tasks": ["3.2", "3.4", "3.5"] },
    { "id": 7, "tasks": ["3.6"] },
    { "id": 8, "tasks": ["4.1"] },
    { "id": 9, "tasks": ["4.2", "4.3"] },
    { "id": 10, "tasks": ["4.4"] },
    { "id": 11, "tasks": ["5.1"] },
    { "id": 12, "tasks": ["5.2"] },
    { "id": 13, "tasks": ["5.3"] },
    { "id": 14, "tasks": ["6.1", "6.3"] },
    { "id": 15, "tasks": ["6.2", "6.4"] },
    { "id": 16, "tasks": ["6.5"] },
    { "id": 17, "tasks": ["7.1", "7.2"] }
  ]
}
```
