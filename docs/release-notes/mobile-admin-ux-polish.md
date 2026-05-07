# Mobile Admin UX Polish

## Summary
Frontend-only improvements to the Tog & Dogs operations portal for mobile usability, owner-friendly language, visual polish, and accessibility. No backend, API, database, or authentication changes.

## Changes

### 1. Mobile Layout Improvements
- Admin Dashboard stat cards stack single-column on phones (≤480px), two-column on tablets
- Request List converts from table rows to stacked cards on mobile
- Filter panel collapses behind a toggle button on mobile with active filter count badge
- Scheduler shows a vertical list view on mobile instead of wide timeline
- All interactive elements have 44×44px minimum tap targets on mobile
- Header/nav stacks vertically on mobile without label overlap

### 2. Record Modal Mobile Improvements
- All modals (decision, bulk confirm, purge, CareCard) expand to full-screen on mobile
- Scroll lock prevents background page scrolling when modals are open (iOS Safari compatible)
- Close button is sticky at top-right with 44×44px tap target
- Form fields and action buttons stack vertically with adequate spacing
- CareCard tabs are horizontally scrollable with touch support

### 3. Staff/Client Management Wording
- "Role" → "Access Level"
- "Disable user" → "Turn Off Login Access"
- "Enable user" → "Restore Login Access"
- "Set Temp Pass" → "Set Temporary Password"
- "Send Reset" → "Send Password Reset Email"
- All references to "Cognito" and "User Pool" removed from user-facing text
- Forms restructured into "Login Identity" and "Profile Details" sections with helper text
- Staff and client grids collapse to single-column cards on mobile

### 4. Confirmation Dialog Improvements
- All window.confirm() prompts replaced with in-app modal dialogs
- Each dialog names the affected person and explains the consequence in plain language
- Destructive actions use distinct visual styling (dashed border, bold text)
- Protected account guardrails prevent accidental modification of admin/owner accounts
- "Protected Platform Admin" badge displayed on protected accounts
- Title attributes explain why disabled buttons are blocked

### 5. Status Label Improvements
- "Needs M&G" → "Needs Meet & Greet"
- "Quote Needed" → "Needs Price Quote"
- "Quoted" → "Price Quote Sent"
- "Booked" → "Approved / Ready to Schedule"
- "Scheduled" → "Scheduled with Staff"
- "Completed" → "Visit Completed"
- "Archived" → "Saved for Records"
- "Deleted" → "Trash"
- Sidebar filter labels updated to match
- Unknown statuses display as title case with spaces (fallback)
- All backend status values remain unchanged — labels are display-only

### 6. Visual Hierarchy & Accessibility
- Button hierarchy: primary (filled), secondary (outlined), destructive (dashed border + bold)
- Focus indicators (`:focus-visible`) on all interactive elements with 3px outline
- Text contrast improved: `--text-muted` darkened to meet WCAG AA 4.5:1 ratio
- Minimum 14px font size enforced globally
- Border-radius normalized to CSS custom properties
- Shadows use warm tones instead of pure black
- Mobile cards hide checkbox and staff columns to reduce clutter

## Known Behavior Notes
- Bulk selection checkboxes are hidden on mobile (≤480px) — bulk operations are a desktop workflow
- Staff assignment column is hidden on mobile cards — accessible by tapping into record detail
- `handleDisconnectGoogle` and `handleProcessCancellation` still use browser confirm dialogs (not staff/client actions)
- 20 pre-existing lint issues remain (unused vars, React hooks warnings) — not introduced by this feature

## Files Modified
- `web/src/Admin.css` — Mobile breakpoints, card layouts, button hierarchy, metadata hiding
- `web/src/App.css` — Mobile header/nav compact layout
- `web/src/Portal.css` — CareCard full-screen mobile modal
- `web/src/index.css` — Focus indicators, contrast fixes, typography
- `web/src/components/AdminDashboard.jsx` — Labels, field grouping, confirmation dialogs, protected accounts
- `web/src/components/CareCard.jsx` — Scroll lock
- `web/src/components/MasterScheduler.jsx` — Mobile list layout

## What Was NOT Changed
- No backend Lambda functions, API Gateway endpoints, or Step Functions
- No DynamoDB schema, indexes, or access patterns
- No Cognito User Pool configuration or authentication flow
- No RBAC permission boundaries
- No new dependencies added
- No deployment performed
