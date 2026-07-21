# Phase 1B.3: Frontend Bounded Corrections Review

**Date:** 2026-07-20
**Reviewer:** Kiro
**Status:** READY FOR PHASE 1B.3 COMPONENT TESTING APPROVAL

---

## AG Correction Commit Reviewed

`b9724ea` — Phase 1B.3: Apply accessibility improvements and race-condition guards to client and staff cards

## Files Changed

| File | Change |
|------|--------|
| `web/src/Admin.css` | card-summary-button-link reset class with focus-visible styling |
| `web/src/components/AdminDashboard.jsx` | Card structure, trigger params, request-sequence guard |
| `web/src/components/ClientDetailDrawer.jsx` | loadingPets prop for loading state |
| `web/tests/phase1b3.test.js` | 10 new structural validation tests |

---

## Client-Card Assessment: SOUND

- Outer card div is **non-interactive** — no `role="button"`, no `tabIndex`, no `onKeyDown`
- A native `<button type="button" className="card-summary-button-link">` occupies the primary summary area
- Native Enter and Space behavior opens the drawer (standard button semantics)
- "View Details" is a sibling `<button>` in a separate action section with `stopPropagation`
- Both buttons call the same `openClientDetail(c, e.currentTarget)` function
- Selected styling remains on the outer card container (accent border + muted bg)
- `focus-visible` styling is clear (3px solid outline with inset offset, rounded)
- No nested interactive semantic violation remains
- No action was lost during restructuring

---

## Staff-Card Assessment: SOUND

- Outer card div is **non-interactive** — no `role="button"`, no `tabIndex`, no `onKeyDown`
- Native `<button type="button" className="card-summary-button-link">` occupies the summary area
- "View Details" is a sibling button with `stopPropagation`
- Both call `openStaffDetail(s, e.currentTarget)`
- Protected, self, virtual, orphaned, role, and access indicators remain intact inside the summary button
- All management actions remain accessible in the staff drawer
- No nested interactive violation

---

## Focus-Restoration Assessment: SOUND

### Primary Path
- `openClientDetail(client, triggerElement)` accepts the trigger as a parameter
- `openStaffDetail(staff, triggerElement)` accepts the trigger as a parameter
- Click handlers pass `e.currentTarget` — this IS the clicked button itself
- Keyboard activation (Enter/Space on the native button) also passes `e.currentTarget`
- Stored trigger is always the actual initiating `<button>` element

### Fallback
- `const el = triggerElement || document.activeElement` — fallback only if triggerElement is somehow undefined
- Assessment: **safe fallback only** — not harmful, never reached in normal flow because event handlers always pass currentTarget

### Restoration Logic
- `if (trigger && typeof trigger.focus === 'function' && document.body.contains(trigger))` — verifies element is still in DOM
- Focus restored only when element is connected
- Refs cleared after restoration (`clientDrawerTriggerRef.current = null`, `staffDrawerTriggerRef.current = null`)

### Other Focus Behavior
- Initial focus moves into client drawer (closeBtnRef.focus on mount)
- Initial focus moves into staff drawer (first input or close button after 50ms)
- Focus containment via Tab trap in both drawers
- Escape close operational (via closeStaffDrawerRef pattern and keydown listener)
- Body scroll locked and restored via useEffect cleanup

---

## Stale-Request Assessment: SOUND

### Guard Mechanism
- `clientPetRequestSeqRef = useRef(0)` — monotonically increasing sequence counter
- `activeClientDetailIdRef = useRef(null)` — stores the currently active client ID

### Protection Flow
1. `handleEditClient` increments `clientPetRequestSeqRef.current` and captures `currentSeq`
2. `activeClientDetailIdRef.current` set to `currentClientId`
3. `setClientPets([])` immediately clears prior pets (prevents flash of stale data)
4. `setIsClientPetsLoading(true)` activates loading indicator
5. On Promise resolution: **double guard** checks both `currentSeq === clientPetRequestSeqRef.current` AND `activeClientDetailIdRef.current === currentClientId`
6. Late responses (from a previous client) are silently discarded
7. Error handler uses the same double guard

### Drawer Close Invalidation
- `clientPetRequestSeqRef.current += 1` — any in-flight request becomes stale
- `activeClientDetailIdRef.current = null` — no client is active
- `setIsClientPetsLoading(false)` — loading indicator cleared

### Race Scenarios Covered
- ✅ Select A, then quickly select B → A's late response ignored
- ✅ Select A, close drawer → A's late response ignored
- ✅ Select A, close, reopen B → A's response ignored, B loads fresh
- ✅ Late empty result from A cannot clear B's pets
- ✅ Late error from A cannot replace B's state

