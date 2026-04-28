# Release Notes: RBAC Owner and Client Access Enhancement

## Overview
We have successfully developed the enhanced access-control infrastructure for Tog and Dogs.

## Changed Files
- **`src/backend/common/auth.py`** (Central RBAC engine)
- **`src/backend/handlers/admin_handler.py`**
- **`src/backend/handlers/pet_handler.py`**
- **`src/backend/handlers/assignment_handler.py`**
- **`src/backend/handlers/cancellation_handler.py`**
- **`src/backend/handlers/review_handler.py`**
- **`web/src/api/auth.js`**
- **`web/src/components/AdminDashboard.jsx`**
- **`web/src/components/ClientPortal.jsx`**
- **`web/src/components/CareCard.jsx`**
- **`scripts/sanity_check.py`**

## Access Model Summary
We support role verification in Cognito groups across:
`owner > admin > staff > client`

- **Owner**: Full access across customer bounds.
- **Admin**: Full access minus ultimate configurations.
- **Staff**: Operational constraints only.
- **Client**: Restricted to personal data bounds.

## Redaction Constraints
Masking applies directly against:
`meet_and_greet_notes`, `internal_pricing_notes`, `internal_notes`, `admin_notes`, `staff_notes`, `private_notes`, `pricing_notes`, `discount_rationale`, `owner_comments`, `operational_comments`, `audit_log`.

## Cognito Group Directives
Cognito groups are managed manually in the AWS Console:
1. Create `owner` and `client`.
2. Migrate Ryan securely.

## Test Executable Evidence
Local validation coverage is passed.

Production Context: https://toganddogs.usmissionhero.com/
