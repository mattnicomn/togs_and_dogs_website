# Release 5D: Client Management Pet Visibility — Implementation Plan

**Date:** 2026-05-15  
**Status:** Plan Only — No Implementation Yet  
**Prerequisite:** Releases 5A–5C accepted  
**Objective:** Show linked pets on client profile cards so Ryan can see a client's pets without opening individual CareCards.

---

## 1. Current-State Findings

### What's Already Available on Client Profiles

From Release 4A, client profiles may have:
- `pet_names_summary` — comma-separated pet names (rebuilt from active PET# records on approval)
- `pet_breeds_summary` — comma-separated breeds
- `request_count` — number of linked requests

These fields are already used for **search** but are NOT visually displayed on the client cards.

### What's NOT Available Without Extra API Calls

- Individual PET# record details (species, age, active/archived status)
- Per-pet structured data
- Real-time pet list (summary fields only update on approval events)

### Current Client Card Display

Each client card shows:
- Display name + auto-created badge + request count badge
- Email
- Phone (📞 icon)
- Access status badge
- Account security actions
- Edit/Disable/Delete actions

**Gap:** No pet information visible on the card itself.

---

## 2. Recommended Approach: Display Summary Fields (Frontend-Only)

### Option A: Show `pet_names_summary` on client cards ✅ RECOMMENDED

**Simplest, no backend changes, no extra API calls.**

Add a line to each client card showing the pet names and breeds already stored on the profile:

```jsx
{c.pet_names_summary && (
  <p style={{ margin: '4px 0', fontSize: '12px' }}>
    🐾 {c.pet_names_summary}
    {c.pet_breeds_summary && <span style={{ color: 'var(--text-muted)' }}> ({c.pet_breeds_summary})</span>}
  </p>
)}
```

**Pros:**
- Zero backend changes
- Zero extra API calls
- Data already loaded with client list
- Instant rendering

**Cons:**
- Only shows active pet names (not archived status)
- Only updates when approval triggers `_rebuild_pet_summary`
- Doesn't show species or age

### Option B: Fetch PET# records on card expand/click

Would require per-client API calls. Adds complexity and latency. Deferred.

---

## 3. Files Likely to Change

| File | Change | Type |
|------|--------|------|
| `web/src/components/AdminDashboard.jsx` | Add pet summary display to client cards | Frontend |

**One file. ~5 lines of JSX.**

No backend changes. No Terraform.

---

## 4. Implementation Detail

Insert after the phone line and before the account security section:

```jsx
{c.phone && <p style={{ margin: '2px 0' }}>📞 {c.phone}</p>}
{/* Release 5D: Pet visibility on client cards */}
{c.pet_names_summary && (
  <p style={{ margin: '4px 0', fontSize: '12px' }}>
    🐾 {c.pet_names_summary}
    {c.pet_breeds_summary && (
      <span style={{ color: 'var(--text-muted)', marginLeft: '4px' }}>
        ({c.pet_breeds_summary})
      </span>
    )}
  </p>
)}
```

---

## 5. Risks

| Risk | Level | Mitigation |
|------|-------|------------|
| `pet_names_summary` is stale | Low | Only updates on approval. Acceptable for MVP. |
| Field is null for old profiles | None | `&&` guard prevents rendering |
| Long pet name lists overflow | Low | CSS handles wrapping naturally |

---

## 6. Validation Checklist

| # | Test | Expected |
|---|------|----------|
| 1 | Client with pets (summary populated) | Shows "🐾 Joey, Kyle (Golden Retriever, Tabby)" |
| 2 | Client without pets | No pet line shown |
| 3 | Client with names but no breeds | Shows "🐾 Joey, Kyle" (no breed parenthetical) |
| 4 | Search by pet name still works | Unchanged |
| 5 | Client card layout not broken | Clean display |
| 6 | No console errors | Clean |
| 7 | `npm run build` | Passes |

---

## 7. Out of Scope

| Item | Reason |
|------|--------|
| Per-pet detail view in Client Management | Requires extra API calls, deferred |
| Archived pet visibility toggle | Deferred to Release 5E |
| Permanent delete | Deferred |
| Backend changes | Not needed |
| Real-time pet list refresh | Summary fields are sufficient for MVP |

---

## 8. Deployment Type

**Frontend-only.** S3 sync + CloudFront invalidation. No Terraform.
