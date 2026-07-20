# Phase 1B.3: Client Pet Inventory and Management Detail UX — Implementation Review

**Date:** 2026-07-20
**Reviewer:** Kiro
**Status:** NEEDS LOCAL CODE CORRECTION

---

## Implementation Commit Reviewed

`fa32ded` — feat: Implement Phase 1B.3 Client Pet Inventory and Management Detail UX

## Files Changed

| File | Change |
|------|--------|
| `web/src/App.jsx` | Add /my-pets route, conditional nav link, session-role detection |
| `web/src/components/MyPets.jsx` | New: client pet listing page with login gate |
| `web/src/components/AdminDashboard.jsx` | Card-click interaction, drawer-action relocation, staff read-only mode |
| `web/src/components/ClientDetailDrawer.jsx` | Enhanced with pet list, action footer, danger zone |
| `web/src/Admin.css` | Mobile bottom-sheet, slideUp animation, responsive breakpoints |
| `web/src/utils/petHelpers.js` | New: sanitizePetDetails/sanitizePetsList utility |
| `web/tests/phase1b3.test.js` | New: 5 tests for petHelpers |

---

## My Pets Assessment: MOSTLY SOUND — 2 ISSUES

### Correct
- `/my-pets` route registered correctly in App.jsx
- Desktop and mobile navigation conditionally show "My Pets" link
- Role-gated: only client/owner/admin see the link
- Uses existing `getClientPets()` API client (no new endpoint)
- No POST/PUT/PATCH/DELETE possible from this page
- Loading, empty, populated, and error states all implemented
- Semantic `<ul>` with `<li>` items for pet grid
- `aria-live="polite"` on the status container
- Sanitizer removes internal pricing/quote fields
- No pagination UI introduced

### Issues

**ISSUE 1 — Duplicated login flow:** MyPets contains a full login form identical to ClientPortal. This is functional but creates maintenance burden and potential session-sync drift. The component manages its own `session` state independently of the App shell's `hasClientSession`. A shared authenticated-client wrapper would be cleaner. **Assessment: Acceptable for bounded first release but document as tech debt.** Not a blocking defect.

**ISSUE 2 — Session-state synchronization:** If a user navigates to /my-pets while already logged in, `checkSession()` fires on mount and correctly detects the session. If the user subsequently logs out (e.g. via the UserProfile component in the header), MyPets' local `session` state remains truthy until the next navigation event causes App.jsx to re-evaluate `hasClientSession`. The "My Pets" nav link disappears (because App.jsx rechecks on `location.pathname` change), but the MyPets page content remains visible until the user navigates away. **Assessment: Low risk (user must actively navigate away), not a security issue (the API will reject unauthenticated requests), but a UX inconsistency. Document as future improvement, not a blocker.**

---

## Session/Navigation Assessment: ACCEPTABLE

- `hasClientSession` is computed from `getEffectiveRole(session)` on every route change
- Logout removes the "My Pets" nav link when the next route change triggers the effect
- Staff and unknown roles do not receive the nav link
- Platform admin users who also have client/owner/admin role correctly see the link

---

## Client-Card Assessment: NEEDS CORRECTION

### Correct
- Card `onClick` opens the client detail drawer via `openClientDetail(c)`
- Enter and Space keyboard activation implemented (`onKeyDown` handler)
- View Details button calls the same `openClientDetail(c)` function
- Selected-card styling (accent border, muted bg) preserved
- Nested action buttons removed from cards — relocated to drawer
- `stopPropagation` on the remaining "View Details" button area

### ISSUE 3 — Nested interactive semantics (BLOCKING)

The card div has `role="button"` and `tabIndex="0"`, making it a single interactive element in the accessibility tree. Inside it, the "View Details" `<button>` is a NESTED interactive control. This violates ARIA's requirement that `role="button"` elements must not contain interactive descendants.

Screen readers will announce the card as a single button. Users will not easily discover or activate the nested button independently. Some assistive technologies may ignore or malfunction with nested interactive controls.

**Required correction:** Remove `role="button"` from the card div. Keep `tabIndex="0"` for focusability. Use a card-group pattern where the primary action area (e.g., an overlay link or a stretched first link) handles activation, while nested buttons remain independently accessible. Alternatively, remove the nested "View Details" button entirely since the card itself performs the same action.

The same issue exists on staff cards.

---

## Client-Drawer Assessment: MOSTLY SOUND — 1 ISSUE

### Correct
- Existing client detail fields preserved
- PET records rendered from `clientPets` prop (name, species, breed, is_active badge)
- Summary fallback still present when no PET records available
- Client ID displayed (moved from card)
- Action handlers passed correctly (onEdit, onExecuteAction, onLinkEmail, onCreateProfile)
- All card actions now available in drawer footer
- Destructive actions in a visually separated "Danger Zone" section
- Protected-profile restrictions enforced (`disabled` + title tooltip)
- Opening the drawer does not mutate a record
- Focus trap and Escape-to-close preserved from Phase 1B.1B

### ISSUE 4 — Stale pet-data race condition (BLOCKING)

