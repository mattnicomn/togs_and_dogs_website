# Release 8T: Mobile Visit Status Workflow

**Status:** Planning
**Priority:** High (enables staff to mark visits complete from their phone)
**Risk to Production:** Low (reuses existing review endpoint; staff role already permitted)
**Terraform Required:** No
**Backend Changes:** Minimal (see Section 6 — may need one small addition)
**Scope:** Mobile staff action buttons + optional backend visit-status metadata

---

## 1. Purpose

Allow staff to update visit status from the mobile app: mark a visit as arrived, in-progress, or completed. This closes the operational loop — Ryan assigns via mobile, staff completes via mobile.

---

## 2. Current State

### What Staff Can Do Now (Mobile)

| Action | Status |
|--------|--------|
| Login as staff | ✅ |
| View Today/Upcoming schedule | ✅ |
| View booking detail (client, pet, care instructions) | ✅ |
| **Mark visit as arrived/in-progress/completed** | ❌ Not available |
| Add visit notes | ❌ Not available |
| Upload photos | ❌ Not available |

### Backend Capability Analysis

| Endpoint | Can Staff Call It? | Supports COMPLETED? |
|----------|-------------------|---------------------|
| `POST /admin/review` | ✅ Yes (role check allows `staff`) | ✅ Yes — `COMPLETED` is not in the sensitive-status block |
| Status transition `ASSIGNED → COMPLETED` | ✅ Valid in `REQUEST_TRANSITIONS` | ✅ |
| `IN_PROGRESS` status | ⚠️ Recognized by workflow detection but NOT in `REQUEST_TRANSITIONS` | Missing |

### Key Finding

**Staff CAN already transition ASSIGNED → COMPLETED** using the existing `POST /admin/review` endpoint. The backend:
1. Allows `staff` role (line 50: `role not in ['owner', 'admin', 'staff']` — staff is permitted)
2. Does NOT block `COMPLETED` in the sensitive-status guard (line 76 only blocks APPROVED, BOOKED, DECLINED, CANCELLED, ARCHIVED, DELETED)
3. Has `ASSIGNED → COMPLETED` as a valid transition in `REQUEST_TRANSITIONS`

**However:** There is NO `IN_PROGRESS` or `ARRIVED` in the formal transition map. Adding these would require a small backend update.

---

## 3. Recommended Staff Visit Actions

### MVP (Release 8T — No Backend Changes Needed)

| Action | Status Transition | Backend Support |
|--------|-------------------|-----------------|
| **Mark Completed** | ASSIGNED → COMPLETED | ✅ Already works via `POST /admin/review` |

This is the safest first step: one button, one transition, using an existing endpoint that staff are already authorized to call.

### Phase 2 (Requires Small Backend Addition — Separate Approval)

| Action | Status Transition | Backend Support |
|--------|-------------------|-----------------|
| Mark Arrived | ASSIGNED → IN_PROGRESS | ❌ `IN_PROGRESS` not in transition map |
| Mark In Progress | ASSIGNED → IN_PROGRESS | ❌ Same |
| Add Visit Notes | Updates `visit_notes` field | ❌ No endpoint for note-only update from staff |

---

## 4. MVP Scope: Mark Completed Only

### What "Mark Completed" Does

