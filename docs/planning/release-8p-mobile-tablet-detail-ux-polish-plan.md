# Release 8P: Mobile Tablet Layout & Detail UX Polish

**Status:** Planning
**Priority:** Medium (operational readiness polish before Ryan uses daily)
**Risk to Production:** None (mobile-only, no backend changes)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Mobile app layout polish for tablet widths, detail screen spacing, action area clarity

---

## 1. Purpose

Polish the mobile app's tablet experience and detail view readability so Ryan's primary workflow feels operationally ready on both his iPhone and iPad. This is UX refinement — no new features, no new mutations.

---

## 2. Current State (After Release 8O)

| Area | Phone (375-430px) | Tablet (768px+) | Issue? |
|------|-------------------|-----------------|--------|
| Request List | ✅ Looks good | Cards stretch full-width, wasted space | Yes |
| Booking Detail | ✅ Readable | Single column — wide but readable | Minor |
| Schedule | ✅ Cards stack well | Cards stretch full-width | Yes |
| Dashboard | ✅ Single stat card works | Could use 2-column grid | Minor |
| Actions (Approve/Assign) | ✅ Work | Buttons spread too far apart | Minor |
| Empty states | ✅ Centered | Still centered — fine | No |

### Primary Tablet Issue

On iPad (768px+ width), all cards and content stretch to the full available width. This creates long, horizontal cards that are harder to scan than narrower, vertically-stacked content. The web app solves this with `max-width` constraints. The mobile app needs the same.

---

## 3. Recommended Polish Items

### 3.1 Max-Width Content Container for Tablet

Add a reusable `ContentContainer` wrapper that constrains content on wider screens:

```typescript
const { width } = useWindowDimensions();
const isTablet = width >= 768;
const contentMaxWidth = isTablet ? 600 : undefined;
```

Apply to: RequestListScreen, ScheduleScreen, DashboardScreen, RequestDetailScreen.

This centers content and prevents cards from stretching to 768px+.

### 3.2 Dashboard 2-Column Stats Grid on Tablet

Currently the dashboard has a single-column stat card layout. On tablet, show a 2-column grid:

```
Phone:                      Tablet:
[Pending Reviews: 3]        [Pending: 3]  [Needs Assign: 1]
[Needs Assignment: 1]       [Today: 2]    [This Week: 5]
[Today's Visits: 2]
[This Week: 5]
```

Use `useWindowDimensions()` to switch between single and 2-column `flexWrap` layout.

### 3.3 Detail Screen Section Spacing

The `RequestDetailScreen` sections (Client, Pet, Service, Dates, Care, Emergency) need clearer visual separation on tablet where there's more vertical space:

- Add 16px gap between sections (currently may be tighter)
- Add subtle section header styling (uppercase small label, border-bottom)
- Ensure tappable contact rows have ≥44px touch targets on all widths

### 3.4 Persistent Action Footer on Detail Screen

Move the action buttons (Approve, Assign Staff, Change Staff) to a sticky bottom area on the detail screen instead of inline within the scroll content:

```
┌─────────────────────────────────────┐
│ [scrollable content above]          │
├─────────────────────────────────────┤
│ [Assign Staff]  [Change Staff]      │  ← Fixed bottom
└─────────────────────────────────────┘
```

This ensures Ryan always sees the primary action without scrolling to the bottom of a long detail view.

### 3.5 Schedule Section Headers (Today vs Upcoming)

Group schedule visits by date with sticky section headers:

```
── Today (Tue, Jun 10) ──────────────
  [Visit card 1]
  [Visit card 2]

── Tomorrow (Wed, Jun 11) ───────────
  [Visit card 3]

── Thu, Jun 12 ──────────────────────
  [Visit card 4]
```

This is a `SectionList` pattern instead of flat `FlatList`. Makes it easier to scan which visits are today vs upcoming.

### 3.6 Improved Empty States

Customize empty state messages per filter:

