# Release 22W: Post-22V Operational Readiness and Core Workflow Validation Plan

**Status:** Planning
**Date:** 2026-07-11
**Priority:** Medium (stability checkpoint before new features)
**Scope:** Validation plan and next-priority decision framework after 22V production deployment

---

## 1. Background

Release 22V deployed to production on 2026-07-11. It combined two pre-deploy fixes:

| Fix | Source | Issue Resolved |
|-----|--------|----------------|
| Profile Editor drawer portal/overflow stability | 22S | 22P/22R failures: drawer flicker, page-level horizontal scrollbar, background reflow |
| Client Portal My Bookings date/window display | 22U | 22T triage: timezone ISO parse offset, single-day display for multi-day bookings, missing visit windows |

**Production state:**
- Bundle: `index-CZXrWtrt.js`
- CloudFront invalidation: `I7CAY1196DA62J897U29B4NM0S` (completed)
- No backend/Terraform/DynamoDB/Cognito/Stripe/calendar/mobile changes occurred in 22V
- No hotfix/main divergence remains — production now runs from `main`
- Docs commit: `a532650`

**Resolution chain:**
- 22J Profile Editor MVP → 22P failed → 22Q/22R failed → 22S fixed → 22V deployed ✅
- 22T Client Bookings triage → 22U fixed → 22V deployed ✅

---

## 2. Manual Validation Checklist for 22V (Matthew)

### Staff Management & Profile Editor

| # | Check | Safe in Prod? | Status |
|---|-------|:---:|--------|
| 1 | `/admin` loads without errors | ✅ Safe | ⬜ |
| 2 | Staff Management tab shows staff cards | ✅ Safe | ⬜ |
| 3 | Each card shows: name, role badge, status, single "Manage" button | ✅ Safe | ⬜ |
| 4 | Clicking "Manage" opens Profile Editor drawer from right | ✅ Safe | ⬜ |
| 5 | Drawer stays open and stable (no flicker/disappear) | ✅ Safe | ⬜ |
| 6 | No page-level horizontal scrollbar appears when drawer is open | ✅ Safe | ⬜ |
| 7 | Drawer scrolls internally (body does not scroll behind) | ✅ Safe | ⬜ |
| 8 | Clicking X or outside drawer closes it cleanly | ✅ Safe | ⬜ |
| 9 | USmissionhero profile shows "⚠️ Orphaned Login" warning banner | ✅ Safe | ⬜ |
| 10 | USmissionhero account security actions are disabled/hidden | ✅ Safe | ⬜ |
| 11 | Protected admin (Matthew) shows 🔒 Protected banner | ✅ Safe | ⬜ |
| 12 | Protected admin dangerous actions hidden | ✅ Safe | ⬜ |
| 13 | Other staff (Ryan York) show normal active state | ✅ Safe | ⬜ |

### Client Portal & My Bookings

| # | Check | Safe in Prod? | Status |
|---|-------|:---:|--------|
| 14 | `/my-bookings` loads for logged-in client | ✅ Safe | ⬜ |
| 15 | Multi-day bookings show correct date range (e.g., "Jul 15–18, 2026") | ✅ Safe | ⬜ |
| 16 | Single-day bookings show correct single date | ✅ Safe | ⬜ |
| 17 | All selected visit windows display (mapped to friendly labels) | ✅ Safe | ⬜ |
| 18 | No timezone-offset display errors (dates not shifted by a day) | ✅ Safe | ⬜ |
| 19 | Booking status badges display correctly | ✅ Safe | ⬜ |

### General Admin Portal

| # | Check | Safe in Prod? | Status |
|---|-------|:---:|--------|
| 20 | `/book` (public intake form) loads | ✅ Safe | ⬜ |
| 21 | Admin Request List shows correct status queues | ✅ Safe | ⬜ |
| 22 | Needs Action shows pending cancellations (2 records from 22O) | ✅ Safe | ⬜ |
| 23 | Google Calendar status shows "Connected" (not degraded) | ✅ Safe | ⬜ |
| 24 | Platform Admin `/platform-admin` loads | ✅ Safe | ⬜ |

---

## 3. Core Workflow Validation Areas

### Workflows Safe to Visually Verify (No Mutations)

