# Release 8N: Mobile Client/Pet Detail View

**Status:** Planning
**Priority:** High (Ryan needs full booking context from his phone)
**Risk to Production:** None (mobile read-only, no backend changes)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Mobile app — dedicated detail screen with full request/client/pet data

---

## 1. Purpose

Give Ryan a full-screen detail view when he taps a booking, showing everything he needs to manage the visit: client contact info, pet care instructions, visit dates/times, assigned staff, address, special notes, and status. Currently, the RequestCard only shows a compact inline expansion with limited fields.

---

## 2. Current State

### What's Available Now

The `RequestCard` component expands inline to show:
- Client name, pet name, service type, dates, status
- Visit window, preferred sitter, worker name (if assigned)
- Special instructions (if present)
- Approve button (for PENDING_REVIEW)
- Assign Staff button (for APPROVED/ASSIGNED, from Release 8M)

### What's Missing

- **Full client contact details:** email, phone, address
- **Pet care instructions:** feeding notes, medication, behavior, vet info
- **Emergency contact information**
- **Timing notes and access instructions**
- **Multi-day occurrence breakdown** (which days, which are done)
- **Scrollable full-screen layout** for long content
- **Quick-access call/text actions** from contact info

### Data Already Returned by Backend

The `GET /admin/requests?status=ALL` endpoint returns the full DynamoDB item for each REQ record. Fields available but not currently displayed in mobile:

| Field | Available? | Currently Shown? |
|-------|-----------|-----------------|
| `client_name` | ✅ | ✅ |
| `client_email` | ✅ | ❌ |
| `client_phone` | ✅ | ❌ |
| `pet_names` / `pet_name` | ✅ | ✅ (partial) |
| `pet_info` | ✅ | ❌ |
| `pets` (structured array) | ✅ | ❌ |
| `vet_info` | ✅ | ❌ |
| `emergency_contact_info` | ✅ | ❌ |
| `service_type` | ✅ | ✅ |
| `start_date` / `end_date` | ✅ | ✅ |
| `selected_dates` | ✅ | ✅ |
| `visit_windows` | ✅ | Partial |
| `details` | ✅ | ❌ |
| `timing_notes` | ✅ | ❌ |
| `worker_name` / `worker_id` | ✅ | ✅ |
| `preferred_sitter_name` | ✅ | ✅ |
| `is_multi_day` / `total_occurrences` | ✅ | ❌ |
| `job_id` / `job_ids` | ✅ | Internal use |
| `status` | ✅ | ✅ |
| `source` | ✅ | ❌ |
| `created_at` | ✅ | ❌ |

**No new endpoints needed.** The data is already in the response — just not rendered.

---

## 3. UX Recommendation: Stack Navigation Detail Screen

### Why a Full Screen (Not a Bigger Inline Expansion)

| Approach | Pros | Cons |
|----------|------|------|
| Inline expansion (current) | No navigation change | Cramped, can't scroll independently, context is lost in a long list |
| Bottom sheet / modal | Overlay feel, quick dismiss | Height-limited on phone, nested scrolling issues |
| **Full-screen detail (recommended)** | Full scrollable area, native navigation, back gesture | Requires stack navigator |

**Recommendation: Add a native stack navigator inside the Requests tab** so tapping a card navigates to a full-screen `RequestDetailScreen`. This is the standard React Native pattern for list → detail flows.

### Navigation Structure Change

```
AdminTabs (bottom tabs)
├── Dashboard
├── Requests
│   └── Stack Navigator
│       ├── RequestListScreen (list)
│       └── RequestDetailScreen (detail) ← NEW
└── Schedule
```

This keeps the bottom tabs visible and uses React Navigation's standard stack push/pop for the detail view. The back gesture (iOS swipe, Android back button) returns to the list.

---

## 4. RequestDetailScreen Layout

```
┌─────────────────────────────────────┐
│ ← Back          Request Detail       │
├─────────────────────────────────────┤
│ [ASSIGNED]           Admin Created   │
│                                      │
│ ── Client ───────────────────────── │
│ 👤 Jane Smith                        │
│ ✉  jane@example.com          [tap]  │
│ 📞 555-123-4567               [tap]  │
│ 📍 123 Oak Lane, Springfield        │
│                                      │
│ ── Pet ──────────────────────────── │
│ 🐾 Buddy (Golden Retriever, 3yr)    │
│                                      │
│ ── Service ──────────────────────── │
│ 30-Minute Walk                       │
│ Window: Morning (7–10 AM)           │
│ Staff: 👤 Ryan                       │
│                                      │
│ ── Dates ────────────────────────── │
│ Jun 10, 11, 12, 2026 (3 days)       │
│ Multi-Day • Day 1 of 3 today        │
│                                      │
│ ── Care Instructions ─────────────  │
│ Feeding: 1 cup kibble, twice daily   │
│ Meds: None                           │
│ Behavior: Pulls on leash, friendly   │
│ Access: Back gate code 1234          │
│                                      │
│ ── Emergency ────────────────────── │
│ Contact: John Smith (spouse)         │
│ Phone: 555-987-6543                  │
│ Vet: Dr. Martinez, Happy Paws       │
│ Vet Phone: 555-111-2222             │
│                                      │
│ ── Notes ────────────────────────── │
│ "Please make sure gate is latched    │
│  when leaving. Dog likes to run."    │
│                                      │
│ ── Actions ──────────────────────── │
│ [Assign Staff] / [Change Staff]      │
│ [Approve] (if pending)               │
├─────────────────────────────────────┤
│ Created: Jun 8, 2026 • ID: abc-123  │
└─────────────────────────────────────┘
```

