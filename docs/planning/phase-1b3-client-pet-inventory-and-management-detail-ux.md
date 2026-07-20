# Phase 1B.3 — Client Pet Inventory and Management Detail UX

**Date:** 2026-07-20
**Status:** Planning Complete — Awaiting Matthew Approval for AG Implementation
**Type:** Frontend-only (no backend or infrastructure changes)

---

## Objective

Deliver a cohesive management detail experience across Client Management, Staff
Management, and the Client Portal. Introduce a read-only My Pets route in the client
portal, unify card-selection interaction patterns, and establish the right-side drawer
as the primary detailed workspace for both client and staff records.

---

## Scope

1. Client Portal: read-only My Pets route
2. Whole-card selection interaction (Client and Staff Management)
3. Drawer as detailed workspace (enhanced Client drawer, aligned Staff drawer)
4. Profile card simplification
5. Responsive/mobile behavior
6. Accessibility compliance

**No backend changes.** All data comes from existing endpoints (GET /client/pets,
GET /admin/pets?clientId, GET /admin/clients, GET /admin/staff).

---

## 1. Client Portal — My Pets Route

### Recommendation: Dedicated `/my-pets` Route

A dedicated `/my-pets` route is preferred because:
- The existing client navigation already uses separate routes (`/`, `/my-bookings`)
- A new route maintains clear URL semantics and browser history support
- It avoids bloating the existing ClientPortal component

### Requirements

- Add "My Pets" to client navigation between "Portal" and "My Bookings"
- Use the existing authenticated GET /client/pets endpoint
- Display active pets only (backend already filters `is_active === False`)
- Show client-safe fields only: name, species, breed, age, care_instructions,
  feeding_notes, medication_notes, behavior_notes
- Respect sanitizer restrictions (no internal_pricing_notes, no quote_amount,
  no meet_and_greet_notes)
- States: loading spinner, empty ("No pets on file"), error, populated grid/list
- No create, edit, delete, archive, or remediation capability
- No production test-data creation
- Mobile-responsive layout (card grid stacks to single column below 480px)
- Keyboard accessible: Tab through pet cards, proper heading hierarchy
- Screen-reader accessible: semantic list, descriptive labels

### Component Structure

```
web/src/components/MyPets.jsx
├── Loading state (spinner)
├── Error state (retry button)
├── Empty state ("No pets on file" illustration)
└── Pet card grid
    └── PetCard (name, species, breed, age, care notes)
```

---

## 2. Whole-Card Detail Interaction

### Design

For both Client Management and Staff Management:

- Clicking anywhere on a profile card selects the record and opens its detail drawer
- Enter and Space activate a focused card (keyboard equivalence)
- "View Details" button performs the same action (accessible redundancy)
- Nested action buttons (Account Security, Edit, Disable, Delete) use
  `stopPropagation` to prevent accidental card activation — this pattern already
  exists in Phase 1B.1C
- Selected-card styling: accent border + muted background (already implemented)
- Focus moves into the drawer on open
- Closing the drawer restores focus to the originating card

### Changes Required