| Filter | Current | Improved |
|--------|---------|----------|
| Pending | Generic "Queue is Empty" | "No pending requests to review. ✓" |
| Approved | Generic | "All approved bookings have been assigned." |
| Assigned | Generic | "No assigned visits in this view." |
| All Active | Generic | "No active bookings at this time." |
| Schedule (no visits) | "No Upcoming Visits" | "No visits scheduled for today or this week. Check Requests tab for pending approvals." |

---

## 4. Split-View on Tablet (Deferred)

A true side-by-side split view (list on left, detail on right) would be the ideal tablet experience. However, this adds significant navigation complexity:

- Requires a fundamentally different navigator structure
- Selection state management between panels
- Different back button/gesture behavior

**Recommendation: Defer to Release 8Q or later.** For 8P, the max-width container + 2-column dashboard provides a good tablet experience without restructuring navigation.

---

## 5. Files to Create/Modify

| File | Change | New? |
|------|--------|------|
| `mobile/src/components/ContentContainer.tsx` | Max-width wrapper for tablet | ✅ New |
| `mobile/src/screens/DashboardScreen.tsx` | 2-column stats on tablet, use ContentContainer | Modified |
| `mobile/src/screens/RequestListScreen.tsx` | Use ContentContainer for card width constraint | Modified |
| `mobile/src/screens/ScheduleScreen.tsx` | Section headers by date, ContentContainer | Modified |
| `mobile/src/screens/RequestDetailScreen.tsx` | Sticky action footer, section spacing, ContentContainer | Modified |

### Files NOT Changed

- No backend handlers
- No web app files
- No API client changes
- No Terraform / AWS
- No new navigation structure
- No new npm dependencies

---

## 6. Acceptance Criteria

- [ ] On tablet (768px+), cards and content max out at ~600px centered
- [ ] Dashboard shows 2-column stat grid on tablet
- [ ] Request Detail has clear section headers with spacing
- [ ] Action buttons (Approve/Assign) are in a persistent bottom area on detail screen
- [ ] Schedule groups visits by date with section headers
- [ ] Empty states have contextual messages per filter type
- [ ] Phone layout (375-430px) is unchanged / no regression
- [ ] All tap targets remain ≥44px
- [ ] TypeScript compiles (`npx tsc --noEmit`)
- [ ] App launches in Expo Go without crashes

---

## 7. Validation Checklist

### Local Expo Startup

```bash
cd mobile
npx expo start --port 8082
```

If port 8082 is occupied, use `--port 8083`. Scan QR code with Expo Go on device.

### iPhone (375-430px) Validation

| # | Test | Expected |
|---|------|----------|
| 1 | Request List | Cards fill width, no wasted space |
| 2 | Booking Detail | Sections readable, actions visible |
| 3 | Schedule | Visit cards stack vertically |
| 4 | Dashboard | Stats in single column |
| 5 | Empty state (Assigned filter with 0 results) | Contextual message |

### iPad / Tablet (768px+) Validation

| # | Test | Expected |
|---|------|----------|
| 6 | Request List | Cards max-width ~600px, centered |
| 7 | Booking Detail | Content constrained, sections clear |
| 8 | Schedule | Section headers visible, cards constrained |
| 9 | Dashboard | 2-column stat grid |
| 10 | Actions on detail | Sticky bottom area, clearly visible |
| 11 | Landscape rotation | Layout adapts without overflow |

### Cross-Cutting

| # | Test | Expected |
|---|------|----------|
| 12 | Pull-to-refresh on all list screens | Works on both phone and tablet |
| 13 | Approve action from detail | Confirmation → success (no regression) |
| 14 | Assign action from detail | Staff picker → confirm → success |
| 15 | Navigate back (swipe/button) | Returns to list on both devices |

---

## 8. Rollback

- Revert mobile source changes: `git checkout -- mobile/src/`
- No backend or production impact
- App reverts to Release 8O layout (functional but less polished on tablet)
- No data changes to revert

---

