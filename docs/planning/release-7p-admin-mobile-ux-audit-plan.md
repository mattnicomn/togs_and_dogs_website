# Release 7P: Admin/Mobile UX Audit & Polish

**Status:** Planning
**Priority:** Low-Medium (UX quality, not blocking operations)
**Risk to Production:** Very Low (CSS/JSX display-only changes)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Frontend-only — `AdminDashboard.jsx`, `Admin.css`, possibly `MasterScheduler.jsx`

---

## 1. Audit Findings

### 1.1 What's Already Good

The admin portal has solid responsive foundations from prior releases:

| Area | Status |
|------|--------|
| Mobile card layout (request list → stacked cards at ≤480px) | ✅ Implemented |
| 44px minimum tap targets on mobile | ✅ Implemented |
| Full-screen modal on mobile | ✅ Implemented |
| Collapsible filter panel on mobile | ✅ Implemented |
| Mobile scheduler list view | ✅ Implemented |
| Stat cards responsive grid | ✅ Implemented |
| Service type friendly labels | ✅ Implemented (`getServiceLabel()`) |
| Multi-day/selected-date compact display | ✅ Implemented (`formatVisitDates()`) |
| Tooltip with full date list | ✅ Implemented (`getFullVisitDatesList()`) |
| Admin Created badge | ✅ Implemented |
| Offline Client badge | ✅ Implemented |
| Visit window display | ✅ Implemented |
| Preferred sitter badge | ✅ Implemented |
| Bulk actions toolbar | ✅ Implemented |
| Action dropdown menus | ✅ Implemented |

### 1.2 UX Gaps Identified

| # | Issue | Severity | Area |
|---|-------|----------|------|
| 1 | **No "empty state" message for filtered views** — when a filter has 0 results, the table body is just empty with no guidance | Low | Request List |
| 2 | **Visit window badges show raw values** — displays "MORNING" instead of "Morning (7–10 AM)" | Low | Request List |
| 3 | **No visual indicator for multi-day bookings in the list** — can't tell at a glance if a booking is multi-day vs single-day without reading the date | Low | Request List |
| 4 | **Action dropdown has no keyboard dismiss** — pressing Escape doesn't close it | Low | Accessibility |
| 5 | **Filter sidebar counts not visible on mobile** — the filter options don't show how many items are in each category | Low | Mobile UX |
| 6 | **Long client/pet names overflow on mobile cards** — names > 30 chars can push layout | Very Low | Mobile UX |
| 7 | **No loading skeleton/placeholder** — data fetch shows blank then pops in | Very Low | UX Polish |
| 8 | **Google integration card text overflow on narrow screens** — technical details can overflow | Very Low | Responsive |
| 9 | **No aria-label on action dropdown trigger** — screen readers don't know what the button does | Low | Accessibility |
| 10 | **Bulk toolbar not sticky on mobile** — scrolls out of view when selecting many items | Very Low | Mobile UX |

### 1.3 Regression Risk from Releases 7E–7O

| Release | Regression Risk | Notes |
|---------|----------------|-------|
| 7E (multi-day JOBs) | None | Backend-only; frontend already handles `selected_dates` display |
| 7E Phase 2B (date picker) | None | New Visit modal only; doesn't affect list view |
| 7E Phase 2C (public intake) | None | IntakeForm only; doesn't affect admin |
| 7F (notification dedup) | None | Backend-only |
| 7N (policy content) | None | Constants file only |
| 7O (no-op) | None | Documentation only |

**No regressions detected.** The admin portal is stable.

---

## 2. Recommended Release 7P Scope (Small, Safe)

Focus on the **highest-value, lowest-risk** items that improve Ryan's daily experience:

### In Scope (Phase 1)

| # | Item | Effort | Risk |
|---|------|--------|------|
| 1 | Empty state messages for filtered views | 15 min | None |
| 2 | Friendly visit window labels (with time ranges) | 15 min | None |
| 3 | Multi-day badge on request list rows | 15 min | None |
| 4 | Escape key closes action dropdown | 10 min | None |
| 5 | aria-label on action dropdown trigger | 5 min | None |

**Total: ~1 hour, frontend-only, zero backend risk.**

### Explicitly Deferred

| Item | Reason |
|------|--------|
| Filter sidebar counts on mobile | Requires additional API data or client-side counting logic |
| Loading skeleton/placeholder | Nice-to-have, not blocking |
| Bulk toolbar sticky on mobile | CSS complexity, edge cases with scroll lock |
| Google integration card overflow | Already handled at 900px breakpoint; edge case only |
| Long name overflow | Already has `word-wrap: break-word`; only extreme cases |

