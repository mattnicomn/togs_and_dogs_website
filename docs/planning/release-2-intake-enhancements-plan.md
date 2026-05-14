# Release 2: Intake Enhancements — Implementation Plan

**Date:** 2026-05-11  
**Status:** Plan Only — No Implementation Yet  
**Prerequisite:** Release 1 deployed and validated  
**Objective:** Add Preferred Visit Window multi-select and Preferred Sitter selection to the intake form, admin views, and scheduler.

---

## Scope

| Feature | Description |
|---------|-------------|
| Visit Window Multi-Select | Clients can select one or more preferred visit windows (Morning, Midday, Afternoon, Evening, Anytime) |
| Preferred Sitter | Optional field where clients can express a staff preference. Does NOT auto-assign. |
| Admin Integration | Both fields visible in Request List, CareCard, and Scheduler |
| Search/Filter | Scheduler can filter by preferred sitter |

### Explicitly Out of Scope
- Automatic staff assignment from preferred sitter
- Changes to lifecycle/status transitions
- Changes to RBAC or protected account safeguards
- Schema migration or destructive data operations
- Multi-pet structured fields (Release 3)
- Client profile automation (Release 3)

---

## 1. Current State

### Visit Window (IntakeForm.jsx, Step 2)
```jsx
<select value={formData.visit_window}>
  <option value="MORNING">Morning (7 AM - 10 AM)</option>
  <option value="MIDDAY">Midday (11 AM - 2 PM)</option>
  <option value="AFTERNOON">Afternoon (3 PM - 6 PM)</option>
  <option value="EVENING">Evening (7 PM - 10 PM)</option>
  <option value="ANYTIME">Anytime (Flexible)</option>
</select>
```

- Single-select dropdown
- Stored as string: `"MORNING"`, `"ANYTIME"`, etc.
- Displayed in Request List as badge: `item.visit_window || 'ANYTIME'`
- Displayed in CareCard Visit tab: `pet.visit_window || 'ANYTIME'`

### Preferred Sitter
- Does not exist in the current system
- No field on intake form, REQ record, or CareCard

### Staff Assignment
- Admin manually assigns via dropdown in Request List (ASSIGN action)
- Staff list comes from `GET /admin/staff` (DynamoDB + Cognito merge)
- Only `is_assignable !== false && is_active !== false` staff appear in dropdown
- Assignment stored as `worker_id` (email) and `worker_name` (display name)

---

## 2. Target State

### Visit Window → Multi-Select

**Data shape change:**
```
// Before (string):
visit_window: "MORNING"

// After (array of strings):
visit_windows: ["MORNING", "AFTERNOON"]
```

**Backward compatibility:**
- Backend accepts both `visit_window` (string, legacy) and `visit_windows` (array, new)
- Display logic reads `visit_windows` first, falls back to `[visit_window]`
- Existing records with `visit_window` string continue to work without migration

### Preferred Sitter → New Optional Field

**Data shape:**
```
// New field on REQ record:
preferred_sitter: "ryanywork@gmail.com"  // or null/empty
preferred_sitter_name: "Ryan"            // display name for UI
```

**Behavior:**
- Optional field on intake form (Step 2)
- Populated from staff list (only `is_assignable` staff shown)
- Stored on REQ record
- Displayed in admin views as informational badge
- Does NOT trigger auto-assignment
- Does NOT restrict which staff can be assigned
- Admin can assign any staff regardless of client preference

---

## 3. Frontend Changes

### `web/src/components/IntakeForm.jsx`

| Section | Current | Target |
|---------|---------|--------|
| Step 2 — Visit Window | Single `<select>` | Checkbox group (multi-select) |
| Step 2 — Preferred Sitter | Does not exist | Optional `<select>` with staff names |
| Form state | `visit_window: 'ANYTIME'` | `visit_windows: ['ANYTIME']`, `preferred_sitter: ''` |
| Validation | `formData.service_type && formData.start_date` | No change (visit_windows and preferred_sitter are optional) |
| Payload | `visit_window: string` | `visit_windows: string[]`, `preferred_sitter: string`, `preferred_sitter_name: string` |

