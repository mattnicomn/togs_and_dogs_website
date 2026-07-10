# Release 22F: Centralized Profile Editor and Orphaned Identity Cleanup Plan

**Status:** Planning
**Date:** 2026-07-09
**Priority:** Medium-High (UX improvement + data hygiene before broader onboarding)
**Scope:** Design a centralized profile/identity editor and safe orphaned identity cleanup strategy

---

## 1. Centralized Profile Editor UX Model

### Proposed Sections (Staff/User Detail View)

| Section | Purpose | Contents |
|---------|---------|----------|
| **Profile Details** | Core identity info | Display name, email, phone, role, notes, created date |
| **Login Identity** | Cognito account status | Linked/unlinked state, username, last login, invite status |
| **Tenant & Role** | Organizational placement | company_id, group membership (owner/admin/staff/client) |
| **Account Security** | Password/access management | Resend invite, send password reset, set temp password, disable/restore |
| **Protected Account Guardrails** | Safety banner | Warning for platform admin / protected root accounts |
| **Danger Zone** | Destructive actions | Unlink login, delete profile (with confirmation) |
| **Audit History** | Action trail | Recent changes to this profile (read-only) |

### Navigation

- Staff card in management list → click → opens centralized Profile Editor (full-page or large modal)
- Staff card itself remains simple: name, role badge, status indicator, single "Manage" button
- All complex actions live INSIDE the editor, not as crowded card buttons

---

## 2. Staff Card vs Profile Editor — Action Placement

### Staff Card (Minimal — Quick Glance)

| Shown on Card | Purpose |
|---------------|---------|
| Name + role badge | Identity at a glance |
| Status indicator (active/disabled/orphaned) | Health state |
| "Manage →" button | Opens full profile editor |

### Profile Editor (Full Detail — All Actions)

| Action | Section | Confirmation Required? |
|--------|---------|----------------------|
| Edit name/phone/notes | Profile Details | Save button |
| Resend invite email | Account Security | Confirmation modal |
| Send password reset | Account Security | Confirmation modal |
| Set temporary password | Account Security | Confirmation + warning |
| Disable login | Account Security | Confirmation modal |
| Restore login | Account Security | Confirmation modal |
| Unlink Cognito reference | Danger Zone | Double confirmation |
| Delete profile entirely | Danger Zone | Double confirmation + type-to-confirm |

---

## 3. Identity States

| State | DynamoDB Profile | Cognito User | Login Works? | Display |
|-------|-----------------|--------------|-------------|---------|
| **Profile only** | ✅ Exists | ❌ None | ❌ | "No login configured" |
| **Invited (pending)** | ✅ Exists | ✅ FORCE_CHANGE_PASSWORD | ⚠️ First login required | "Invited — awaiting first login" |
| **Active** | ✅ Exists | ✅ CONFIRMED | ✅ | "Active" (green) |
| **Disabled** | ✅ Exists | ✅ Exists but disabled | ❌ | "Login disabled" (amber) |
| **Orphaned link** | ✅ Exists (has cognito_sub) | ❌ User not found in Cognito | ❌ | "⚠️ Orphaned — Cognito user not found" |
| **Protected platform admin** | ✅ Exists | ✅ CONFIRMED | ✅ | "🔒 Protected account" |
| **Owner/Admin** | ✅ Exists | ✅ CONFIRMED | ✅ | Role badge: Owner/Admin |

---

## 4. Protected Account Behavior

### Protected Accounts

