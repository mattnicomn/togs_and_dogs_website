# Release 7B Phase 3: Client Management Offline Client UX — Plan

## Objective
Improve visual clarity in Client Management for offline/no-login/no-email clients so admins can instantly distinguish client types and avoid confusing actions.

---

## Current Display Behavior

### Client Card Layout
```
┌─────────────────────────────────────────────┐
│ Display Name  [Protected Platform Admin]     │
│              [Auto-created] [2 requests]     │
│ email@example.com              [No Login]    │
│ 📞 555-1234                                  │
│ 🐾 Buddy (Beagle)                           │
│                                              │
│ ID: client_abc123                            │
│ ─────────────────────────────────────────    │
│ [Link Login Account]                         │
│ ─────────────────────────────────────────    │
│ [Disable] [Delete]                           │
└─────────────────────────────────────────────┘
```

### Current Badges/Labels
| Condition | Badge | Location |
|-----------|-------|----------|
| `is_protected === true` | "Protected Platform Admin" (teal) | After display_name |
| `auto_created === true` | "Auto-created" (green) | After display_name |
| `request_count > 0` | "N requests" (muted) | After display_name |
| `cognito_status === 'not_linked'` | "No Login" (via `getAccessStatus()`) | Top-right corner |
| `is_active === false` | "Disabled" | Top-right corner |
| `cognito_status === 'CONFIRMED'` | "Active" | Top-right corner |
| `cognito_status === 'FORCE_CHANGE_PASSWORD'` | "Invited" | Top-right corner |

### Current Issues for Offline Clients

| Issue | Description | Impact |
|-------|-------------|--------|
| "No Login" is ambiguous | Could mean "hasn't logged in yet" or "intentionally offline" | Admin confusion |
| No email shown as blank | Client card shows empty space where email would be | Looks broken |
| "Link Login Account" always shows | Even for clients with no email (would fail if clicked) | Misleading action |
| No "Offline" or "Manual" indicator | Can't distinguish intentionally-offline from not-yet-onboarded | Workflow confusion |
| No "Admin Created" badge on bookings | Can't tell which bookings were created by admin vs client | Audit gap |

---

## Recommended Changes (Frontend-Only)

### Change 1: Enhanced Access Status for Offline Clients

**Update `getAccessStatus()` to distinguish offline clients:**

```javascript
// Current:
if (!user.cognito_sub && (!user.cognito_status || user.cognito_status === 'not_linked')) {
  return { label: 'No Login', class: 'status-no-login' };
}

// Proposed:
if (!user.cognito_sub && (!user.cognito_status || user.cognito_status === 'not_linked')) {
  if (!user.email) {
    return { label: 'Offline Client', class: 'status-offline' };
  }
  return { label: 'No Login', class: 'status-no-login' };
}
```

This gives:
- Client with email but no Cognito → "No Login" (can be onboarded later)
- Client without email → "Offline Client" (intentionally managed offline)

### Change 2: Show "(no email)" on Client Cards

**When email is blank/missing, show a clear indicator:**

```javascript
// Current:
<p style={{ ... }}>{c.email}</p>

// Proposed:
<p style={{ ... }}>{c.email || <span style={{ fontStyle: 'italic', opacity: 0.6 }}>No email on file</span>}</p>
```

### Change 3: Conditionally Hide "Link Login Account"

**Only show "Link Login Account" when the client has an email address:**

```javascript
// Current: always shows when !cognito_sub
) : (
  <button ...>Link Login Account</button>
)

// Proposed: only show when client has email
) : c.email ? (
  <button ...>Link Login Account</button>
) : (
  <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontStyle: 'italic' }}>
    Offline client — add email to enable login
  </span>
)
```

### Change 4: "Admin Created" Badge on Request List

**Show a small badge on bookings with `source: 'admin_created'`:**

```javascript
// In the request list row, after the status chip:
{item.source === 'admin_created' && (
  <span style={{ fontSize: '9px', marginLeft: '6px', ... }}>Admin Created</span>
)}
```

### Change 5: Add CSS Class for Offline Status

```css
.status-offline {
  background-color: rgba(158, 158, 158, 0.1);
  color: var(--text-muted);
  border: 1px solid rgba(158, 158, 158, 0.3);
}
```

---

## Implementation Scope

| Change | Files | Effort | Risk |
|--------|-------|--------|------|
| Enhanced getAccessStatus | AdminDashboard.jsx | 15 min | Very Low |
| "(no email)" indicator | AdminDashboard.jsx | 10 min | Very Low |
| Conditional Link Login Account | AdminDashboard.jsx | 15 min | Very Low |
| "Admin Created" badge on requests | AdminDashboard.jsx | 20 min | Very Low |
| CSS class for offline status | Admin.css | 5 min | None |

**Total: ~1 hour, frontend-only, no backend or Terraform changes.**

---

## Acceptance Criteria

- [ ] Offline clients (no email) show "Offline Client" badge instead of "No Login"
- [ ] Clients with email but no Cognito still show "No Login"
- [ ] Client cards with no email show "No email on file" instead of blank
- [ ] "Link Login Account" is hidden for clients without email
- [ ] Clients without email see "Offline client — add email to enable login" instead
- [ ] Bookings with `source: 'admin_created'` show a small "Admin Created" badge
- [ ] `npm run build` passes
- [ ] No backend or Terraform changes
- [ ] Existing client cards for portal-enabled clients are unchanged

---

## AG Implementation Prompt

```
AG — implement Release 7B Phase 3: Client Management Offline Client UX Polish.

Frontend-only changes in web/src/components/AdminDashboard.jsx and web/src/Admin.css.

1. In getAccessStatus():
   - If client has no cognito_sub AND no email → return { label: 'Offline Client', class: 'status-offline' }
   - If client has no cognito_sub but HAS email → keep existing 'No Login' behavior

2. In client card email display:
   - If c.email is blank/null → show "No email on file" in italic/muted text

3. In the Link Login Account section (around line ~2720):
   - Only show the button when c.email exists
   - When no email: show "Offline client — add email to enable login" text instead

4. In the Request List row rendering:
   - If item.source === 'admin_created' → show a small "Admin Created" badge after the status chip

5. In Admin.css:
   - Add .status-offline class with muted gray styling

6. Run: npm run build
7. Confirm no backend or Terraform changes.
8. Deploy frontend only (S3 sync + CloudFront invalidation).

Do not modify backend code or Terraform.
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing client cards break | Very Low | Low | Only adds new conditions, doesn't change existing paths |
| "Offline Client" label confuses admin | Very Low | Low | Clear, descriptive label |
| Build failure | Very Low | None | Simple JSX changes |

---

## What Should Remain Deferred

| Item | Reason |
|------|--------|
| Admin UI to convert offline → portal client | Separate feature (add email + onboard) |
| Bulk offline client import | Different scope |
| Offline client notification preferences | Requires backend changes |
| Client card redesign | Larger UX project |