**Visit Window Multi-Select UI:**
```jsx
// Checkbox group replacing the <select>
const WINDOW_OPTIONS = [
  { value: 'MORNING', label: 'Morning (7–10 AM)' },
  { value: 'MIDDAY', label: 'Midday (11 AM–2 PM)' },
  { value: 'AFTERNOON', label: 'Afternoon (3–6 PM)' },
  { value: 'EVENING', label: 'Evening (7–10 PM)' },
  { value: 'ANYTIME', label: 'Anytime (Flexible)' },
];

// When ANYTIME is selected, clear other selections
// When any specific window is selected, clear ANYTIME
```

**Preferred Sitter UI:**
```jsx
// Optional dropdown — only shown for authenticated clients (VISIT_BOOKING workflow)
// For public intake (CUSTOMER_INTAKE), this field is hidden since new clients
// don't know the staff yet.
<select value={formData.preferred_sitter}>
  <option value="">No preference</option>
  {staffList.filter(s => s.is_assignable).map(s => (
    <option key={s.email} value={s.email}>{s.display_name}</option>
  ))}
</select>
```

**Staff list loading for IntakeForm:**
- For authenticated clients: fetch staff list via a new lightweight public endpoint OR embed assignable staff names in the client session context
- For public intake: field is hidden (no staff list needed)

### `web/src/components/AdminDashboard.jsx`

| Section | Current | Target |
|---------|---------|--------|
| Request List table — Window column | `item.visit_window \|\| 'ANYTIME'` | `(item.visit_windows \|\| [item.visit_window \|\| 'ANYTIME']).join(', ')` |
| Request List table — Staff column | Shows assigned worker only | Show assigned worker + preferred sitter badge if different |

**Preferred Sitter display in list:**
```jsx
// In the staff/assignment column:
{item.preferred_sitter_name && item.preferred_sitter !== item.worker_id && (
  <span className="badge-preferred">Prefers: {item.preferred_sitter_name}</span>
)}
```

### `web/src/components/CareCard.jsx`

| Tab | Current | Target |
|-----|---------|--------|
| Visit tab — Window | `pet.visit_window \|\| 'ANYTIME'` | Display all selected windows as badges |
| Scheduling tab — Staff | Shows assigned worker | Also show preferred sitter (informational) |

### `web/src/components/MasterScheduler.jsx`

| Section | Current | Target |
|---------|---------|--------|
| Filter bar — Staff dropdown | Filters by `worker_id` (assigned) | Add option to filter by `preferred_sitter` |
| Visit card display | Shows assigned staff | Optionally show preferred sitter indicator |

**New filter option:**
```jsx
<select value={filters.staff}>
  <option value="ALL">All Staff</option>
  {staffList.map(s => (
    <option key={s.email} value={s.email}>{s.display_name}</option>
  ))}
  <option value="">Unassigned</option>
  <option value="__PREFERRED__">Has Sitter Preference</option>
</select>
```

When `__PREFERRED__` is selected, filter to items where `preferred_sitter` is non-empty.

---

## 4. Backend Changes

### `src/backend/handlers/intake_handler.py`

| Section | Current | Target |
|---------|---------|--------|
| Record creation | Stores `visit_window` (string) | Also store `visit_windows` (array) and `preferred_sitter`, `preferred_sitter_name` |
| Validation | No validation on visit_window | Accept both `visit_window` (legacy) and `visit_windows` (new) |

```python
# New fields in the item dict:
'visit_windows': body.get('visit_windows') or [body.get('visit_window', 'ANYTIME')],
'preferred_sitter': body.get('preferred_sitter') or None,
'preferred_sitter_name': body.get('preferred_sitter_name') or None,
# Keep legacy field for backward compatibility:
'visit_window': body.get('visit_window', 'ANYTIME'),
```

### `src/backend/handlers/job_handler.py`

| Section | Current | Target |
|---------|---------|--------|
| JOB creation | Copies `visit_window` | Also copy `visit_windows` and `preferred_sitter` |

