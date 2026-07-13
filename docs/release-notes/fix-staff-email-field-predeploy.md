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
| Email editable when creating new staff | ✅ (disabled removed) |
| Email read-only when editing existing | ✅ (disabled={!!editingStaffId}) |
| Required indicator matches onboard mode | ✅ |
| onChange handler wired | ✅ |
| aria-label present | ✅ |
| Placeholder guidance | ✅ |

## 6. Deployment

Requires frontend-only production deployment:
- `npm run build`
- S3 sync to production bucket
- CloudFront invalidation
- No backend/Terraform/Lambda changes needed

## 7. What Was NOT Changed

- ❌ No backend API changes
- ❌ No Terraform changes
- ❌ No Cognito changes
- ❌ No tenant-resolution changes
- ❌ No production data modification
- ❌ No Client Management changes
- ❌ No mobile changes
