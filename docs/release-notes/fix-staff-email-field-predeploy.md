# Fix: Staff Management Email Field (Pre-Deploy)

**Date:** 2026-07-13
**Status:** Pre-Deploy (awaiting deployment approval)
**Type:** Frontend UI fix
**Scope:** Make the staff email input field editable when adding new staff

---

## 1. Root Cause

The Staff Management "Add New Staff" form had the email input unconditionally `disabled`. Users could see the label saying email was required for onboarding, but could never actually type an email address. The field was rendered as read-only with `disabled` hardcoded on the `<input>` element.

## 2. Intended Behavior

| Mode | Email Field | Creates Cognito Account |
|------|:-:|:-:|
| Create & Invite (onboard) | Required, editable | ✅ Yes |
| Profile Only | Optional, editable | ❌ No |
| Editing existing staff | Read-only | N/A (cannot change login email) |

The Client Management form already implemented this pattern correctly — the staff form was inconsistent.

## 3. Fix Applied

Changed the staff email `<input>`:
- **Before:** Always `disabled`, no `onChange`, class `read-only-field`
- **After:** `disabled={!!editingStaffId}` (only when editing existing), `onChange` handler, `required` when onboard mode + new, `placeholder` indicating when required, `aria-label` for accessibility

## 4. Behavior Summary

- New staff + "Create & Invite": email field is editable and required
- New staff + "Profile Only": email field is editable and optional
- Editing existing staff: email field is read-only (cannot change login identity)
- Cancel performs no action
- Profile-only creation does not call Cognito onboarding
- Onboard calls the correct `POST /admin/staff/onboard` route with `custom:company_id`
- Existing tenant assignment uses trusted server-side context (cb35242 hotfix)
- No duplicate user creation (existing "Cognito user already exists" handling preserved)

## 5. Validation

| Check | Result |
|-------|--------|
| Frontend build (Vite) | ✅ 101 modules, 430ms |
| Frontend lint | 47 problems (38 errors, 9 warnings) — baseline match, 0 new |
| Email editable when creating new staff | ✅ (disabled removed for new) |
| Email read-only when editing existing | ✅ (disabled={!!editingStaffId}) |
| Required indicator matches onboard mode | ✅ |
| onChange handler wired | ✅ |
| aria-label present | ✅ |
| Placeholder guidance | ✅ |
| creation_mode contract consistent | ✅ ('onboard' / 'profile_only' throughout) |
| Frontend component tests | ⚠️ No frontend test framework exists in this repository |

### creation_mode Contract

| Value | Meaning | Email Required | API Route | Creates Cognito |
|-------|---------|:-:|:-:|:-:|
| `'onboard'` | Create & invite | ✅ Yes | POST /admin/staff/onboard | ✅ Yes |
| `'profile_only'` | Profile only, no login | ❌ No | POST /admin/staff | ❌ No |

### Email Editing Rules

| State | Email Editable | Reason |
|-------|:-:|--------|
| New + onboard | ✅ Yes | Required for Cognito user creation |
| New + profile_only | ✅ Yes (optional) | May be provided for contact purposes |
| Editing existing (any) | ❌ No (read-only) | Cannot change login identity without explicit workflow |

The editing rule applies identically to both linked and unlinked staff. The label shows "(Read-only)" when editing. This prevents accidental identity changes without a dedicated identity-change workflow.

## 6. Manual Production Smoke-Test Checklist

After deployment, Matthew should verify:
1. Open Staff Management → click "+ Add New Staff"
2. Select "Create & Invite" mode (default)
3. Confirm email field is editable and shows "*"
4. Type a valid email address
5. Switch to "Create Profile Only" mode
6. Confirm email field becomes "(Optional)" — still editable
7. Submit with display name only (profile-only) — confirm success
8. Submit with display name + email (onboard) — confirm invite sent
9. Edit an existing staff member — confirm email shows as read-only

## 7. Deployment

Requires frontend-only production deployment:
- `npm run build`
- S3 sync to production bucket
- CloudFront invalidation
- No backend/Terraform/Lambda changes needed

## 8. Rollback

Revert `web/src/components/AdminDashboard.jsx` to the previous commit and redeploy frontend. No backend rollback needed.

## 9. What Was NOT Changed

- ❌ No backend API changes
- ❌ No Terraform changes
- ❌ No Cognito changes
- ❌ No tenant-resolution changes
- ❌ No production data modification
- ❌ No Client Management changes
- ❌ No mobile changes
