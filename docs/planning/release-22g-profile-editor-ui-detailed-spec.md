# Release 22G: Profile Editor UI Detailed Spec

**Status:** Planning
**Date:** 2026-07-09
**Priority:** Medium-High (implementation-ready spec for AG)
**Scope:** Detailed UI/UX specification for centralized Profile Editor

---

## 1. Staff Management Card Model (Simplified)

### Card Layout

```
┌──────────────────────────────────────────────┐
│ [Avatar/Initials]  Ryan York                 │
│                    Staff • Active             │
│                    ✅ Assignable              │
│                                              │
│                              [Manage →]       │
└──────────────────────────────────────────────┘
```

### Card Fields

| Field | Source | Display |
|-------|--------|---------|
| Name | `display_name` | Bold text |
| Role badge | Cognito group / effective role | Colored chip (Owner/Admin/Staff) |
| Login status | Derived from Cognito state | Small label: Active / Invited / Disabled / ⚠️ Orphaned |
| Assignable | `is_assignable` field | ✅ or ❌ indicator |
| Protected badge | Platform admin / root check | 🔒 if protected |
| Primary action | Always present | "Manage →" button |

### What Is NOT on the Card

- ❌ No "Resend Invite" button
- ❌ No "Password Reset" button
- ❌ No "Disable" button
- ❌ No "Delete" button
- ❌ No "Unlink" button
- ❌ No expandable action menu on the card itself

---

## 2. Profile Editor Layout

### Recommendation: Right-Side Drawer (Slide-In Panel)

| Property | Value |
|----------|-------|
| Type | Slide-in drawer from right |
| Width | ~500px (desktop); full-screen on mobile |
| Trigger | Click "Manage →" on staff card |
| Close | X button, click outside, or Escape key |
| Scroll | Internal scroll within drawer sections |
| Unsaved changes | Warning on close if edits pending |

### Why Drawer (Not Modal or Full Page)

- Drawer keeps the staff list visible behind (context preserved)
- Modal obscures everything (loses context)
- Full page requires back-navigation (heavier)
- Drawer pattern matches existing CareCard behavior in the project

### Mobile/Responsive

- On screens < 768px: drawer becomes full-width bottom sheet or full-screen
- Sections stack vertically
- Actions remain at bottom with sticky footer

---

## 3. Section Specifications

### Section 1: Profile Details

```
┌─── Profile Details ─────────────────────────┐
│ Display Name:  [Ryan York           ]       │
│ Email:         ryan@example.com (read-only) │
│ Phone:         [555-1234             ]      │
│ Notes:         [Internal notes...    ]      │
│ Created:       Jun 15, 2026                 │
│                                             │
│                          [Save Changes]     │
└─────────────────────────────────────────────┘
```

- Email is read-only (linked to Cognito identity)
- Display name, phone, notes are editable
- Save applies changes to DynamoDB staff profile only

### Section 2: Login Identity

```
┌─── Login Identity ──────────────────────────┐
│ Status:       ✅ Active                     │
│ Username:     ryan@example.com              │
│ Last Login:   Jul 8, 2026 3:15 PM          │
│ Cognito Sub:  (hidden - security)           │
│                                             │
│ ── or if orphaned: ──                       │
│ Status:       ⚠️ Orphaned                   │
│ Warning:      Login reference no longer     │
│               exists in authentication      │
│               system.                       │
│                                             │
│ ── or if no login: ──                       │
│ Status:       No login configured           │
│ Hint:         Use "Resend Invite" in        │
│               Account Security to set up    │
└─────────────────────────────────────────────┘
```

- Shows current identity state clearly
- Never shows raw Cognito sub or tokens
- Links to Account Security section for actions

### Section 3: Tenant & Role

```
┌─── Tenant & Role ──────────────────────────┐
│ Business:     Tog & Dogs                    │
│ Company ID:   tog_and_dogs                  │
│ Role:         Staff                         │
│ Groups:       staff                         │
│                                             │
│ ℹ️ Role changes require platform admin     │
│    action.                                  │
└─────────────────────────────────────────────┘
```