---

## 3. Detailed Implementation Plan

### 3.1 Empty State Messages

When a filter view has 0 results, show a helpful message instead of blank space:

```jsx
{visibleRecords.length === 0 && !loading && (
  <tr>
    <td colSpan={6} style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text-muted)' }}>
      <p style={{ fontSize: '1.1rem', fontWeight: 600 }}>No records in this view</p>
      <p style={{ fontSize: '0.85rem', marginTop: '8px' }}>
        {statusFilter === 'DATA_ISSUES' ? 'No data integrity issues found.' :
         statusFilter === 'DELETED' ? 'Trash is empty.' :
         statusFilter === 'COMPLETED' ? 'No completed visits yet.' :
         'No records match the current filter.'}
      </p>
    </td>
  </tr>
)}
```

### 3.2 Friendly Visit Window Labels

Update the visit window badge to show human-readable time ranges:

```javascript
const WINDOW_LABELS = {
  'MORNING': 'Morning (7–10 AM)',
  'MIDDAY': 'Midday (11 AM–2 PM)',
  'AFTERNOON': 'Afternoon (3–6 PM)',
  'EVENING': 'Evening (7–10 PM)',
  'ANYTIME': 'Anytime'
};

// In the table row:
<span className="badge-window">
  {(item.visit_windows || [item.visit_window || 'ANYTIME'])
    .map(w => WINDOW_LABELS[w] || w)
    .join(', ')}
</span>
```

### 3.3 Multi-Day Badge

Add a small indicator when a booking has multiple days:

```jsx
{(item.is_multi_day || (item.selected_dates && item.selected_dates.length > 1) || 
  (item.end_date && item.start_date && item.end_date !== item.start_date)) && (
  <span className="badge-multi-day" style={{ 
    fontSize: '0.65rem', fontWeight: 700, 
    background: 'var(--bg-muted)', color: 'var(--text-muted)',
    padding: '1px 6px', borderRadius: '4px', marginLeft: '4px'
  }}>
    Multi-Day
  </span>
)}
```

### 3.4 Escape Key Closes Dropdown

Add keyboard listener to the action menu:

```javascript
useEffect(() => {
  const handleEscape = (e) => {
    if (e.key === 'Escape' && openMenuId) {
      setOpenMenuId(null);
    }
  };
  document.addEventListener('keydown', handleEscape);
  return () => document.removeEventListener('keydown', handleEscape);
}, [openMenuId]);
```

### 3.5 Aria-Label on Dropdown Trigger

```jsx
<button 
  className="dropdown-trigger"
  aria-label={`Actions for ${item.pet_names || item.client_name || 'this record'}`}
  aria-expanded={openMenuId === getRecordKey(item)}
  onClick={() => setOpenMenuId(openMenuId === getRecordKey(item) ? null : getRecordKey(item))}
>
```

---

## 4. Files Affected

| File | Change |
|------|--------|
| `web/src/components/AdminDashboard.jsx` | Empty states, window labels, multi-day badge, escape handler, aria-labels |
| `web/src/Admin.css` | `.badge-multi-day` style (optional — can be inline) |

### Files NOT Changed

- No backend files
- No Terraform
- No API client
- No IntakeForm
- No CareCard
- No MasterScheduler (already has mobile list view)

---

## 5. Acceptance Criteria

- [ ] Filtered views with 0 results show a contextual empty state message
- [ ] Visit window badges show friendly labels with time ranges (e.g., "Morning (7–10 AM)")
- [ ] Multi-day bookings show a "Multi-Day" badge in the request list
- [ ] Pressing Escape closes the action dropdown menu
- [ ] Action dropdown trigger has an `aria-label` describing the record
- [ ] `npm run build` passes
- [ ] No backend, Terraform, or API changes
- [ ] Existing request list behavior unchanged for single-day bookings
- [ ] Mobile card layout still works correctly at 480px and below

---

## 6. Validation Plan

### Manual Testing

| # | Test | Expected |
|---|------|----------|
| 1 | Set filter to "Completed" with no completed records | Empty state message: "No completed visits yet." |
| 2 | Set filter to "Trash" with no trashed records | Empty state message: "Trash is empty." |
| 3 | View a booking with `visit_windows: ["MORNING"]` | Badge shows "Morning (7–10 AM)" |
| 4 | View a multi-day booking | "Multi-Day" badge visible next to date |
| 5 | Open action dropdown, press Escape | Dropdown closes |
| 6 | Tab to action dropdown trigger with screen reader | Announces "Actions for [pet/client name]" |
| 7 | View on 480px viewport | Cards stack correctly, no overflow |
| 8 | `npm run build` | No errors |