## 9. ContentContainer Implementation Pattern

```typescript
// mobile/src/components/ContentContainer.tsx
import React from 'react';
import { View, useWindowDimensions, StyleSheet } from 'react-native';

interface Props {
  children: React.ReactNode;
  maxWidth?: number;
}

export const ContentContainer: React.FC<Props> = ({ children, maxWidth = 600 }) => {
  const { width } = useWindowDimensions();
  const isWide = width >= 768;

  return (
    <View style={[styles.container, isWide && { maxWidth, alignSelf: 'center', width: '100%' }]}>
      {children}
    </View>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
});
```

Usage: wrap screen content in `<ContentContainer>...</ContentContainer>`. On phone it's a no-op (full width). On tablet it constrains to 600px centered.

---

## 10. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8P: Mobile Tablet Layout & Detail UX Polish.

Mobile app changes only. No backend, web, Terraform, or infrastructure changes.

=== 1. Create mobile/src/components/ContentContainer.tsx ===

A layout wrapper that constrains content on tablet widths:
- Props: children, maxWidth (default 600)
- Uses useWindowDimensions() to detect width >= 768
- On tablet: applies maxWidth + alignSelf: 'center' + width: '100%'
- On phone: no-op (children render full width)

=== 2. Update mobile/src/screens/DashboardScreen.tsx ===

a) Wrap content in ContentContainer
b) Use useWindowDimensions() to detect tablet
c) On tablet (>= 768px): render stat cards in a 2-column flexWrap row
d) On phone: keep existing single-column layout

=== 3. Update mobile/src/screens/RequestListScreen.tsx ===

a) Wrap the FlatList area in ContentContainer
b) Cards will naturally constrain on tablet
c) No other changes needed

=== 4. Update mobile/src/screens/ScheduleScreen.tsx ===

a) Wrap content in ContentContainer
b) Convert FlatList to SectionList grouped by date:
   - Section header: formatted date ("Today (Tue, Jun 10)" or "Wed, Jun 11")
   - Section items: visit cards for that date
   - "Today" section header has distinct styling (bold, gold accent)
c) Improve empty state message: "No visits scheduled for today or this week. Check Requests tab for pending approvals."

=== 5. Update mobile/src/screens/RequestDetailScreen.tsx ===

a) Wrap scrollable content in ContentContainer
b) Add clearer section headers:
   - Small uppercase label text (e.g., "CLIENT", "PET", "SERVICE", "CARE INSTRUCTIONS")
   - Subtle bottom border on each section header
   - 16px gap between sections
c) Move action buttons to a sticky bottom View (outside ScrollView):
   - Use a View with position at the bottom of the SafeAreaView
   - Show Approve / Assign Staff / Change Staff based on status
   - Style: white background, top border, padding, shadow
d) Ensure the ScrollView has paddingBottom to account for the fixed action bar

=== 6. Update empty states in RequestListScreen ===

Customize the empty state message based on activeFilter:
- PENDING_REVIEW: "No pending requests to review. ✓"
- APPROVED: "All approved bookings have been assigned."
- ASSIGNED: "No assigned visits in this view."
- ALL: "No active bookings at this time."
- COMPLETED: "No completed visits recorded."
- CANCELLED: "No cancelled bookings."

=== 7. Validation ===

Run: npx tsc --noEmit (in mobile/)
Run: npx expo start --port 8082 (or 8083 if occupied)
Test on iPhone: confirm no regression on phone layout
Test on iPad or wide emulator: confirm content is constrained, 2-col stats, section headers
Test: action buttons visible without scrolling on detail screen

Do NOT modify backend, web, Terraform, or AWS resources.
Do NOT deploy to App Store.

Return: files changed, TypeScript result, phone/tablet test observations.
```

---

## 11. Commit Command (Planning Doc Only)

```bash
git add docs/planning/release-8p-mobile-tablet-detail-ux-polish-plan.md
git commit -m "docs: plan release 8p mobile tablet detail ux polish"
```
