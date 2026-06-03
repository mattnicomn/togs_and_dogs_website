# Release 8M: Mobile Admin Assignment & Scheduling Actions

**Status:** Planning
**Priority:** High (enables Ryan's primary phone workflow: approve → assign → manage)
**Risk to Production:** Low (reuses existing backend endpoints, confirmation-gated)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Mobile app — staff assignment, reassignment, and schedule management actions

---

## 1. Purpose

Give Ryan the ability to assign and reassign staff from his phone. After Release 8J (approve) and 8L (schedule visibility), the critical missing action is staff assignment. Without it, Ryan must switch to the web app every time a booking is approved.

---

## 2. Current Mobile Action State

| Action | Status | Release |
|--------|--------|---------|
| View requests | ✅ Working | 8I |
| Filter by status (including Assigned) | ✅ Working | 8L |
| View today's schedule | ✅ Working | 8L |
| Approve booking | ✅ Working | 8J |
| **Assign staff** | ❌ Not available | **8M (this release)** |
| **Reassign staff** | ❌ Not available | **8M (this release)** |
| Cancel visit | ❌ Not available | 8N (future) |
| Delete / Purge | ❌ Deferred to web | — |

---

## 3. Backend Endpoint (Existing — No Changes)

### `POST /admin/assign`

**Payload:**
```json
{
  "job_id": "job-uuid-here",
  "req_id": "request-uuid-here",
  "client_id": "client-uuid-here",
  "worker_id": "worker-email@example.com",
  "worker_name": "Ryan"
}
```

**Backend side effects (all automatic, server-side):**
1. Updates JOB record status to `ASSIGNED`
2. Updates REQ record with `worker_id` and `worker_name`
3. Creates or updates Google Calendar event for assigned staff
4. Sends `STAFF_ASSIGNED` notification email to staff
5. Sends `VISIT_SCHEDULED` notification email to client
6. Notification dedup prevents duplicates within 5-minute window
7. For multi-day bookings, assignment handler resolves all child JOBs

**Required fields:** `job_id`, `req_id`, `client_id`, `worker_id`

**Resolving `job_id` from the request record:**
- Single-day: `request.job_id`
- Multi-day: `request.job_ids[0]` (assigns first JOB; backend cascades to all if same worker)

**Note:** The web app handles a race condition where `job_id` is null immediately after approval (JOB Lambda still processing). The mobile app should check for this and show a brief "still initializing" message.

---

## 4. Implementation Design

### 4.1 New API Function

Add to `mobile/src/api/client.ts`:

```typescript
export const assignWorker = (
  jobId: string, reqId: string, clientId: string, workerId: string, workerName: string
) => request('/admin/assign', 'POST', {
  job_id: jobId,
  req_id: reqId,
  client_id: clientId,
  worker_id: workerId,
  worker_name: workerName
}, true);
```

### 4.2 Staff Picker Bottom Sheet

A new component that shows the list of assignable staff:

```
┌─────────────────────────────────────┐
│ Assign Staff                    [✕] │
│─────────────────────────────────────│
│ ┌─────────────────────────────────┐ │
│ │ ○ Ryan                          │ │
│ │ ○ Sarah                         │ │
│ │ ○ Mike                          │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [Confirm Assignment]                │
└─────────────────────────────────────┘
```

- Fetches staff via `GET /admin/staff`
- Filters to `is_active === true` and `is_assignable !== false`
- Shows display name for each
- Tap to select (radio-style), then confirm
- Shows currently assigned worker as pre-selected (for reassignment)

### 4.3 Action Buttons on Request Card

Extend the existing `RequestCard` expanded section:

| Request Status | Actions Shown |
|---------------|---------------|
| `PENDING_REVIEW` | [Approve Booking] |
| `APPROVED` | [Assign Staff] |
| `ASSIGNED` / `SCHEDULED` | [Change Staff] |
| `COMPLETED` / `CANCELLED` | No actions |

The "Assign Staff" and "Change Staff" buttons trigger the same flow (staff picker → confirmation → API call). The only difference is the button label and confirmation wording.

### 4.4 Confirmation Flow

```
1. User taps "Assign Staff" or "Change Staff"
2. Staff Picker opens → user selects a worker
3. Confirmation modal: "Assign [Worker Name] to [Pet Name]'s [Service]?"
   - For reassignment: "Change assignment from [Current] to [New]?"
   - Warning: "This will update the Google Calendar and send notifications."
4. User confirms → loading state → API call
5. Success → dismiss modal → refresh request data → show success toast
6. Failure → show error in modal → user can retry or dismiss
```

### 4.5 Anti-Double-Tap & In-Progress Lock

```typescript
const [isMutating, setIsMutating] = useState(false);

// In the assignment handler:
if (isMutating) return; // Prevent re-entry
setIsMutating(true);
try {
  await assignWorker(jobId, reqId, clientId, workerId, workerName);
  // Success handling
} catch (error) {
  // Error handling
} finally {
  setIsMutating(false);
}
```

All action buttons are disabled while `isMutating` is true. The confirmation modal shows a spinner and disables both Confirm and Cancel buttons during the API call.

### 4.6 Post-Success Refresh

After a successful assignment:
1. Dismiss the staff picker and confirmation modals
2. Refresh the current request card data (status should now be ASSIGNED)
3. If on Dashboard: refresh stat counts (Needs Assignment count decreases)
4. If navigating to Schedule after: it will auto-fetch on focus (existing behavior from 8L)

Use the existing `onApproveSuccess` callback pattern — rename/generalize to `onActionSuccess`:

```typescript
interface RequestCardProps {
  request: PetRequest;
  onActionSuccess?: () => void;  // Refresh parent list after any mutation
}
```

### 4.7 Token Refresh / Session Error Handling

Release 8L added `isTokenExpired()` pre-check and silent refresh in the API client. The assignment flow inherits this automatically because it uses the same `request()` function. If the session is truly expired:

1. API call throws "Your session expired. Please sign in again."
2. Catch block calls `await logout()` → navigates to login screen
3. User re-authenticates → returns to their previous position

---

## 5. Multi-Day Assignment Behavior

For multi-day bookings (`is_multi_day: true`):

- The `job_id` or `job_ids[0]` from the parent REQ record is used for the assignment call
- The backend `assignment_handler` resolves all child JOBs linked to the REQ and assigns the same worker to all
- Calendar events are created per-JOB (one per occurrence date)
- Notification dedup ensures only one `STAFF_ASSIGNED` email is sent to the worker

**Mobile app logic:**
```typescript
const jobId = request.job_id || (request.job_ids && request.job_ids[0]);
if (!jobId) {
  // JOB creation still processing — show "try again in a moment" message
  return;
}
```

---

## 6. Guardrails

### Duplicate Prevention

| Risk | Guard |
|------|-------|
| Double-tap assigns twice | `isMutating` state disables button during call |
| Duplicate notification emails | Backend 5-minute dedup window (Release 7F) |
| Duplicate calendar events | Backend uses `google_event_id` for PUT/update |
| Assign same worker twice | Backend handles gracefully (re-assignment overwrites, no duplicate) |

### What Remains Web-Only

| Action | Reason |
|--------|--------|
| Delete / Move to Trash | Destructive — needs full context |
| Purge permanently | Irreversible — typed confirmation, desktop only |
| Bulk operations | Multi-select + complex confirmation |
| Google Calendar OAuth reconnect | Requires browser redirect |
| Data export (Excel) | File download — desktop only |
| Staff/Client creation | Complex forms — desktop friendly |
| Archive | Low urgency — not needed on the go |
| Restore from trash | Recovery action — rare, desktop ok |

---

## 7. Files to Create/Modify

| File | Change | New? |
|------|--------|------|
| `mobile/src/api/client.ts` | Add `assignWorker()` function | Modified |
| `mobile/src/components/StaffPickerSheet.tsx` | Staff selection modal/bottom sheet | ✅ New |
| `mobile/src/components/RequestCard.tsx` | Add "Assign Staff" / "Change Staff" buttons for APPROVED/ASSIGNED status | Modified |
| `mobile/src/hooks/useStaff.ts` | Hook to fetch and cache active staff list | ✅ New |

### Files NOT Changed

- No backend handlers
- No web app files
- No Terraform / AWS
- No DynamoDB schema
- No notification logic
- No Google Calendar logic
- No Cognito configuration

---

## 8. Acceptance Criteria

- [ ] "Assign Staff" button visible on APPROVED request cards (expanded)
- [ ] "Change Staff" button visible on ASSIGNED request cards (expanded)
- [ ] Staff picker shows only active/assignable staff from production API
- [ ] Currently assigned worker is pre-selected on reassignment
- [ ] Confirmation modal shows worker name + warning about calendar/notifications
- [ ] Confirm button disabled during API call (anti-double-tap)
- [ ] Successful assignment refreshes the request card (status → ASSIGNED, shows worker name)
- [ ] JOB-not-ready state shows friendly "try again in a moment" message
- [ ] Session expiry during assignment triggers logout gracefully
- [ ] Network error shows error message in modal (does not crash)
- [ ] No delete/purge/bulk/archive actions available
- [ ] TypeScript compiles without errors (`npx tsc --noEmit`)
- [ ] App launches in Expo Go without crashes

---

## 9. Validation Checklist

### TypeScript
```bash
cd mobile && npx tsc --noEmit
```

### Expo Launch
```bash
cd mobile && npx expo start
```

### Manual Testing (iPhone Expo Go)

| # | Test | Expected |
|---|------|----------|
| 1 | Open an APPROVED request → expand → see "Assign Staff" button | Button renders |
| 2 | Tap "Assign Staff" → staff picker opens | Shows active staff names |
| 3 | Select a worker → confirmation modal appears | Shows "Assign [Name] to [Pet]?" |
| 4 | Tap "Confirm" → loading spinner | Button disabled, spinner shows |
| 5 | Assignment succeeds → modal closes → card refreshes | Status shows ASSIGNED + worker name |
| 6 | Open an ASSIGNED request → expand → see "Change Staff" button | Button renders |
| 7 | Tap "Change Staff" → staff picker shows current worker pre-selected | Pre-selection visible |
| 8 | Select different worker → confirm → success | Worker name updates on card |
| 9 | Disconnect network → tap Assign → error | Error message in modal |
| 10 | Tap Assign button rapidly during loading | Only one API call made |
| 11 | Freshly approved request with no job_id yet | "Still initializing" message shown |
| 12 | Navigate to Schedule after assignment | New assignment visible in today/upcoming |

### Tablet (iPad) Validation

| # | Test | Expected |
|---|------|----------|
| 13 | Staff picker displays well on wider screen | Modal centered, not stretched |
| 14 | Request cards readable on tablet | No cramped or oversized layout |
| 15 | Landscape orientation | Layout adapts (no overflow) |

---

## 10. Rollback

- Revert mobile source changes: `git checkout -- mobile/src/`
- No backend rollback needed — backend is unchanged
- Users fall back to web/PWA for assignment
- No data corruption risk — backend guards prevent invalid states
- App reverts to 8L state (approve-only + read schedule)

---

## 11. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8M: Mobile Admin Assignment & Scheduling Actions.

Mobile app changes only. No backend, web, Terraform, or infrastructure changes.

=== 1. Update mobile/src/api/client.ts ===

Add the assignWorker function:

export const assignWorker = (
  jobId: string, reqId: string, clientId: string, workerId: string, workerName: string
) => request('/admin/assign', 'POST', {
  job_id: jobId,
  req_id: reqId,
  client_id: clientId,
  worker_id: workerId,
  worker_name: workerName
}, true);

=== 2. Create mobile/src/hooks/useStaff.ts ===

A hook that fetches and caches the active staff list:

export const useStaff = () => {
  const [staff, setStaff] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  
  const fetchStaff = async () => {
    setIsLoading(true);
    try {
      const data = await getStaff();
      const list = data.staff || [];
      // Filter to active + assignable only
      setStaff(list.filter(s => s.is_active !== false && s.is_assignable !== false));
    } catch (e) {
      console.warn('Failed to fetch staff', e);
    } finally {
      setIsLoading(false);
    }
  };
  
  return { staff, isLoading, fetchStaff };
};

=== 3. Create mobile/src/components/StaffPickerSheet.tsx ===

A modal/overlay for selecting a staff member:

Props:
  visible: boolean
  currentWorkerId?: string (for pre-selection on reassignment)
  onSelect: (workerId: string, workerName: string) => void
  onCancel: () => void

Behavior:
- On open: fetch staff list (using useStaff hook)
- Show loading spinner while fetching
- Display each staff member as a tappable row with radio indicator
- Currently assigned worker (if any) pre-selected
- "Confirm" button at bottom (disabled until selection made)
- "Cancel" / dismiss button
- 44px min touch targets for each row

Style: modal overlay with white card, rounded corners, brand colors.

=== 4. Update mobile/src/components/RequestCard.tsx ===

Add assignment actions to the expanded card section:

a) After the existing Approve button logic, add:

  For status === 'APPROVED':
    Show "Assign Staff" button (primary color, same style as Approve)
    
  For status in ['ASSIGNED', 'SCHEDULED', 'IN_PROGRESS']:
    Show "Change Staff" button (secondary/outline style)