### Tappable Contact Actions

- Email address: opens device email app (`Linking.openURL('mailto:...')`)
- Phone number: opens phone dialer (`Linking.openURL('tel:...')`)
- Address: opens Maps app (`Linking.openURL('maps:...')` or Google Maps URL)

These use React Native's `Linking` API — no native module required.

---

## 5. Tablet Layout

On iPad/tablet (≥ 768px width), use a split view:
- Left panel: Request list (narrower)
- Right panel: Detail view (wider, scrollable)

This can be achieved with `useWindowDimensions()` — same pattern used in the web's MasterScheduler. For Phase 1, a full-screen detail is sufficient. Split-view is a future tablet enhancement.

---

## 6. Types Update

Expand `PetRequest` to include all detail fields:

```typescript
export interface PetRequest {
  // Existing fields
  request_id: string;
  client_id: string;
  client_name: string;
  pet_name: string;
  service_type: string;
  selected_dates: string[];
  status: string;
  created_at: string;
  
  // Contact fields (for detail view)
  client_email?: string;
  client_phone?: string;
  address?: string;
  
  // Pet structured data
  pets?: PetProfile[];
  pet_names?: string;
  pet_info?: string;
  
  // Vet/Emergency
  vet_info?: { vet_name?: string; clinic_phone?: string };
  emergency_contact_info?: { name?: string; phone?: string };
  
  // Service/scheduling
  visit_window?: string;
  visit_windows?: string[];
  timing_notes?: string;
  details?: string;
  preferred_sitter?: string;
  preferred_sitter_name?: string;
  
  // Assignment
  worker_id?: string;
  worker_name?: string;
  assigned_sitter?: string;
  job_id?: string;
  job_ids?: string[];
  
  // Multi-day
  start_date?: string;
  end_date?: string;
  is_multi_day?: boolean;
  total_occurrences?: number;
  
  // Metadata
  source?: string;
  timeframe?: string;
  special_instructions?: string;
}

export interface PetProfile {
  name: string;
  species?: string;
  breed?: string;
  age?: number;
  feeding_notes?: string;
  medication_notes?: string;
  behavior_notes?: string;
}
```

---

## 7. Files to Create/Modify

| File | Change | New? |
|------|--------|------|
| `mobile/src/screens/RequestDetailScreen.tsx` | Full-screen detail view | ✅ New |
| `mobile/src/navigation/AppNavigator.tsx` | Add stack navigator inside Requests tab | Modified |
| `mobile/src/screens/RequestListScreen.tsx` | Navigate to detail on card tap (instead of inline expand) | Modified |
| `mobile/src/components/RequestCard.tsx` | Remove inline expansion; add onPress to navigate | Modified |
| `mobile/src/types/index.ts` | Expand PetRequest, add PetProfile interface | Modified |

### Files NOT Changed

- No backend handlers
- No web app files
- No Terraform / AWS
- No API endpoints (data already returned)
- No new npm dependencies (Linking, useWindowDimensions are built-in)

---

## 8. Acceptance Criteria

- [ ] Tapping a request card navigates to a full-screen detail view
- [ ] Detail view shows: client name, email, phone, address
- [ ] Detail view shows: pet names, care instructions (feeding, meds, behavior)
- [ ] Detail view shows: service type, visit window, dates, assigned staff
- [ ] Detail view shows: emergency contact and vet info (if present)
- [ ] Detail view shows: notes/details/timing notes
- [ ] Detail view shows: multi-day badge with occurrence count
- [ ] Tapping email opens device email app
- [ ] Tapping phone number opens phone dialer
- [ ] iOS swipe-back returns to request list
- [ ] Android back button returns to request list
- [ ] Action buttons (Approve, Assign) still work from detail screen
- [ ] Missing fields show gracefully (no crash if vet_info is null)
- [ ] Long content scrolls smoothly
- [ ] TypeScript compiles without errors
- [ ] App launches in Expo Go without crashes

---

## 9. Validation Checklist (iPhone Expo Go)