| Area | What to Check | Risk |
|------|---------------|------|
| Care request intake | `/book` form loads, steps navigate, validation shows inline errors | None (don't submit) |
| Client Portal My Bookings | Bookings list, date/window display, status badges | None (read-only) |
| Admin request list/queues | Status tabs, filter counts, record display, action dropdown presence | None (don't click actions) |
| Staff Management cards | Card layout, badges, Manage button presence | None |
| Profile Editor sections | All 7 sections render, correct identity state banners | None (don't save changes) |
| Google Calendar banner | Connection status indicator on admin dashboard | None (read-only) |
| Cancellation queue | Needs Action shows pending records, Review Cancellation visible in dropdown | None (don't approve/deny) |

### Workflows Requiring Explicit Approval Before Testing

| Area | Action | Risk | Requires |
|------|--------|------|----------|
| Submit care request | Creates DynamoDB record + potential notification | Medium | Matthew approval + test data policy |
| Assign staff | Modifies booking record + potential calendar event | Medium | Matthew approval |
| Approve/deny cancellation | Changes record status + potential calendar/notification | Medium | Matthew approval (see 22O plan) |
| Resend invite / password reset | Sends email via Cognito | Medium | Matthew approval |
| Create/edit client/pet | DynamoDB writes | Low-Medium | Matthew approval |
| Multi-day booking creation | Multiple DB records + calendar events | Medium | Matthew approval |
| Postmark notification test | Sends real email | Medium | Matthew approval + test recipient |

---

## 4. Production/Main Branch Status

| Item | Value |
|------|-------|
| Production deployed from | `main` (22V) |
| Hotfix/main divergence | ❌ None — resolved |
| Production bundle | `index-CZXrWtrt.js` |
| 22J Profile Editor | ✅ Deployed and stable (fixed via 22S/22V) |
| 22L Cancellation visibility | ✅ Deployed and working |
| Previous 22M hotfix branch | Superseded — production now matches main |

---

## 5. Issues Resolved by 22S/22U/22V

| Original Issue | Root Cause | Fix |
|----------------|-----------|-----|
| 22P: Drawer flickers/disappears | Card onClick re-triggering, backdrop pointer events, hover CSS transform + backdrop-filter reflow | 22Q (partial) → 22S (portal rendering, fixed positioning, body scroll lock, no backdrop-filter) |
| 22R: Page-level horizontal scrollbar | Drawer rendered inside page flow, `100vw` + scrollbar width | 22S (React Portal to document.body, `inset: 0` fixed positioning, `100dvh`) |
| 22T: Wrong dates on My Bookings | `new Date(isoString)` timezone offset shifting dates backward | 22U (date-only string split parsing, no `new Date()` for display) |
| 22T: Single day shown for multi-day | Only `start_date` rendered, no range logic | 22U (multi-day range with badge: "Jul 15–18, 2026 (4 days)") |
| 22T: Missing visit windows | Only first window shown, no multi-select mapping | 22U (map all selected windows to friendly labels) |

---

## 6. Next Recommended Release Options

| Option | Release Name | Description | Priority | Effort |
|--------|-------------|-------------|----------|--------|
| **A** | 22X | Controlled core workflow smoke test plan | Medium | Low (planning only) |
| **B** | 23A | Profile Editor polish (edit save, audit history stub) | Medium | Medium |
| **C** | 23B | Client Portal booking detail improvements (view details, pet info) | Medium | Medium |
| **D** | 23C | Google Calendar reconnect readiness review | Low | Low (planning) |
| **E** | 23D | Production test/stale data policy and admin labeling | Low-Medium | Low (planning) |
| **F** | — | Process pending cancellation records (22O plan) | Medium | Low (Matthew decision only) |
| **G** | — | Continue SaaS maturity (Stripe live, second-tenant expansion) | Blocked (EIN) | — |

### Recommendation

**Option A (22X)** is recommended as the immediate next step:
- Defines a safe, read-only smoke test that Matthew can run to confirm all core workflows display correctly post-22V
- No mutations, no approval needed for display checks
- Builds confidence before starting new features
- After smoke validation passes, proceed to **Option B or C** for next feature work

**Option F** (cancellation record processing) can happen in parallel — it only requires Matthew's classification decision per the 22O plan.

---

## 7. Pending Items Carried Forward

| Item | Status | Reference |
|------|--------|-----------|
| 2 pending cancellation records | Awaiting Matthew classification | 22O plan |
| USmissionhero orphaned Cognito cleanup | Deferred (requires explicit approval) | 22F/22K plan |
| Ryan external testing | Paused | 19-series |
| EIN / Stripe live | Blocked (IRS) | Backlog |
| Apple Beta App Review | Submitted, outcome unknown | 15J |
| Audit history section in Profile Editor | Deferred to later phase | 22G spec |

---

## 8. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Deployment
- ❌ Terraform/AWS changes
- ❌ DynamoDB writes
- ❌ Submitting care requests or creating bookings
- ❌ Approving/denying cancellations
- ❌ Assigning staff or modifying records
- ❌ Cognito/identity/profile changes
- ❌ Email/password/invite actions
- ❌ Stripe/payment changes
- ❌ Google Calendar changes
- ❌ Mobile/TestFlight/App Store changes
- ❌ Ryan/tester changes
- ❌ Test data creation without separate approval

This is a validation plan and decision framework document. Mutation actions require Matthew's explicit approval.
