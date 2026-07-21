# Phase 1B.4 — Client and Staff Drawer Editor Consolidation

**Date:** 2026-07-21
**Status:** Planning Complete — Awaiting Matthew Approval for AG Implementation
**Type:** Frontend-only (no backend or infrastructure changes)

---

## Objective

Make the right-side profile drawer the single primary place for viewing AND editing
client and staff profiles. Eliminate the duplicate large inline client editor.
Preserve all existing actions, validation, authorization restrictions, and mobile
behavior.

---

## Current Architecture Analysis

### Client Management — DUAL UI PROBLEM

| Concern | Current State |
|---------|--------------|
| Read-only view | ClientDetailDrawer (portal-based right-side drawer) |
| Edit form | Large inline form at top of Client Management tab |
| Trigger | "Edit Profile" in drawer calls `handleEditClient()`, closes drawer, populates inline form |
| Unsaved-change protection | ❌ None — Cancel instantly resets form |
| State synchronization | `editingClientId` controls inline form visibility |
| User experience | Drawer closes → page scrolls to top → inline form appears |

### Staff Management — TARGET PATTERN

| Concern | Current State |
|---------|--------------|
| Read-only view | Staff drawer in read-only mode (`isStaffEditMode === false`) |
| Edit form | Same drawer switches to edit mode (`isStaffEditMode === true`) |
| Trigger | "Edit Profile" button inside drawer sets `isStaffEditMode = true` |
| Unsaved-change protection | ✅ `closeStaffDrawer()` compares against `initialFormValues` |
| User experience | Single drawer, smooth transition, no page jump |

### Conclusion
Client editing should adopt the Staff pattern: edit within the same drawer, with
unsaved-change protection, without closing and reopening a separate UI.

---

## Field and Action Mapping

### Client Profile Fields