| # | Test | Expected |
|---|------|----------|
| 1 | Tap a request card | Navigates to detail screen with back button |
| 2 | Swipe right (iOS back gesture) | Returns to request list |
| 3 | Client email displayed and tappable | Opens Mail app |
| 4 | Client phone displayed and tappable | Opens Phone dialer |
| 5 | Pet care instructions visible | Feeding, meds, behavior sections |
| 6 | Emergency contact visible | Name + phone (if present on record) |
| 7 | Multi-day booking shows all dates | "Jun 10, 11, 12 (3 days)" |
| 8 | Assigned staff visible | "👤 Ryan" in service section |
| 9 | Record with no pet_info | "No care instructions recorded" (graceful) |
| 10 | Record with no emergency contact | Section hidden or "Not provided" |
| 11 | Long notes text scrolls | No clipping, full content visible |
| 12 | Approve button works from detail | Same confirmation flow as before |
| 13 | Assign Staff button works from detail | Staff picker opens, assignment succeeds |
| 14 | Detail screen on iPad | Layout remains readable (wider card area) |

---

## 10. Rollback

- Revert mobile source changes: `git checkout -- mobile/src/`
- No backend impact — data was always returned, just not rendered
- App reverts to inline-expansion cards (8M behavior)
- No data or API changes to revert

---

## 11. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8N: Mobile Client/Pet Detail View.

Mobile app changes only. No backend, web, Terraform, or infrastructure changes.

=== 1. Update mobile/src/types/index.ts ===

Expand PetRequest to include all fields returned by the admin requests API:
  client_email?, client_phone?, address?,
  pets?: PetProfile[],
  pet_names?, pet_info?,
  vet_info?: { vet_name?: string; clinic_phone?: string },
  emergency_contact_info?: { name?: string; phone?: string },
  visit_window?, visit_windows?: string[],
  timing_notes?, details?,
  start_date?, end_date?,
  is_multi_day?, total_occurrences?,
  source?

Add PetProfile interface:
  { name, species?, breed?, age?, feeding_notes?, medication_notes?, behavior_notes? }

=== 2. Update mobile/src/navigation/AppNavigator.tsx ===

Wrap the Requests tab in a Stack Navigator:

import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { RequestDetailScreen } from '../screens/RequestDetailScreen';

const RequestStack = createNativeStackNavigator();

const RequestStackNavigator = () => (
  <RequestStack.Navigator screenOptions={{ headerShown: false }}>
    <RequestStack.Screen name="RequestList" component={RequestListScreen} />
    <RequestStack.Screen name="RequestDetail" component={RequestDetailScreen} />
  </RequestStack.Navigator>
);

Replace the Requests tab component from RequestListScreen to RequestStackNavigator.

=== 3. Update mobile/src/screens/RequestListScreen.tsx ===

Add navigation:
- import { useNavigation } from '@react-navigation/native';
- Pass onPress to RequestCard that navigates to RequestDetail with the request data:
  onPress={() => navigation.navigate('RequestDetail', { request: item })}

=== 4. Update mobile/src/components/RequestCard.tsx ===

Change from inline expand to navigation:
- Accept an onPress prop: onPress?: () => void
- Remove the expanded state and inline expansion content
- Keep the compact card display (client, pet, service, dates, status, worker)
- Make the entire card a TouchableOpacity that calls onPress
- Remove the Approve/Assign buttons from the card (move to detail screen)

=== 5. Create mobile/src/screens/RequestDetailScreen.tsx ===

A full-screen scrollable detail view:

Structure:
- Header: back button + "Request Detail" title
- Status badge (colored chip)
- Source badge (if admin_created)
- Section: Client (name, email [tappable], phone [tappable], address)
- Section: Pet (names, species/breed/age if pets array exists, care instructions)
- Section: Service (type label, visit window, assigned staff)
- Section: Dates (formatted, multi-day indicator, occurrence count)
- Section: Care Instructions (pet_info, details, timing_notes)
- Section: Emergency (emergency_contact_info, vet_info)
- Section: Actions (Approve for PENDING, Assign/Change for APPROVED/ASSIGNED)
- Footer: created_at timestamp, request_id

Tappable contacts:
  import { Linking } from 'react-native';
  - Email: Linking.openURL(`mailto:${email}`)
  - Phone: Linking.openURL(`tel:${phone}`)

Graceful null handling:
  - If a section has no data, show "Not provided" or hide the section
  - If vet_info is null/undefined, don't render the vet row
  - If pets array is empty, fall back to pet_name/pet_names string

Action buttons:
  - Reuse ConfirmationModal and StaffPickerSheet from 8J/8M
  - After successful action, refresh data (re-fetch or pop navigation)

Style: Use COLORS from theme, consistent card sections with headers,
16px body text, 44px touch targets for actions.

=== 6. Validation ===

Run: npx tsc --noEmit (in mobile/)
Run: npx expo start (confirm app launches)
Test: Tap a request → detail screen opens with full data
Test: Swipe back → returns to list
Test: Tap email → device mail opens
Test: Tap phone → dialer opens
Test: Record with missing fields → no crash
Test: Approve/Assign from detail → still works

Do NOT modify backend, web, Terraform, or AWS resources.
Do NOT deploy to App Store.

Return: files changed, TypeScript result, manual test observations.
```

---

## 12. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-8n-mobile-client-pet-detail-view-plan.md
git commit -m "docs: plan release 8n mobile client pet detail view"
```