- Read-only in MVP (role changes are platform admin operations)
- Shows the tenant this user belongs to

### Section 4: Account Security

```
┌─── Account Security ───────────────────────┐
│                                             │
│ [📧 Resend Invite]                         │
│   Send a new invitation email.             │
│                                             │
│ [🔑 Send Password Reset]                   │
│   User receives email to set new password. │
│                                             │
│ [🔒 Set Temporary Password]                │
│   Requires user to change on next login.   │
│                                             │
│ [⏸️ Disable Login]   or   [▶️ Restore Login] │
│   Prevents/restores authentication.        │
│                                             │
└─────────────────────────────────────────────┘
```

### Section 5: Protected Account Guardrails

Only shown for protected accounts:

```
┌─── 🔒 Protected Account ──────────────────┐
│                                             │
│ This is a protected platform account.       │
│ Security and identity actions are disabled  │
│ to prevent accidental lockout.              │
│                                             │
│ To modify this account, contact the         │
│ platform operator directly.                 │
│                                             │
└─────────────────────────────────────────────┘
```

### Section 6: Danger Zone

```
┌─── ⚠️ Danger Zone ─────────────────────────┐
│                                             │
│ [Unlink Login Reference]                    │
│   Removes the connection between this       │
│   profile and the authentication system.    │
│   The profile is preserved.                 │
│                                             │
│ [Delete Profile]                            │
│   Permanently removes this staff profile.   │
│   This cannot be undone.                    │
│                                             │
└─────────────────────────────────────────────┘
```

- Red/destructive styling
- Hidden for protected accounts
- Each requires double confirmation

### Section 7: Audit History

```
┌─── Audit History ──────────────────────────┐
│                                             │
│ Jul 9  • Invite resent by Matthew           │
│ Jul 1  • Profile created by Matthew         │
│                                             │
│ (Empty state: "No audit history")           │
└─────────────────────────────────────────────┘
```

- Read-only timeline
- Shows action type, actor (safe label), timestamp
- No raw tokens, passwords, or auth data
- MVP: last 10 entries; future: paginated

---

## 4. Action Visibility and Permission Logic

| Action | Profile Only | Invited | Active | Disabled | Orphaned | Protected |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|
| Edit Profile | ✅ | ✅ | ✅ | ✅ | ✅ | ⚠️ Warning |
| Resend Invite | ✅ | ✅ | ❌ Hidden | ❌ Hidden | ❌ Hidden | ❌ Hidden |
| Password Reset | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ Hidden |
| Set Temp Password | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ Hidden |
| Disable Login | ❌ | ✅ | ✅ | ❌ Hidden | ❌ | ❌ Hidden |
| Restore Login | ❌ | ❌ | ❌ Hidden | ✅ | ❌ | ❌ Hidden |
| Unlink Login | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ Hidden |
| Delete Profile | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ Hidden |
| Re-invite (after unlink) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

---

## 5. Confirmation Modal Requirements

### Standard Confirmation

```
┌────────────────────────────────────────────────┐
│ [Action Title]                                  │
│                                                 │
│ You are about to: [consequence statement]       │
│                                                 │
│ Affected: [person name]                         │
│ Tenant: [tenant name]                           │
│ Email will be sent: [Yes/No]                    │
│ Login will be modified: [Yes/No]                │
│                                                 │
│ This action [can/cannot] be undone.             │
│                                                 │
│              [Cancel]   [Confirm Action]         │
└────────────────────────────────────────────────┘
```

### Destructive Confirmation (Delete / Unlink)

```
┌────────────────────────────────────────────────┐
│ ⚠️ Delete Staff Profile                        │
│                                                 │
│ This will permanently remove [name]'s profile.  │
│ This cannot be undone.                          │
│                                                 │
│ Type "DELETE" to confirm: [________]            │
│                                                 │
│              [Cancel]   [Delete Profile]         │
└────────────────────────────────────────────────┘
```

### Rules