### Closure Safety
The guard uses refs (not captured state) so it correctly evaluates the CURRENT value at resolution time, not the closure-captured value at fetch time. This is the correct pattern.

---

## Loading-State Assessment: SOUND

- `isClientPetsLoading` state tracks loading lifecycle
- `ClientDetailDrawer` receives `loadingPets` prop (default `false`)
- When `loadingPets === true`: renders "Loading pets..." message
- When `loadingPets === false` and `pets.length > 0`: renders pet list
- When `loadingPets === false` and `pets.length === 0`: falls through to summary fallback or empty state
- Loading state cleared on: successful fetch, error, drawer close, no pet IDs found

---

## Preserved Actions and Guardrails: COMPLETE

All previously available actions remain reachable in their respective drawers:
- Client: Edit, Resend Invite, Reset Password, Set Temp Password, Link Login, Create Profile, Disable/Enable, Unlink, Delete
- Staff: Edit Profile, mode transition, role change, assignment, disable/enable, unlink, delete
- Protected-profile restrictions enforced (disabled + tooltip)
- Self-account restrictions remain
- Orphaned-identity restrictions remain
- Unsaved-change confirmation on staff drawer close
- All destructive actions require confirmation dialog

---

## Test Assessment

### 10 New Tests (Source-Structure Assertions)

| # | Test | Type | Proves |
|---|------|------|--------|
| 1 | No role="button" in client card | Structure | ARIA violation removed |
| 2 | No role="button" in staff card | Structure | ARIA violation removed |
| 3 | card-summary-button-link exists ≥2x | Structure | Native buttons rendered |
| 4 | openClientDetail accepts triggerElement | Structure | Parameter exists |
| 5 | openStaffDetail accepts triggerElement | Structure | Parameter exists |
| 6 | triggerElement stored in ref | Structure | Assignment pattern correct |
| 7 | document.body.contains check | Structure | DOM connection verified |
| 8 | Trigger refs cleared | Structure | Cleanup exists |
| 9 | Request sequence refs defined | Structure | Guards initialized |
| 10 | Sequence check before state update | Structure | Race guard present |

### Classification
All 10 new tests are **source-structure assertions** that verify correct patterns exist in the source code. They do NOT:
- Mount React components
- Simulate user clicks or keyboard events
- Test focus movement
- Verify that late responses are actually discarded at runtime
- Test drawer opening/closing behavior

They ARE valid as:
- Regression guards against accidental removal of the fixes
- Markup invariant protection
- Contract verification for the correction patterns

---

## Updated 32-Requirement Coverage Matrix

| # | Requirement | Status |
|---|-------------|--------|
| 1 | Authenticated navigation link | NOT COVERED |
| 2 | Route renders | NOT COVERED |
| 3 | Loading state | NOT COVERED |
| 4 | Populated state | NOT COVERED |
| 5 | Empty state | NOT COVERED |
| 6 | API error state | NOT COVERED |
| 7 | Restricted fields excluded | COVERED (petHelpers test) |
| 8 | No create/edit/delete controls | NOT COVERED |
| 9 | No mutation API call | NOT COVERED |
| 10 | Mobile behavior | NOT COVERED |
| 11 | Client card click | COVERED BY STRUCTURAL ASSERTION (native button exists) |
| 12 | Staff card click | COVERED BY STRUCTURAL ASSERTION (native button exists) |
| 13 | Enter activation | COVERED BY STRUCTURAL ASSERTION (native button = native Enter) |
| 14 | Space activation | COVERED BY STRUCTURAL ASSERTION (native button = native Space) |
| 15 | View Details equivalence | PARTIALLY COVERED (same function call verifiable by inspection) |
| 16 | Selected styling | NOT COVERED |
| 17 | Nested Edit propagation | NOT COVERED (removed from card — N/A) |
| 18 | Nested login-action propagation | NOT COVERED (removed from card — N/A) |
| 19 | Nested destructive-action propagation | NOT COVERED (removed from card — N/A) |
| 20 | Dialog semantics | NOT COVERED |
| 21 | Escape close | NOT COVERED |
| 22 | Close-button behavior | NOT COVERED |
| 23 | Initial focus | NOT COVERED |
| 24 | Focus restoration | COVERED BY STRUCTURAL ASSERTION (trigger stored, contains check, clear) |
| 25 | Client sections | NOT COVERED |
| 26 | Staff sections | NOT COVERED |
| 27 | Destructive confirmation | NOT COVERED |
| 28 | Read-only-to-edit staff transition | NOT COVERED |
| 29 | Mobile sheet classes/behavior | NOT COVERED |
| 30 | No horizontal overflow | NOT COVERED |
| 31 | Semantic pet list and live status | PARTIALLY COVERED (sanitizePetsList + source inspection) |
| 32 | Keyboard-only workflow | NOT COVERED |