### `src/backend/handlers/admin_handler.py`

No changes needed. The scan already returns all fields on REQ records.

### `src/backend/handlers/review_handler.py`

No changes needed. Status transitions don't depend on visit_windows or preferred_sitter.

### New: `GET /client/staff-options` (lightweight endpoint)

For authenticated clients to see available sitter names:

```python
# Returns only display_name and email for assignable staff
# No sensitive data (no cognito_sub, no phone, no notes)
# Accessible by 'client' role
```

This could be added to `admin_handler.py` under the `/client/` path prefix, or as a new lightweight handler.

---

## 5. Data Shape Summary

### REQ Record — New Fields

| Field | Type | Required | Default | Notes |
|-------|------|----------|---------|-------|
| `visit_windows` | `List[String]` | No | `["ANYTIME"]` | Array of selected windows |
| `preferred_sitter` | `String` | No | `null` | Staff email (identifier) |
| `preferred_sitter_name` | `String` | No | `null` | Staff display name (for UI) |

### JOB Record — New Fields (copied from REQ on creation)

| Field | Type | Notes |
|-------|------|-------|
| `visit_windows` | `List[String]` | Copied from parent REQ |
| `preferred_sitter` | `String` | Copied from parent REQ |

### Backward Compatibility

- `visit_window` (string) remains on all records for backward compatibility
- Display logic: `item.visit_windows || [item.visit_window || 'ANYTIME']`
- No migration needed for existing records

---

## 6. Preferred Sitter — Behavioral Rules

| Rule | Description |
|------|-------------|
| Optional | Field can be empty/null. No preference = no badge. |
| Informational only | Does NOT auto-assign staff. Does NOT restrict assignment. |
| Visible to admin | Shown as badge in Request List and CareCard. |
| Not enforced | Admin can assign any staff regardless of preference. |
| No notification | No alert if assigned staff differs from preference. |
| Client-facing | Shown in client portal "My Bookings" as "Preferred: [name]". |
| Editable by admin | Admin can clear or change preferred_sitter via CareCard edit. |

### Why No Auto-Assignment

1. Ryan needs full control over scheduling (availability, workload, geography)
2. Client preference is a soft signal, not a hard constraint
3. Auto-assignment would bypass the approval/scheduling workflow
4. Staff availability isn't tracked in the current system

---

## 7. Test Cases

### TC-01: Multi-Select Visit Window — Public Intake

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open intake form (unauthenticated) | Step 2 shows checkbox group for windows |
| 2 | Select Morning + Afternoon | Both checked, ANYTIME unchecked |
| 3 | Select ANYTIME | Morning + Afternoon unchecked, ANYTIME checked |
| 4 | Submit | REQ created with `visit_windows: ["MORNING", "AFTERNOON"]` |
| 5 | View in admin list | Shows "Morning, Afternoon" in window column |

### TC-02: Multi-Select Visit Window — Client Portal

| Step | Action | Expected |
|------|--------|----------|
| 1 | Authenticated client opens request form | Step 2 shows checkboxes + preferred sitter |
| 2 | Select Evening only | `visit_windows: ["EVENING"]` |
| 3 | Submit | REQ created with correct windows |

### TC-03: Preferred Sitter — Client Portal

| Step | Action | Expected |
|------|--------|----------|
| 1 | Authenticated client opens request form | Preferred Sitter dropdown visible |
| 2 | Select "Ryan" | `preferred_sitter: "ryanywork@gmail.com"`, `preferred_sitter_name: "Ryan"` |
| 3 | Submit | REQ created with preferred_sitter fields |
| 4 | View in admin list | "Prefers: Ryan" badge visible |
| 5 | Admin assigns different staff | Assignment succeeds (no restriction) |
| 6 | View in admin list | Shows assigned staff + "Prefers: Ryan" badge |

### TC-04: Preferred Sitter — Public Intake (Hidden)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open intake form (unauthenticated) | Preferred Sitter field NOT shown |
| 2 | Submit | REQ created with `preferred_sitter: null` |

### TC-05: Backward Compatibility