- Platform admin (Matthew's usmissionhero account)
- Root/admin account (`admin@toganddogs.com` / protected sub)
- Any account in `platform_admin` Cognito group

### Guardrails for Protected Accounts

| Action | Allowed? | Reason |
|--------|----------|--------|
| View profile | ✅ | Read-only safe |
| Edit display name | ⚠️ With warning | Low risk but should be deliberate |
| Resend invite | ❌ Hidden | Not applicable to active protected accounts |
| Password reset/set temp | ❌ Hidden | Must not lock out platform admin |
| Disable login | ❌ Hidden | Must not disable platform access |
| Unlink login | ❌ Hidden | Would orphan critical account |
| Delete profile | ❌ Hidden | Would remove platform admin |

### UI for Protected Accounts

```
┌────────────────────────────────────────────────┐
│ 🔒 Protected Platform Account                  │
│                                                 │
│ This account is a protected platform            │
│ administrator. Dangerous actions are disabled   │
│ to prevent accidental lockout.                  │
│                                                 │
│ To modify this account, contact the platform    │
│ operator directly.                              │
└────────────────────────────────────────────────┘
```

---

## 5. Orphaned Cognito Linkage Handling

### Detection

A staff profile has an orphaned link when:
- Profile record has `cognito_sub` field set
- Cognito `ListUsers` or `AdminGetUser` with that sub returns "user not found"
- This means the DynamoDB profile references a Cognito user that no longer exists (or was never properly created)

### UI Display

```
┌────────────────────────────────────────────────┐
│ ⚠️ Orphaned Login Reference                    │
│                                                 │
│ This profile references a login identity that   │
│ no longer exists in the authentication system.  │
│                                                 │
│ This user cannot log in. To fix:                │
│ • Unlink the stale reference, then              │
│ • Re-invite or create a new login              │
│                                                 │
│ [Unlink Stale Reference]  (requires approval)   │
└────────────────────────────────────────────────┘
```

### Safe Unlink Flow

| Step | Action | Effect |
|------|--------|--------|
| 1 | Admin clicks "Unlink Stale Reference" | Confirmation modal appears |
| 2 | Admin confirms | Profile's `cognito_sub` field is cleared |
| 3 | Profile returns to "No login configured" state | Safe — no data deleted |
| 4 | Admin can then "Resend Invite" or "Link to existing Cognito user" | New clean linkage |
| 5 | Audit record created | Documents the unlink action |

### What Unlink Does NOT Do

- Does NOT delete the staff profile
- Does NOT delete any Cognito user (it's already gone)
- Does NOT affect other staff/client records
- Does NOT modify the tenant or other tenants

---

## 6. USmissionhero-Specific Cleanup Recommendation

### Current State

The "USmissionhero" staff profile has an orphaned Cognito link — `Resend Invite` fails with "Cognito user not found." This is a known legacy linkage issue.

### Recommendation

| Action | Timing | Approval |
|--------|--------|----------|
| Document as known orphaned profile | ✅ Done (22A/22F) | N/A |
| No immediate data mutation | ✅ Current state | N/A |
| Plan controlled unlink + re-invite in 22J | ⏳ Future | Matthew approval |
| Do not delete the profile | ✅ Preserved | N/A |
| Do not expose raw Cognito sub/email in docs | ✅ | N/A |

### Future Cleanup (22J — Only If Approved)

1. Matthew approves the exact profile to unlink
2. AG or Matthew clears `cognito_sub` on the orphaned profile
3. If needed: re-invite with corrected email/identity
4. Audit records document the change
5. Validate login works after re-link

---

## 7. Validation and Audit Requirements

| Requirement | Implementation |
|-------------|---------------|
| Every identity action creates an audit record | Backend writes audit on resend/reset/disable/restore/unlink/delete |
| No password or token values shown in UI | Only status labels; credentials handled by Cognito directly |
| Email/password actions require confirmation modal | UI gate before API call |
| Protected accounts cannot be accidentally modified | UI hides dangerous actions; backend also checks |
| Tenant isolation preserved | Profile editor operates within caller's company_id only |
| Cross-tenant profiles never visible | Standard tenant isolation rules apply |

---

## 8. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **22F** | Profile editor + orphaned identity cleanup plan (this document) | ✅ Kiro (done) |
| **22G** | Centralized Profile Editor UI detailed spec (wireframes, components) | Kiro |
| **22H** | Orphaned identity detection implementation (backend utility) | AG |
| **22I** | Profile Editor MVP implementation (frontend + backend actions) | AG |
| **22J** | Controlled USmissionhero orphaned link cleanup (Matthew approval required) | AG + Matthew |
| **22K** | Controlled account action validation (live email/password test if approved) | AG + Matthew |

---

## 9. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Sending invite/reset emails
- ❌ Setting passwords
- ❌ Disabling/restoring/unlinking/deleting any profile or login
- ❌ Modifying Cognito users/groups/attributes
- ❌ Modifying tenant metadata
- ❌ DynamoDB writes
- ❌ Deployment
- ❌ Terraform/AWS changes
- ❌ Stripe/Google Calendar changes
- ❌ Mobile/TestFlight/App Store changes
- ❌ Ryan/tester changes
- ❌ Creating production data

This is a planning document. Implementation (22G+) requires separate approval.