| Field | Current Location | Target Drawer Location | API Support | Notes |
|-------|-----------------|----------------------|-------------|-------|
| display_name | Inline form | Edit mode section | ✅ PATCH /admin/clients/:id | Required |
| email | Inline form (read-only when editing) | Edit mode section (read-only) | ✅ | Cannot change once created |
| phone | Inline form | Edit mode section | ✅ | Optional |
| address | Inline form (textarea) | Edit mode section | ✅ | Optional |
| emergency_contact | Inline form | Edit mode section | ✅ | Optional |
| notes | Inline form (textarea) | Edit mode section | ✅ | Internal |
| creation_mode | Inline form (new only) | Create mode section | ✅ POST /admin/clients | Onboard vs profile-only |
| send_invite | Inline form (new only) | Create mode section | ✅ | With onboard mode |
| pet_names_summary | View only in drawer | View mode section | ✅ GET /admin/clients | Read-only |
| pet list (PET# records) | View only in drawer | View mode section | ✅ GET /admin/pets?clientId | Read-only |
| cognito_status | View in drawer | View mode section | ✅ | Read-only |
| is_active | Derived from actions | View mode badge | ✅ | Controlled via enable/disable |

### Client Actions

| Action | Current Location | Target | API | Restrictions |
|--------|-----------------|--------|-----|-------------|
| Edit Profile | Drawer footer | Drawer: transitions to edit mode | — | — |
| Save Changes | Inline form submit | Drawer edit footer | PATCH | Validation |
| Cancel Edit | Inline form button | Drawer edit footer | — | Returns to view mode |
| Create Profile (virtual) | Drawer footer | Drawer: create mode | POST | — |
| Resend Invite | Drawer footer | Drawer: security section | POST | State-gated |
| Send Password Reset | Drawer footer | Drawer: security section | POST | Protected-gated |
| Set Temp Password | Drawer footer | Drawer: security section | POST | Protected-gated |
| Link Login Account | Drawer footer | Drawer: security section | POST | — |
| Turn Off Login | Drawer danger zone | Drawer: danger zone | POST | Protected-gated, confirmation |
| Restore Login | Drawer danger zone | Drawer: danger zone | POST | Confirmation |
| Unlink | Drawer danger zone | Drawer: danger zone | DELETE | Protected-gated, confirmation |
| Delete Profile | Drawer danger zone | Drawer: danger zone | DELETE | Protected-gated, is_active=false, confirmation |

### Staff Profile Fields

| Field | Current Location | Target | API | Notes |
|-------|-----------------|--------|-----|-------|
| display_name | Drawer edit form | Same | ✅ | Required |
| email | Drawer edit form (new only) | Same | ✅ | Read-only when editing |
| phone | Drawer edit form | Same | ✅ | Optional |
| role | Drawer edit form (select) | Same | ✅ | Staff/Admin/Owner |
| is_assignable | Drawer edit form (checkbox) | Same | ✅ | — |
| assignment_color | Drawer edit form (swatches) | Same | ✅ | Calendar visualization |
| notes | Drawer edit form (textarea) | Same | ✅ | Internal |
| creation_mode | Drawer edit form (new only) | Same | ✅ | Onboard vs profile-only |

### Staff Actions (Already in drawer — no change needed)

All staff actions already live in the drawer. Phase 1B.4 only needs to ensure
consistency with the client drawer pattern.

---

## Target Drawer Design

### Recommended Approach: Stacked Sections with Mode Toggle

**Rationale:** Tabs would hide important context (like login status) while editing.
Accordions add unnecessary interaction. Stacked sections with a clear View/Edit
mode toggle is the simplest pattern that:
- Shows all relevant information at once
- Matches the existing staff drawer behavior
- Requires minimal new component infrastructure
- Works on mobile without horizontal space constraints

### Client Drawer Modes

**View Mode** (default when card is clicked):
1. Profile Overview — name, badges, contact
2. Login Identity — account status, cognito state
3. Pets — PET# record list (read-only, existing)
4. Requests — count (existing)
5. Account Security — resend, reset, temp password, link
6. Danger Zone — disable, unlink, delete

**Edit Mode** (triggered by Edit Profile button):
1. Profile Form — display_name, phone, address, emergency_contact, notes
2. Email (read-only display when editing existing)
3. Sticky footer: Save Changes / Cancel

**Create Mode** (triggered by "+ Add New Client"):
1. Creation mode selector (onboard / profile-only)
2. Full form (email editable)
3. Sticky footer: Create / Cancel

### Staff Drawer Modes (minimal change from current)

Already implements the correct pattern. Phase 1B.4 may:
- Add a View mode overview matching client layout
- Add Account Security and Danger Zone sections matching client
- Keep the existing edit form as-is

---

## Backend Impact Assessment: NONE

| Capability | API Status | Phase 1B.4 Change |
|-----------|-----------|-------------------|
| Get client list | ✅ GET /admin/clients | No change |
| Update client | ✅ PATCH /admin/clients/:id | No change |
| Create client | ✅ POST /admin/clients | No change |
| Onboard client | ✅ POST /admin/clients/onboard | No change |
| Disable/enable client | ✅ POST /admin/clients/:id/disable | No change |
| Get pets | ✅ GET /admin/pets?clientId | No change |
| Update staff | ✅ PATCH /admin/staff/:id | No change |
| All security actions | ✅ Existing endpoints | No change |

**Phase 1B.4 is entirely frontend-only.** No new API endpoints required. No backend
changes needed. All current save/update/create handlers use existing API client
functions.

---

## Testing Strategy

### Component Tests (Vitest + React Testing Library)

| # | Test | Validates |
|---|------|-----------|
| 1 | Card click opens View mode | Drawer state |
| 2 | View mode shows all read-only sections | Content |
| 3 | Edit Profile transitions to Edit mode | Mode toggle |
| 4 | Edit mode shows form with pre-populated values | Form state |
| 5 | Cancel returns to View mode | Mode transition |
| 6 | Cancel after changes prompts confirmation | Unsaved protection |
| 7 | Save validates required fields | Validation |
| 8 | Successful save returns to View mode | Lifecycle |
| 9 | Sticky footer visible in Edit mode | Layout |
| 10 | Protected-account edit restrictions | Authorization |
| 11 | Self-account restrictions | Authorization |
| 12 | Orphaned-identity restrictions | Authorization |
| 13 | Destructive actions require confirmation | Safety |
| 14 | Focus remains in drawer during mode transitions | Accessibility |
| 15 | Close with unsaved changes prompts | UX |
| 16 | Client form fields render correctly | Content |
| 17 | Staff form fields render correctly | Content |
| 18 | No duplicate legacy editor accessible | Cleanup |
| 19 | Mobile sheet classes remain | Responsive |
| 20 | No horizontal overflow | Responsive |
| 21 | "+ Add New Client" opens create mode in drawer | Create path |

### Manual Browser Tests

1. Desktop drawer width and edit-form scrolling
2. Mobile bottom-sheet during editing
3. Keyboard navigation through form fields
4. Sticky Save/Cancel footer reachability
5. No horizontal overflow on mobile
6. iPhone safe-area behavior
7. No production records modified during testing

---

## Implementation Sequence

| Phase | Scope | Likely Files | Depends On |
|-------|-------|-------------|-----------|
| 1B.4A | Client drawer View/Edit mode state + edit form | ClientDetailDrawer.jsx, AdminDashboard.jsx | — |
| 1B.4B | Client unsaved-change protection + validation | ClientDetailDrawer.jsx | 1B.4A |
| 1B.4C | Client action/guardrail preservation in drawer | ClientDetailDrawer.jsx, AdminDashboard.jsx | 1B.4A |
| 1B.4D | Remove/retire duplicate inline client editor | AdminDashboard.jsx | 1B.4A-C |
| 1B.4E | "+ Add New Client" opens drawer in create mode | AdminDashboard.jsx, ClientDetailDrawer.jsx | 1B.4D |
| 1B.4F | Staff drawer alignment (add View mode overview if needed) | AdminDashboard.jsx | — |
| 1B.4G | Responsive and accessibility polish | Admin.css, drawers | 1B.4A-F |
| 1B.4H | Component tests | tests/*.test.jsx | 1B.4A-G |
| 1B.4I | Build validation and Kiro review | — | 1B.4H |
| 1B.4J | Production deployment approval + manual smoke | — | 1B.4I |

---

## Approval Gates

| Gate | Approver | Requires |
|------|----------|----------|
| AG local implementation | Matthew (approving this plan) | — |
| Kiro implementation review | Kiro | Tests pass, build succeeds |
| Production frontend deployment | Matthew | Review + approval |
| Authenticated manual smoke | Matthew | Post-deployment browser validation |

**No backend or Terraform plan required.**

---

## Explicit Exclusions

- ❌ No backend code changes
- ❌ No new API endpoints
- ❌ No Terraform or infrastructure changes
- ❌ No pet create/edit/delete/archive capability (remains read-only)
- ❌ No production test-data creation
- ❌ No remediation
- ❌ No second-tenant creation
- ❌ No Cognito schema changes
- ❌ No Stripe, Google Calendar, or mobile distribution changes
- ❌ Pet editing is deferred (separate Phase 1B.5 if needed)