| Step | Action | Expected |
|------|--------|----------|
| 1 | Existing record with `visit_window: "MORNING"` (no `visit_windows`) | Displays "Morning" correctly |
| 2 | New record with `visit_windows: ["MORNING", "EVENING"]` | Displays "Morning, Evening" |
| 3 | Admin opens CareCard for old record | Shows single window correctly |

### TC-06: Scheduler Filter by Preferred Sitter

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open MasterScheduler | Staff filter shows "Has Sitter Preference" option |
| 2 | Select "Has Sitter Preference" | Shows only records with non-empty preferred_sitter |
| 3 | Select specific staff name | Shows records assigned to that staff (existing behavior) |

### TC-07: CareCard Display

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open CareCard for record with multi-window | Visit tab shows all selected windows |
| 2 | Open CareCard for record with preferred sitter | Scheduling tab shows "Client Prefers: [name]" |
| 3 | Admin edits CareCard | Can clear/change preferred_sitter |

---

## 8. Risks and Rollback

### Low Risk

1. **Backward compatibility** — `visit_window` string field preserved. Display logic falls back gracefully. No migration needed.
2. **Optional fields** — Both new fields are optional. Existing records unaffected.
3. **No lifecycle changes** — Status transitions, cascade, RBAC all unchanged.

### Medium Risk

4. **Staff list endpoint for clients** — New endpoint exposes staff display names to authenticated clients. Mitigation: only return `display_name` and `email` for `is_assignable` staff. No sensitive data.

### Rollback

- Revert frontend changes → checkboxes revert to single select, preferred sitter field disappears
- Backend continues to accept both `visit_window` and `visit_windows` (no breaking change)
- Records created with `visit_windows` array still display correctly via fallback logic
- No data cleanup needed

---

## 9. Implementation Order

### Step 1: Backend — Accept New Fields (intake_handler.py)

Add `visit_windows` and `preferred_sitter` to the REQ record creation. Keep `visit_window` for backward compatibility.

### Step 2: Backend — Copy to JOB (job_handler.py)

Copy `visit_windows` and `preferred_sitter` to JOB record on creation.

### Step 3: Backend — Client Staff Options Endpoint

Add lightweight `GET /client/staff-options` returning assignable staff names for the intake form dropdown.

### Step 4: Frontend — IntakeForm Multi-Select

Replace visit_window `<select>` with checkbox group. Add ANYTIME mutual exclusion logic.

### Step 5: Frontend — IntakeForm Preferred Sitter

Add optional preferred sitter dropdown (only for authenticated clients). Load staff options from new endpoint.

### Step 6: Frontend — AdminDashboard Display

Update Request List window column to show multi-window. Add preferred sitter badge.

### Step 7: Frontend — CareCard Display

Update Visit tab and Scheduling tab to show new fields.

### Step 8: Frontend — MasterScheduler Filter

Add "Has Sitter Preference" filter option.

### Step 9: Validation

- npm build
- Python compile check
- Manual test all 7 test case groups
- Verify backward compatibility with existing records

---

## 10. Files to Change

| File | Changes |
|------|---------|
| `web/src/components/IntakeForm.jsx` | Multi-select checkboxes, preferred sitter dropdown, staff loading |
| `web/src/components/IntakeForm.css` | Checkbox group styling |
| `web/src/components/AdminDashboard.jsx` | Window column display, preferred sitter badge |
| `web/src/components/CareCard.jsx` | Visit tab multi-window, scheduling tab preferred sitter |
| `web/src/components/MasterScheduler.jsx` | Preferred sitter filter option |
| `web/src/api/client.js` | New `getStaffOptions()` API call |
| `src/backend/handlers/intake_handler.py` | Accept and store new fields |
| `src/backend/handlers/job_handler.py` | Copy new fields to JOB |
| `src/backend/handlers/admin_handler.py` | New `/client/staff-options` endpoint |

**Total:** 9 files (6 frontend, 3 backend)  
**Estimated effort:** ~200 lines frontend, ~40 lines backend  
**Risk level:** Low (all additive, backward compatible, no lifecycle changes)