- No accidental default-submit behavior (button must be explicitly clicked)
- Cancel is always left; destructive action is right (harder to misclick)
- Destructive button is red/danger styled
- Type-to-confirm only for delete/unlink (not for resend/reset)

---

## 6. Orphaned Identity UX

### Badge on Staff Card

Small warning indicator: `⚠️ Orphaned` (amber text)

### Banner in Profile Editor (Login Identity section)

```
⚠️ This profile references a login identity that no longer exists
   in the authentication system. This user cannot log in.

   Recommended: Unlink the stale reference, then re-invite.
```

### Unlink Action

- Located in Danger Zone section
- Confirmation modal explains: "This removes the stale login reference. The profile itself is preserved. You can re-invite afterward."
- After unlink: profile state returns to "No login configured"

---

## 7. Protected Account UX

### Badge on Staff Card

`🔒 Protected` (appears next to name)

### Banner in Profile Editor

Full-width informational banner at top of editor (not dismissible):
- Yellow/amber background
- Text: "Protected platform account — dangerous actions disabled"
- No close button (always shown for protected accounts)

### Sections Affected

- Account Security: all actions hidden
- Danger Zone: section hidden entirely
- Profile Details: editing allowed with "proceed carefully" note

---

## 8. API/Data Needs

### Staff List (Existing Endpoint)

The current `GET /admin/staff` returns enough for card rendering:
- display_name, email, role/groups, cognito_sub (presence check), is_assignable, status

### Additional Detail (May Need)

| Need | Source | MVP? |
|------|--------|------|
| Cognito user status (CONFIRMED/FORCE_CHANGE/etc.) | Backend checks Cognito | ✅ MVP |
| Orphaned state detection | Backend: has sub but Cognito user not found | ✅ MVP |
| Protected account flag | Backend: check platform_admin group or protected list | ✅ MVP |
| Audit history | New endpoint or existing audit query | ⏳ Later |
| Last login time | Cognito user metadata | ⏳ Later |

### Recommendation

Add a `GET /admin/staff/{staff_id}/identity-status` endpoint (or extend existing GET) that returns:
```json
{
  "login_state": "active|invited|disabled|orphaned|none",
  "is_protected": false,
  "cognito_status": "CONFIRMED",
  "is_assignable": true
}
```

No raw tokens, subs, or private Cognito data in response.

---

## 9. MVP vs Later Phases

### MVP (22I)

- ✅ Staff card simplified (name, badge, status, Manage button)
- ✅ Profile Editor drawer with all 7 sections
- ✅ Action visibility logic based on identity state
- ✅ Confirmation modals for all actions
- ✅ Orphaned/protected banners
- ✅ Existing actions moved into editor (no new backend endpoints required if current APIs support it)

### Later

- ⏳ Audit history section (requires audit query endpoint)
- ⏳ Relink flow (link profile to different Cognito user)
- ⏳ Bulk cleanup tools (unlink multiple orphaned profiles)
- ⏳ Platform admin identity controls (cross-tenant user management)
- ⏳ Last login timestamp display

---

## 10. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **22G** | Profile Editor UI detailed spec (this document) | ✅ Kiro (done) |
| **22H** | Orphaned identity detection (backend utility or endpoint extension) | AG |
| **22I** | Profile Editor MVP implementation (frontend drawer + action routing) | AG |
| **22J** | Profile Editor production deployment + validation | AG + Matthew |
| **22K** | Controlled USmissionhero orphaned link cleanup (if Matthew approves) | AG + Matthew |
| **22L** | Controlled live email/password action validation (if Matthew approves) | AG + Matthew |

---

## 11. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Creating/modifying UI components
- ❌ Backend endpoint changes
- ❌ Cognito/identity/profile actions
- ❌ Email/password/invite actions
- ❌ DynamoDB writes
- ❌ Deployment
- ❌ Terraform/AWS changes
- ❌ Stripe/Google Calendar changes
- ❌ Mobile/TestFlight/App Store changes
- ❌ Ryan/tester changes

This is a UI specification document. Implementation (22H/22I) requires separate approval.
