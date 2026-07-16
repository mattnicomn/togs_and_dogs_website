# Phase 1B.1A: Client Management List, Search, and Filters (Pre-Deploy)

**Date:** 2026-07-16
**Status:** Pre-Deploy (awaiting frontend deployment approval)
**Type:** Frontend compatibility enhancement (no backend changes)

---

## Objective

Modernize the Client Management list presentation to use the server-provided `account_status` field from Phase 1A, separate profile state from account state in the visible UI, and add client-side filters.

## Scope

- Use server `account_status` for account labels (no browser-side Cognito inference)
- Separate profile-status badge from account-status badge
- Add client-side filter control (profile and account state filters)
- Preserve existing search behavior (enhanced with address field)
- Preserve all existing client workflows unchanged
- No new backend endpoints or API calls
- No detail drawer (deferred to Phase 1B.1B)
- No account-action redesign

## Files Changed

| File | Change |
|------|--------|
| `web/src/utils/clientManagement.js` | New pure utility module (status labels, search, filter) |
| `web/src/components/AdminDashboard.jsx` | Import utilities, add filter state, replace inline search/filter logic, add dual-badge status display |
| `web/src/Admin.css` | Add profile/account status badge CSS classes |
| `web/tests/clientManagement.test.js` | 52 pure utility tests using Node built-in test runner |

## Account-Status Mapping (Server-Provided)

| `account_status` | Label | CSS Class |
|-----------------|-------|-----------|
| linked_active | Login Active | status-active |
| linked_disabled | Login Disabled | status-disabled |
| invitation_sent | Invitation Pending | status-invited |
| invite_available | Ready to Invite | status-no-login |
| profile_only | Profile Only | status-offline |
| orphaned_identity | Login Needs Repair | status-disabled |
| unlinked | Unlinked | status-no-login |

## Profile-Status Mapping

| `is_active` | Label | CSS Class |
|-------------|-------|-----------|
| true / missing | Active Profile | status-profile-active |
| false | Archived Profile | status-archived |

An archived profile with `account_status=linked_active` displays both badges: "Archived Profile" and "Login Active". It does NOT display "Login Disabled".

## Legacy Fallback

When `account_status` is absent (pre-Phase 1A responses), the utility derives a status from `cognito_sub`, `cognito_status`, and `email`. This fallback is documented as temporary and should be removed after all production responses include `account_status`.

## Search Behavior

Client-side search over already-loaded records:
- display_name, email, phone, notes, pet_names_summary, pet_breeds_summary, address
- Case-insensitive, trims whitespace
- Clear button with accessible label
- Result count shown with `aria-live="polite"`
- No backend request per keystroke

## Filter Definitions

| Value | Label | Logic |
|-------|-------|-------|
| all | All Clients | No filter |
| active_profiles | Active Profiles | `is_active !== false` |
| archived_profiles | Archived Profiles | `is_active === false` |
| linked_active | Login Active | `account_status === 'linked_active'` |
| linked_disabled | Login Disabled | `account_status === 'linked_disabled'` |
| invitation_sent | Invitation Pending | `account_status === 'invitation_sent'` |
| invite_available | Ready to Invite | `account_status === 'invite_available'` |
| profile_only | Profile Only | `account_status === 'profile_only'` |
| orphaned_identity | Login Needs Repair | `account_status === 'orphaned_identity'` |
| unlinked | Unlinked | `account_status === 'unlinked'` |

Search and filter compose together.

## Compatibility Safeguards

- PK, SK, cognito_sub, client_id remain in React state for existing workflows
- Internal identifiers are not rendered in visible DOM
- Existing action handlers receive the original client object unchanged
- No API payload changes
- No new per-client network requests
- No N+1 query behavior
- household_id is accepted but does not replace client_id

## Test Results

- Pure utility tests (node:test): **52 passed, 0 failed**
- Build (vite build): **PASSED**
- Lint baseline: 47 problems (38 errors, 9 warnings)
- Lint candidate: **47 problems (38 errors, 9 warnings)** — zero candidate-only issues

## What Was NOT Changed

- ❌ No backend changes
- ❌ No detail drawer (deferred to Phase 1B.1B)
- ❌ No account-action redesign
- ❌ No create/edit workflow changes
- ❌ No API payload changes
- ❌ No new dependencies added
- ❌ No production deployment

## Next Steps

- Phase 1B.1B: Read-only client detail drawer
- Frontend deployment (requires separate explicit Matthew approval)