`openClientDetail` calls `handleEditClient(client)` which fires `Promise.all(petIds.map(...))` to fetch pets, then calls `setClientPets(results)`. If the user rapidly clicks two different client cards:

1. Click client A → starts fetching A's pets
2. Click client B → clears pets with `setClientPets([])`, starts fetching B's pets, opens drawer for B
3. A's pet fetch resolves → `setClientPets(A's pets)` overwrites B's empty state
4. Drawer now shows client B's details with client A's pet records

**Required correction:** Add a cancellation mechanism. Options:
- Store the current `editingClientId` at fetch time and compare before calling `setClientPets`
- Use an AbortController
- Use a monotonically increasing request counter

---

## Staff-Card and Drawer Assessment: SOUND

### Correct
- Card click opens read-only detail mode via `openStaffDetail(s)`
- Enter and Space activation implemented
- "View Details" button calls same function with stopPropagation
- "+ Add New Staff" opens edit/create mode as before
- Read-only drawer mode (when `isStaffEditMode === false`) shows profile information
- "Edit Profile" transitions to edit mode
- Cancel restores prior values
- Unsaved-change confirmation preserved
- Protected-account restrictions preserved
- Self-account restrictions preserved
- Orphaned-identity restrictions preserved
- All management actions remain available in drawer
- Confirmation workflows unchanged

### Same nested interactive issue as client cards (ISSUE 3 applies here too)

---

## Action-Preservation Assessment: COMPLETE

All previously available actions remain reachable:
- Edit Profile (drawer)
- Resend Invite (drawer, state-gated)
- Send Password Reset (drawer, protected-gated)
- Set Temporary Password (drawer, protected-gated)
- Link Login Account (drawer)
- Turn Off Login Access (drawer danger zone)
- Restore Login Access (drawer danger zone)
- Unlink (drawer danger zone)
- Delete Login Account (drawer danger zone)
- Delete Profile (drawer danger zone)
- Create Profile for virtual clients (drawer)

No action was removed without replacement.

---

## Focus-Management Assessment: NEEDS CORRECTION

### ISSUE 5 — `document.activeElement` unreliability (MODERATE)

Both `openStaffDetail` and `openClientDetail` store `document.activeElement` at the time of the click handler. On mouse click:
- The browser may not have moved focus to the card div yet
- `document.activeElement` may be `document.body` or the previously focused element
- Focus restoration on drawer close would then focus the wrong element

For keyboard activation (Enter/Space), `document.activeElement` IS the card (because it already has focus), so keyboard flow is correct.

**Required correction:** Use `event.currentTarget` in the click handler or maintain a stable ref per card. Since the same function is used for both click and keyboard, the simplest fix is to pass the event and use `event.currentTarget` when available, falling back to `document.activeElement` for keyboard.

### Correct
- Initial focus moves into drawer on open (closeBtnRef.focus)
- Focus containment via Tab trap (existing from 1B.1B)
- Background content blocked by overlay
- Body scroll locked and restored on close
- Escape key closes drawer

---

## Responsive Assessment: SOUND

### Correct
- Desktop: right-side drawer remains functional
- Mobile (≤767px): both staff and client drawers become bottom sheets
- Width: 100vw
- Height: 90dvh
- Border-radius: 20px top corners
- SlideUp animation with cubic-bezier easing
- Internal content scrolls
- Footer visible (drawer-footer CSS outside media query)
- Overlay blocks background (rgba backdrop)
- Very small viewport (≤360px) has reduced padding

### Acceptable
- `prefers-reduced-motion` not explicitly handled for the slideUp animation — document as future improvement but not a blocker (animation is short, 0.3s)

---

## Accessibility Assessment: NEEDS CORRECTION (ISSUE 3)

- Cards: `tabIndex="0"` ✅, `aria-label` ✅, `aria-pressed` ✅, keyboard activation ✅
- Cards: `role="button"` with nested `<button>` ❌ (ISSUE 3)
- Drawer: `role="dialog"` ✅, `aria-modal="true"` ✅, `aria-label` ✅
- Focus trap ✅, focus restoration mechanism exists (ISSUE 5 affects mouse-click accuracy)
- Escape closes drawer ✅
- Pet list: semantic `<ul>/<li>` ✅
- `aria-live="polite"` on My Pets status area ✅
- Status badges use text (not color-only) ✅
- 44px touch targets maintained via card padding ✅

---

## 32-Requirement Coverage Matrix

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | Authenticated navigation link | NOT COVERED | No test |
| 2 | Route renders | NOT COVERED | No component test |
| 3 | Loading state | NOT COVERED | No component test |
| 4 | Populated state | NOT COVERED | No component test |
| 5 | Empty state | NOT COVERED | No component test |
| 6 | API error state | NOT COVERED | No component test |
| 7 | Restricted fields excluded | COVERED | sanitizePetDetails test |
| 8 | No create/edit/delete controls | NOT COVERED | No component test |
| 9 | No mutation API call | NOT COVERED | No component test |
| 10 | Mobile behavior | NOT COVERED | No test |
| 11 | Client card click | NOT COVERED | No test |
| 12 | Staff card click | NOT COVERED | No test |
| 13 | Enter activation | NOT COVERED | No test |
| 14 | Space activation | NOT COVERED | No test |
| 15 | View Details equivalence | NOT COVERED | No test |
| 16 | Selected styling | NOT COVERED | No test |
| 17 | Nested Edit propagation | NOT COVERED | No test |
| 18 | Nested login-action propagation | NOT COVERED | No test (removed from card) |
| 19 | Nested destructive-action propagation | NOT COVERED | No test (removed from card) |
| 20 | Dialog semantics | NOT COVERED | No test |
| 21 | Escape close | NOT COVERED | No test |
| 22 | Close-button behavior | NOT COVERED | No test |
| 23 | Initial focus | NOT COVERED | No test |
| 24 | Focus restoration | NOT COVERED | No test |
| 25 | Client sections | NOT COVERED | No test |
| 26 | Staff sections | NOT COVERED | No test |
| 27 | Destructive confirmation | NOT COVERED | No test |
| 28 | Read-only-to-edit staff transition | NOT COVERED | No test |
| 29 | Mobile sheet classes/behavior | NOT COVERED | No test |
| 30 | No horizontal overflow | NOT COVERED | No test |
| 31 | Semantic pet list and live status | PARTIALLY COVERED | sanitizePetsList tests cover list shape |
| 32 | Keyboard-only workflow | NOT COVERED | No test |

### Coverage Summary

| Category | Count |
|----------|-------|
| COVERED WITH MEANINGFUL ASSERTION | 1 |
| PARTIALLY COVERED | 1 |
| NOT COVERED | 30 |
| **Total** | **32** |

---

## Test Totals

- Tests collected: 84 (79 baseline + 5 new)
- Tests passed: 84
- Tests failed: 0
- Warnings: 0

The 5 new tests cover only `petHelpers.js` sanitization (requirements 7 and partially 31). The remaining 30 requirements have no meaningful test coverage. The current test infrastructure (Node built-in test runner with pure-function tests) cannot test React components, DOM interaction, or browser behavior.

---

## Build Result

- Modules transformed: 105
- Build: ✅ SUCCESS
- Chunks: `index-CYUq8xSE.js` (966.74 KB), `index-C9L87K9J.css` (82.68 KB)
- Chunk size warning: expected baseline behavior (>500 KB)
- No candidate-only build failures

---

## Required Corrections (Bounded AG Prompt)

### BLOCKING — Must fix before deployment

1. **ISSUE 3 — Remove `role="button"` from cards:** Both client and staff card divs must not have `role="button"` while containing nested `<button>` elements. Remove the role attribute. Keep `tabIndex="0"` and the `onKeyDown` handler for keyboard access. The card becomes a generic focusable container with a click handler, which is valid for composite widgets.

2. **ISSUE 4 — Prevent stale pet-data race:** Add a request-identity check to the pet-fetch callback. Before calling `setClientPets(results)`, verify `editingClientId` still matches the client whose pets were fetched. If it doesn't match, discard the results silently.

### RECOMMENDED — Should fix before deployment

3. **ISSUE 5 — Improve focus restoration for mouse clicks:** In `openClientDetail` and `openStaffDetail`, accept the event parameter and store `event.currentTarget` as the trigger ref instead of `document.activeElement`. This ensures mouse clicks restore focus to the actual card element.

### DOCUMENT AS TECH DEBT — Not blocking

4. **ISSUE 1 — Shared login wrapper:** MyPets duplicates the full login flow. A shared `AuthenticatedClientRoute` wrapper would reduce duplication. Not blocking for first release.

5. **prefers-reduced-motion:** Add `@media (prefers-reduced-motion: reduce)` to disable the slideUp animation. Low priority.

---

## Restrictions Confirmed

- ❌ No AWS access
- ❌ No Terraform action
- ❌ No deployment
- ❌ No production Query or Scan
- ❌ No remediation
- ❌ No production-data modification
- ❌ No Cognito write
- ❌ No tenant change
- ❌ No second-tenant creation
- ❌ No Google Play, Stripe, Google Calendar, mobile-distribution, or Ryan-testing change
- ❌ No code modification (review only)

---

## Recommendation: **NEEDS LOCAL CODE CORRECTION**

### Corrections Required

| # | Issue | Severity | AG Action |
|---|-------|----------|-----------|
| 3 | Nested interactive semantics | Blocking | Remove `role="button"` from client and staff card divs |
| 4 | Stale pet-data race | Blocking | Add client-identity check before setClientPets |
| 5 | Focus restoration on mouse click | Recommended | Use event.currentTarget in click handlers |

### Next Matthew Approval Gate

**Matthew authorizes AG to apply the 3 bounded corrections above** (no new features, no layout changes, no backend work). After corrections, Kiro re-reviews and if clean, frontend deployment approval can proceed.

---

## Commits

| Item | Value |
|------|-------|
| Starting commit | `bc43215` |
| Implementation commit reviewed | `fa32ded` |
| Ending commit | (this review) |
| Branch | main |