1. Staff taps "Mark Completed" on an ASSIGNED visit in their schedule detail
2. Confirmation modal: "Mark this visit as completed?"
3. On confirm: calls `POST /admin/review` with `{ request_id, client_id, status: "COMPLETED" }`
4. Backend transitions REQ to COMPLETED, cascades to JOB(s)
5. Success: toast + refresh schedule
6. Visit moves out of "Today" list (completed visits don't show in active schedule)

### Side Effects (Handled by Backend)

| Side Effect | What Happens | Safe? |
|-------------|-------------|-------|
| Notification | No notification configured for COMPLETED event | ✅ No email sent |
| Google Calendar | No calendar action for COMPLETED | ✅ Event stays on calendar |
| Cascade | `cascade_status_to_job` updates child JOBs to COMPLETED | ✅ |
| Audit log | Written by review handler | ✅ |

**No notifications fire for COMPLETED.** The system only emails on approval, assignment, and cancellation. Marking complete is silent — exactly what we want.

### Role Safety

| Check | Result |
|-------|--------|
| Staff can call `/admin/review` | ✅ Allowed (role check passes) |
| Staff can set `COMPLETED` | ✅ Not in sensitive-status block |
| Staff can only complete their OWN visits | ⚠️ Not enforced server-side — see mitigation below |

### Ownership Enforcement (Mobile-Side)

The backend does NOT verify that the calling staff user is the assigned worker for this specific visit. However:
- The mobile app only shows visits assigned to the logged-in staff (`worker_id` filter)
- The "Mark Completed" button only appears on the staff's own assigned visits
- There is no way in the mobile UI to navigate to someone else's visit

**Risk is very low** because the UI scopes visibility. A backend ownership check could be added in Phase 2 but is not required for MVP.

---

## 5. Deferred Items

| Item | Reason | When |
|------|--------|------|
| **Mark Arrived / In Progress** | `IN_PROGRESS` not in transition map; backend addition needed | 8T Phase 2 or 8U |
| **Visit notes** | No staff-accessible note-update endpoint | 8U |
| **Photo upload** | Requires S3 integration, image compression | Future (9x) |
| **Backend ownership check** | Low risk without it; UI enforces scoping | 8U |
| **Client notification on completion** | Not configured; separate decision | Future |

---

## 6. Backend Gap Assessment

### For MVP (Mark Completed): No Backend Changes Needed

The existing `POST /admin/review` with `status: "COMPLETED"` works for staff. No modifications required.

### For Phase 2 (Mark Arrived / In Progress): Small Backend Addition Required

If Matthew wants `IN_PROGRESS` support later:

1. Add `IN_PROGRESS` to `RequestStatus` enum in `status.py`
2. Add `ASSIGNED → IN_PROGRESS` to `REQUEST_TRANSITIONS`
3. Add `IN_PROGRESS → COMPLETED` to `REQUEST_TRANSITIONS`
4. Optionally add `arrived_at` / `completed_at` timestamp fields to the update

**This is NOT needed for Release 8T MVP.** Document as a follow-up.

---

## 7. Mobile UI Design

### Staff Booking Detail — Action Footer

When a staff user views an ASSIGNED visit detail:

```
┌─────────────────────────────────────┐
│ [Scrollable booking detail content] │
├─────────────────────────────────────┤
│        [✓ Mark Completed]           │  ← Staff action button
└─────────────────────────────────────┘
```

- Button only visible for staff role viewing ASSIGNED visits
- Button NOT visible for admin/owner (they use their own action set)
- Button NOT visible on COMPLETED, CANCELLED, or other terminal statuses
- Green success color, 44px+ touch target

### Confirmation Modal

```
┌─────────────────────────────────────┐
│ Mark Visit Completed?               │
│                                     │
│ This confirms you've finished the   │
│ care visit for Buddy (Jane Smith).  │
│                                     │
│ The visit will be moved to your     │
│ completed history.                  │
│                                     │
│     [Cancel]    [Confirm ✓]         │
└─────────────────────────────────────┘
```

### Anti-Double-Tap

```typescript
const [isMutating, setIsMutating] = useState(false);
// Button disabled during API call
// Only one call can execute at a time
```

### Post-Success

1. Dismiss confirmation modal
2. Show success toast: "Visit marked as completed ✓"
3. Navigate back to schedule list
4. Pull-to-refresh removes the completed visit from Today

---

## 8. Files to Create/Modify

| File | Change | New? |
|------|--------|------|
| `mobile/src/screens/RequestDetailScreen.tsx` | Add "Mark Completed" button for staff + ASSIGNED status | Modified |
| `mobile/src/api/client.ts` | Confirm `reviewRequest()` already exists (it does from 8J) | No change needed |

### Files NOT Changed

- No backend handlers
- No web app files
- No Terraform / AWS
- No status.py (MVP uses existing COMPLETED transition)
- No new components needed (reuse existing ConfirmationModal)

---

## 9. Acceptance Criteria

- [ ] Staff sees "Mark Completed" button on ASSIGNED visit detail
- [ ] Button NOT visible on non-ASSIGNED visits
- [ ] Button NOT visible for admin/owner role
- [ ] Tapping "Mark Completed" shows confirmation modal
- [ ] Confirming calls `POST /admin/review` with `status: "COMPLETED"`
- [ ] Success: toast shown, navigate back to schedule
- [ ] Completed visit no longer appears in Today schedule on refresh
- [ ] Double-tap prevention works (button disabled during call)
- [ ] Network error shows error toast, no crash
- [ ] Admin can see the visit as COMPLETED in web dashboard
- [ ] TypeScript compiles (`npx tsc --noEmit`)
- [ ] App launches in Expo Go without crashes

---

## 10. Validation Checklist

### Staff Account Testing

| # | Test | Expected |
|---|------|----------|
| 1 | Login as staff | Schedule tab with assigned visits |
| 2 | Tap an ASSIGNED visit | Detail screen opens |
| 3 | "Mark Completed" button visible | Green button at bottom |
| 4 | Tap "Mark Completed" | Confirmation modal appears |
| 5 | Tap "Cancel" on modal | Modal dismissed, no change |
| 6 | Tap "Confirm" on modal | Loading → success toast → back to schedule |
| 7 | Visit no longer in Today list | Completed visit removed on refresh |
| 8 | Tap rapidly during loading | Only one API call |
| 9 | Network disconnected → Confirm | Error toast, no crash |

### Admin Verification

| # | Test | Expected |
|---|------|----------|
| 10 | Open web admin → Request List | Visit shows as COMPLETED |
| 11 | Admin detail view | Status is COMPLETED, updated_at reflects staff action time |

### Negative Testing

| # | Test | Expected |
|---|------|----------|
| 12 | Login as admin → view ASSIGNED visit detail | "Mark Completed" button NOT shown (admin uses different actions) |
| 13 | Staff tries to view non-assigned visit | Should not be possible via UI (filter scoping) |

---

## 11. Rollback

- Revert mobile source changes: `git checkout -- mobile/src/`
- No backend changes to revert
- Staff loses the "Mark Completed" button; falls back to web/admin action
- No data corruption risk — COMPLETED is a valid terminal status

---

## 12. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8T: Mobile Visit Status Workflow (Mark Completed).

Mobile app changes only. No backend, web, Terraform, or infrastructure changes.

=== 1. Update mobile/src/screens/RequestDetailScreen.tsx ===

In the staff action footer area (or add one if not present for staff):

a) Detect role from useAuth():
   const { role } = useAuth();
   const isStaff = role === 'staff';

