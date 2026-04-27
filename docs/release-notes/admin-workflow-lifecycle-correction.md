# Admin Workflow & Lifecycle Correction Release Notes

## Overview
This update implements a more robust and intuitive operational lifecycle for the Tog and Dogs admin portal. It addresses critical bugs in the visit record edit card, enforces operational gating before approval, and enhances the visibility of completed visits.

## Key Changes

### 1. Visit Record Edit Card Improvements
- **Editable Vet Notes**: Added a dedicated field for Primary Vet Notes in the Health & Medications section.
- **Editable Emergency Contact**: The Emergency Contact Name and Phone are now fully editable in the Access & Logistics section.
- **Persistence**: All edits to health, logistics, and care instructions now persist correctly to the backend and reload upon save.

### 2. Operational Lifecycle & Visibility
- **New Lifecycle Statuses**: Introduced statuses for `M&G Scheduled`, `M&G Completed`, `Quote Needed`, and `Quote Sent`.
- **Completed Filter**: Added a dedicated "Completed" quick filter in the sidebar for direct review of past visits.
- **Refined "All Active" View**: Updated the primary request list to exclude `Completed`, `Archived`, and `Deleted` records, ensuring it only shows items requiring immediate action.
- **Sidebar Highlighting**: Added visual feedback for the active sidebar filter and dynamic headings to the request list.

### 3. Workflow Gating
- **Pre-Approval Gating**: Enforced strict backend validation preventing records from moving to `Approved` until Meet & Greet is marked completed and Quote requirements are met.
- **Preserved Operational Path**: Maintained the core flow: `Approved` → `Assign Staff` → `Scheduled` → `Completed`. Gating does not interfere with the workflow once a visit is approved.

### 4. Scheduler Improvements
- **Independent Filtering**: The scheduler now uses its own dedicated filter set, hiding the main request list sidebar to prevent UI clutter.
- **Customer/Pet Search**: Added a real-time search input to find specific client or pet records on the scheduler timeline.
- **Execution-Focused Statuses**: Focused the status filter on operational states: `Scheduled`, `In Progress`, `Completed`, `Canceled`, and `Rescheduled`.

## Validation Results
- [x] Primary Vet Notes and Emergency Contact save and persist successfully.
- [x] Moving to `Approved` is blocked if M&G is required but not completed.
- [x] Assigning staff automatically moves `Approved` records to `Scheduled`.
- [x] The `Complete` button successfully sets the canonical `COMPLETED` status.
- [x] Completed records appear in the new filter and are excluded from "All Active".
- [x] Frontend builds successfully with `npm run build`.

## Status Mapping Reference
| UI Label | Backend Status (Canonical) |
| :--- | :--- |
| Needs Review | `PENDING_REVIEW` |
| Needs M&G | `MEET_GREET_REQUIRED` |
| M&G Scheduled | `MG_SCHEDULED` |
| M&G Completed | `MG_COMPLETED` |
| New Request | `READY_FOR_APPROVAL` |
| Quote Needed | `QUOTE_NEEDED` |
| Quoted | `QUOTE_SENT` |
| Approved | `APPROVED` |
| Scheduled | `ASSIGNED` |
| Completed | `COMPLETED` |
| Archived | `ARCHIVED` |
| Deleted | `DELETED` |