- Client Management: card `onClick` already calls `handleEditClient` which selects
  the client. Wire it to also open the ClientDetailDrawer (currently only "View
  Details" opens the drawer).
- Staff Management: card currently has no `onClick` on the card div itself (only
  the "Manage" button). Add card-level click to open the staff drawer.
- Both: add `role="button"`, `tabIndex="0"`, `onKeyDown` for Enter/Space.

---

## 3. Drawer as Detailed Workspace

### Client Drawer Sections (Enhanced)

| # | Section | Data Source | Status |
|---|---------|-------------|--------|
| 1 | Overview & Profile Status | GET /admin/clients | ✅ Exists |
| 2 | Contact Information | GET /admin/clients | ✅ Exists |
| 3 | Login Identity & Access | GET /admin/clients + cognito fields | ✅ Exists |
| 4 | Pets | GET /admin/pets?clientId | ⬆️ Enhance (currently shows summary only) |
| 5 | Request & Booking Summary | GET /admin/clients (request_count) | ✅ Exists (count only) |
| 6 | Notes | GET /admin/clients (notes field) | ✅ Exists |
| 7 | Account Actions | Existing buttons | 🆕 Move from card |

**Pet section enhancement:** Replace the current summary-only text with the actual
PET record list (already fetched when card is selected via `clientPets` state).
Show: name, species, breed, is_active badge. No edit capability.

**Account actions section:** Relocate the action buttons currently on the card
(Edit, View Details is moot inside drawer, Login access controls) into a clearly
separated actions section at the bottom of the drawer.

### Staff Drawer Sections (Aligned)

| # | Section | Data Source | Status |
|---|---------|-------------|--------|
| 1 | Overview & Staff Status | GET /admin/staff | ✅ Exists (in Profile Details form) |
| 2 | Contact & Email | staff record | ✅ Exists |
| 3 | Role & Permissions | staff record | ✅ Exists |
| 4 | Account/Login Status | cognito fields | ✅ Exists (access badge) |
| 5 | Assignments | Not currently available via API | 🔮 Future work |
| 6 | Notes | staff record | ✅ Exists |
| 7 | Staff Actions | Existing buttons | Exists (in drawer already) |

**Note:** The staff drawer already exists as a profile editor. Phase 1B.3 adds a
read-only overview mode when opened via card click, with an "Edit" button to
transition to the editor. This avoids the current behavior where clicking a card
immediately opens an edit form.

---

## 4. Profile Card Simplification

### Client Cards — Keep on Card

- Display name + badges (Protected, Auto-created)
- Email (or "No email on file")
- Profile status badge + Account status badge
- Pet summary line (🐾 names)

### Client Cards — Move to Drawer

- Phone number
- Full PET# record list
- Account Security buttons (Resend Invite, Reset Password, Set Temp Password)
- Link Login Account button
- Unlink button
- Client ID display
- Create Profile button (virtual clients)

### Staff Cards — Keep on Card

- Display name + color dot
- Role badge
- Access status badge
- Virtual/Protected/Self badges

### Staff Cards — Move to Drawer

- Email, phone, is_assignable
- Orphaned identity warning (keep a small indicator icon on card)
- All management actions

### Destructive Actions (in Drawer Only)

- Visually separated with a danger-zone border
- Explicitly labeled ("Turn Off Login Access", "Delete Profile")
- Protected by confirmation dialog
- Inaccessible through accidental card activation (card click opens read view)

---

## 5. Shared Primitives Between Client and Staff

### Recommended Shared Components

| Component | Purpose |
|-----------|---------|
| `ProfileCard` | Base card with selection state, keyboard activation, badges |
| `DetailDrawer` | Portal-rendered right-side drawer with focus trap, scroll lock, Escape close |
| `StatusBadge` | Consistent badge rendering across client/staff |
| `DrawerSection` | Titled section with consistent spacing |
| `DangerZone` | Separated destructive-actions container with confirmation |

### Differences That Must Remain

- Client has pet section; staff does not
- Staff has assignment color and is_assignable; client does not
- Staff drawer has edit form; client drawer is read-only (edit is separate)
- Action sets differ (client: login access, invite; staff: role change, unlink)

---

## 6. Responsive Behavior

### Desktop (≥769px)

- Right-side detail drawer (existing pattern)
- Selected card remains visible in the grid
- Grid narrows when drawer is open (existing `drawer-open` class)

### Tablet (481–768px)

- Drawer overlays as a wider panel (70–80% viewport)
- Cards visible behind overlay backdrop

### Mobile (≤480px)

- Full-screen detail sheet (100vw × 100dvh)
- Clear close control (× button or back arrow)
- Body scroll locked while open
- Internal content scrolls independently
- No horizontal overflow
- Touch targets ≥ 44px
- Focus management preserved
- Sticky header and footer (actions) within sheet

---

## 7. Accessibility Requirements

- Card: `role="button"`, `tabIndex="0"`, `aria-label` with client/staff name
- Enter and Space activate card (open drawer)
- Drawer: `role="dialog"`, `aria-modal="true"`, `aria-label`
- Focus trap within open drawer
- Focus restoration to originating card on close
- Escape closes drawer
- Heading hierarchy preserved within drawer sections
- Pet list: semantic `<ul>` with descriptive items
- Status badges: text content sufficient (no color-only information)
- Loading/empty/error states announced via `aria-live="polite"`

---

## 8. Test Plan

### My Pets Route

| # | Test | Validates |
|---|------|-----------|
| 1 | /my-pets route renders | Navigation and routing |
| 2 | Authenticated pet retrieval | API integration |
| 3 | Loading state shown | UX |
| 4 | Empty state shown when no pets | UX |
| 5 | Error state shown on API failure | Error handling |
| 6 | Populated state renders pet cards | Data display |
| 7 | Client-safe fields only | Sanitization |
| 8 | No mutation actions available | Read-only enforcement |

### Card Interaction

| # | Test | Validates |
|---|------|-----------|
| 9 | Whole-card click opens drawer | Selection behavior |
| 10 | Enter activates focused card | Keyboard access |
| 11 | Space activates focused card | Keyboard access |
| 12 | View Details button equivalence | Redundant path |
| 13 | Nested action buttons don't bubble | stopPropagation |
| 14 | Selected state visible | Visual feedback |

### Drawer Behavior

| # | Test | Validates |
|---|------|-----------|
| 15 | Drawer opens on card selection | Core behavior |
| 16 | Drawer closes on × button | Close control |
| 17 | Drawer closes on Escape | Keyboard close |
| 18 | Focus moves into drawer on open | Accessibility |
| 19 | Focus returns to card on close | Accessibility |
| 20 | Client drawer shows all sections | Content |
| 21 | Staff drawer shows all sections | Content |
| 22 | Destructive actions require confirmation | Safety |

### Mobile/Responsive

| # | Test | Validates |
|---|------|-----------|
| 23 | Mobile sheet renders full-screen | Layout |
| 24 | No horizontal overflow | Layout |
| 25 | Body scroll locked | UX |
| 26 | Internal scroll works | UX |
| 27 | Close control reachable | Touch targets |

---

## 9. Implementation Sequence

| Phase | Scope | Depends On |
|-------|-------|-----------|
| 1B.3A | Shared card-selection and drawer interaction primitives | — |
| 1B.3B | Client Management: card-click opens drawer, actions relocated | 1B.3A |
| 1B.3C | Staff Management: card-click opens read-only drawer, edit mode transition | 1B.3A |
| 1B.3D | Client Portal My Pets route | — (independent) |
| 1B.3E | Responsive/mobile behavior (full-screen sheet) | 1B.3A |
| 1B.3F | Accessibility and keyboard tests | 1B.3A–E |
| 1B.3G | Frontend unit tests and build validation | 1B.3A–F |

1B.3D (My Pets) is independent of the drawer work and can be implemented in parallel.

---

## 10. Approval Gates

| Gate | Approver | Requires |
|------|----------|----------|
| AG local frontend implementation | (authorized by Matthew approving this plan) | — |
| Kiro implementation review | Kiro | Tests pass, build succeeds, no lint regressions |
| Production frontend deployment | Matthew | Review + approval |
| Authenticated manual smoke | Matthew | Post-deployment browser validation |

**No backend or Terraform plan is required.** All endpoints already exist.

---

## 11. Files and Components Likely Affected

| File | Change |
|------|--------|
| `web/src/App.jsx` | Add `/my-pets` route, add navigation link |
| `web/src/components/MyPets.jsx` | New component |
| `web/src/components/ClientDetailDrawer.jsx` | Enhance pets section, add actions section |
| `web/src/components/AdminDashboard.jsx` | Card-click wiring, action relocation |
| `web/src/Admin.css` | Shared drawer/card styles, responsive rules |
| `web/src/components/shared/ProfileCard.jsx` | New shared primitive (optional) |
| `web/src/components/shared/DetailDrawer.jsx` | New shared primitive (optional) |
| `web/tests/clientManagement.test.js` | Additional card/drawer tests |

---

## 12. Explicit Exclusions

- ❌ No backend code changes
- ❌ No Terraform or infrastructure changes
- ❌ No new API endpoints
- ❌ No pet create/edit/delete/archive capability
- ❌ No production test-data creation
- ❌ No remediation
- ❌ No second-tenant creation
- ❌ No Cognito changes
- ❌ No Stripe, Google Calendar, or mobile distribution changes