### Build Validation

```bash
cd web && npm run build
```

---

## 7. Risks and Rollback

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Empty state message shows when data is still loading | Low | Low | Only show when `!loading` |
| Window label map missing a value | Very Low | None | Fallback to raw value via `|| w` |
| Multi-day badge shows incorrectly | Very Low | None | Checks `is_multi_day` OR `selected_dates.length > 1` OR `end_date != start_date` |
| Escape handler conflicts with modal | Very Low | Low | Only fires when `openMenuId` is set (not modal) |

**Rollback:** Revert `AdminDashboard.jsx` to previous version. Frontend-only, instant via S3 revert + CloudFront invalidation.

---

## 8. Guardrails

- Do NOT modify backend handlers
- Do NOT modify Terraform
- Do NOT modify notification logic
- Do NOT modify the New Visit modal (already polished in 7E Phase 2B)
- Do NOT modify the public intake form
- Do NOT add new dependencies
- Do NOT change data fetching logic or API calls
- Keep all changes display/cosmetic only

---

## 9. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 7P: Admin UX Polish (frontend-only).

Changes in web/src/components/AdminDashboard.jsx only.

=== 1. Empty State Messages ===

In the request list table tbody, after the visibleRecords.map() block,
add an empty state row when visibleRecords.length === 0 && !loading:

  {visibleRecords.length === 0 && !loading && (
    <tr>
      <td colSpan={6} style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text-muted)' }}>
        <p style={{ fontSize: '1.1rem', fontWeight: 600, margin: 0 }}>No records in this view</p>
        <p style={{ fontSize: '0.85rem', marginTop: '8px', margin: '8px 0 0' }}>
          {statusFilter === 'DATA_ISSUES' ? 'No data integrity issues found. ✓' :
           statusFilter === 'DELETED' || statusFilter === 'TRASH' ? 'Trash is empty.' :
           statusFilter === 'COMPLETED' ? 'No completed visits yet.' :
           statusFilter === 'CANCELLED' ? 'No cancelled records.' :
           statusFilter === 'ARCHIVED' ? 'No archived records.' :
           'No records match the current filter.'}
        </p>
      </td>
    </tr>
  )}

=== 2. Friendly Visit Window Labels ===

Add a constant near the top of the component (after getServiceLabel):

  const WINDOW_LABELS = {
    'MORNING': 'Morning (7–10 AM)',
    'MIDDAY': 'Midday (11 AM–2 PM)',
    'AFTERNOON': 'Afternoon (3–6 PM)',
    'EVENING': 'Evening (7–10 PM)',
    'ANYTIME': 'Anytime (Flexible)'
  };

Update the visit window badge in the request list row from:
  {(item.visit_windows || [item.visit_window || 'ANYTIME']).join(', ')}
To:
  {(item.visit_windows || [item.visit_window || 'ANYTIME'])
    .map(w => WINDOW_LABELS[w] || w).join(', ')}

=== 3. Multi-Day Badge ===

In the Dates/Window td, after the visit window badge, add:

  {(item.is_multi_day || (item.selected_dates && item.selected_dates.length > 1) ||
    (item.end_date && item.start_date && item.end_date !== item.start_date)) && (
    <span style={{
      fontSize: '0.65rem', fontWeight: 700,
      background: 'var(--bg-muted)', color: 'var(--text-muted)',
      padding: '1px 6px', borderRadius: '4px', marginTop: '2px',
      display: 'inline-block'
    }}>
      Multi-Day
    </span>
  )}

=== 4. Escape Key Closes Dropdown ===

Add a useEffect near the existing click-outside handler:

  useEffect(() => {
    const handleEscape = (e) => {
      if (e.key === 'Escape' && openMenuId) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [openMenuId]);

=== 5. Aria-Label on Dropdown Trigger ===

On the action dropdown trigger button, add:
  aria-label={`Actions for ${item.pet_names || item.client_name || 'this record'}`}
  aria-expanded={openMenuId === getRecordKey(item)}

=== 6. Validation ===

Run: npm run build (in web/)
Confirm no errors.
Do NOT deploy.

Return: files changed, build result, summary of changes.
```

---

## 10. Deployment (After Approval)

```bash
# Build
cd web && npm run build

# Deploy frontend only
aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod
aws cloudfront create-invalidation --distribution-id <DIST_ID> --paths "/*" --profile usmissionhero-website-prod

# Commit
git add web/src/components/AdminDashboard.jsx
git commit -m "feat: Release 7P — admin UX polish (empty states, window labels, multi-day badge, a11y)"
```