b) When "Assign Staff" or "Change Staff" is tapped:
  1. Check if job_id exists: const jobId = request.job_id || request.job_ids?.[0]
  2. If no jobId: show inline message "Booking still initializing. Try again shortly."
  3. If jobId exists: open StaffPickerSheet

c) When staff is selected from picker:
  1. Show ConfirmationModal:
     - Title: "Assign Staff?" / "Change Assignment?"
     - Message: "Assign [Worker Name] to [Pet Name]'s [Service Type]? This updates calendar and sends notifications."
     - For change: "Change assignment from [Current Worker] to [New Worker]?"
  2. On confirm: call assignWorker(jobId, reqId, clientId, selectedWorkerId, selectedWorkerName)
  3. On success: dismiss modals, call onActionSuccess()
  4. On error: show error in ConfirmationModal, keep modal open for retry

d) Anti-double-tap: reuse existing isMutating state to disable all action buttons during any API call.

e) Rename onApproveSuccess prop to onActionSuccess (or keep both for backward compat).

=== 5. Validation ===

Run: npx tsc --noEmit (in mobile/)
Run: npx expo start (confirm app launches)
Test: Navigate to an APPROVED request → expand → tap "Assign Staff"
Test: Select a worker → confirm → verify success
Test: Check Schedule tab shows the newly assigned visit
Test: Tap rapidly during loading → only one call made

Do NOT modify backend, web, Terraform, or AWS resources.
Do NOT deploy to App Store.

Return: files changed, TypeScript result, manual test observations.
```

---

## 12. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-8m-mobile-admin-assignment-scheduling-actions-plan.md
git commit -m "docs: plan release 8m mobile admin assignment scheduling actions"
```