b) Show "Mark Completed" button ONLY when:
   - isStaff === true
   - request.status === 'ASSIGNED' or request.status === 'SCHEDULED' or request.status === 'IN_PROGRESS'

c) Button:
   - Label: "✓ Mark Completed"
   - Style: Green background (COLORS.success), white text, 44px+ height, full width
   - Disabled when isMutating is true

d) onPress → open existing ConfirmationModal:
   title: "Mark Visit Completed?"
   message: `Confirm you've completed the care visit for ${request.pet_name || request.pet_names} (${request.client_name}).`
   onConfirm: handleMarkCompleted

e) handleMarkCompleted:
   setIsMutating(true)
   try {
     await reviewRequest(request.request_id, request.client_id, 'COMPLETED');
     // Success: toast + navigate back
     Alert.alert('Success', 'Visit marked as completed ✓');
     navigation.goBack();
   } catch (error) {
     if (error.message includes 'expired' or 'unauthorized') {
       await logout();
     } else {
       Alert.alert('Error', error.message || 'Failed to update visit status');
     }
   } finally {
     setIsMutating(false);
   }

f) Ensure admin/owner do NOT see this button:
   - The existing admin action footer (Approve, Assign, Change Staff) remains for admin/owner
   - Staff ONLY sees "Mark Completed" — no approve/assign/change buttons

=== 2. No API Client Changes Needed ===

reviewRequest() already exists in mobile/src/api/client.ts (from Release 8J).
It accepts (requestId, clientId, status, reason) — use status 'COMPLETED'.

=== 3. Validation ===

Run: npx tsc --noEmit (in mobile/)
Run: npx expo start --port 8082
Test: Login as staff → open ASSIGNED visit → tap Mark Completed → confirm
Test: Visit disappears from schedule on refresh
Test: Login as admin → same visit shows COMPLETED in web

Do NOT modify backend, web, Terraform, or AWS resources.
Do NOT add IN_PROGRESS or ARRIVED transitions.
Do NOT deploy to App Store.

Return: files changed, TypeScript result, manual test observations.
```

---

## 13. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-8t-mobile-visit-status-workflow-plan.md
git commit -m "docs: plan release 8t mobile visit status workflow"
```