### Summary

| Category | Count |
|----------|-------|
| COVERED WITH MEANINGFUL BEHAVIORAL ASSERTION | 1 |
| COVERED BY STRUCTURAL ASSERTION | 5 |
| PARTIALLY COVERED | 2 |
| NOT COVERED | 24 |
| **Total** | **32** |

---

## Test Totals

- Collected: 94
- Passed: 94
- Failed: 0
- Skipped: 0
- Warnings: 0

---

## Build Result

- Modules transformed: 105
- Build: ✅ SUCCESS
- JS chunk: `index-BI8d8-BK.js` (967.83 KB)
- CSS chunk: `index-CMB4x4uO.css` (83.02 KB)
- Chunk warning: >500 KB (unchanged from baseline)
- `git diff --check`: ✅ Clean

---

## Recommended Component-Test Approach: Option A — Vitest + React Testing Library

### Rationale
The current Node test runner tests only pure-function utilities and source-string patterns. It cannot:
- Mount React components
- Simulate user events (click, keyboard)
- Assert focus behavior
- Test asynchronous state updates
- Verify drawer open/close lifecycle

### Recommended Dependencies
- `vitest` — fast Vite-native test runner, already compatible with the project build
- `@testing-library/react` — idiomatic React testing without implementation details
- `@testing-library/user-event` — realistic user event simulation
- `jsdom` — lightweight browser environment

### Scope for Next Phase
With this infrastructure, meaningful tests could cover:
- MyPets route rendering (states 2-6)
- Card click → drawer opens (requirements 11-12)
- Focus movement into drawer (23) and restoration (24)
- Escape close (21)
- Late-response rejection with controlled promises (race condition)
- Staff read-only → edit mode transition (28)
- Destructive confirmation dialog (27)

### Risks
- New devDependencies require package-lock update
- Test configuration file needed (vitest.config.js with jsdom)
- Setup file for React Testing Library cleanup
- Learning curve is minimal (well-documented, widely used)

### Alternative: Option C (Deploy with structural tests only)
Acceptable ONLY because:
- The three blocking code corrections are verified correct by code review
- Native button semantics eliminate the ARIA violation (browser-guaranteed behavior)
- The request-sequence guard uses refs (not closure state), which is the correct async pattern
- Focus restoration checks DOM connection before calling .focus()
- The existing production manual smoke by Matthew provides integration confidence

**Recommendation: Approve component testing framework installation as a parallel workstream. Do not block deployment on its completion.** The structural tests plus Matthew's manual smoke provide sufficient confidence for this bounded release.

---

## Restrictions Confirmed

- ❌ No backend code changed
- ❌ No AWS access
- ❌ No Terraform action
- ❌ No deployment
- ❌ No production Query or Scan
- ❌ No remediation
- ❌ No production-data modification
- ❌ No Cognito write
- ❌ No tenant change or second-tenant creation
- ❌ No Google Play, Stripe, Google Calendar, mobile-distribution, or Ryan-testing change

---

## Recommendation: **READY FOR PHASE 1B.3 COMPONENT TESTING APPROVAL**

All three code corrections are sound:
1. ✅ Accessible card structure — native buttons, no nested interactive violation
2. ✅ Explicit trigger focus restoration — event.currentTarget passed, DOM connection verified, refs cleared
3. ✅ Stale request guard — sequence counter + client ID ref, double-checked before state update, invalidated on close

The code is correct and the build passes. However, meaningful runtime behavioral testing remains absent (24 of 32 requirements have no coverage). The recommended next step is installing a component-test framework (Vitest + React Testing Library) to provide the behavioral confidence needed before production deployment.

---

## Next Matthew Approval Gate

**Matthew approves one of:**

**Option A (preferred):** Approve AG to install Vitest + React Testing Library and write focused component tests for the 10-15 highest-priority behavioral requirements. After tests pass, Kiro reviews → frontend deployment approval.

**Option B:** Accept structural tests + manual smoke as sufficient for this bounded release. Approve frontend production deployment directly. Component testing becomes a follow-up improvement.

---

## Commits

| Item | Value |
|------|-------|
| Starting commit | `62932d9` |
| Correction commit reviewed | `b9724ea` |
| Ending commit | (this review) |
| Branch | main |
