# Release 7H: Admin Request List UI Polish Plan

The goal is to fix the "Dates / Window" column in the Admin Request List so that raw ISO dates (and multi-day date arrays) are formatted in a clean, human-readable manner. 

Currently, `AdminDashboard.jsx` blindly renders `{item.start_date} to {item.end_date}`, which wraps awkwardly, especially for multi-day selected dates.

## Proposed Changes

### 1. `web/src/components/AdminDashboard.jsx`

#### [MODIFY] `AdminDashboard.jsx`
- **Add a `formatDateDisplay(item)` helper function:**
  - **Single Date**: If only `start_date` exists and no multi-day array, format it nicely (e.g. `Jun 9, 2026`).
  - **Selected Dates Array**: If `selected_dates` is present (from Release 7E):
    - Determine if the dates are consecutive.
    - If **consecutive**: Display as a range, e.g. `Jun 9–13, 2026`.
    - If **non-consecutive**: Display as comma-separated short dates or compact chips, e.g. `Jun 9, Jun 11, Jun 13`. If there are many dates, we can limit the display and add a "+X more" chip.
  - **Start/End Date Range**: If `start_date` and `end_date` exist (legacy multi-day), format as a range, e.g. `Jun 9–13, 2026`.
- **Update the Table Cell (Line 3623):**
  - Replace `<span className="small">{item.start_date} {item.end_date ? \`to ${item.end_date}\` : ''}</span>` with the output of `formatDateDisplay(item)`.
  - Ensure the CSS prevents awkward wrapping (e.g., using `white-space: nowrap` or flexible chips).

## Open Questions
- For non-consecutive dates, do you prefer comma-separated text (e.g., "Jun 9, Jun 11") or individual rounded chips for each date?
- Is there a maximum number of individual dates we should show before truncating with "+X more"?

## Verification Plan
### Manual Verification
1. Open the Admin UI Request List.
2. Observe bookings with single dates, multi-day consecutive ranges, and multi-day non-consecutive dates.
3. Confirm the dates do not wrap awkwardly and use friendly "MMM D" formatting.
