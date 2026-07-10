# Release 22H — Orphaned Identity Detection Backend/Frontend Pre-Deploy

**Release Date:** 2026-07-09
**Status:** PASS (Pre-Deploy Checkpoint)
**Type:** Backend & Frontend (No Terraform, Cognito, or production data changes)
**Scope:** Safely detect and display staff login identity states in Staff Management

---

## Summary
Implement backend and frontend support to safely detect and display staff login identity states before building the full Profile Editor MVP. This is a read-only detection release: no relinking, unlinking, invitations, or deletions are executed.

---

## Identity State Detection Model
The backend derives the identity state for a staff profile (DynamoDB or Cognito virtual) using the helper `derive_staff_identity_state(profile, cog_match)`:
* **`protected`**: If the profile is a protected platform admin account.
* **`linked_active`**: If the Cognito user exists, is enabled, and status is `CONFIRMED`.
* **`linked_invited`**: If the Cognito user exists, is enabled, and status is unconfirmed (e.g. `FORCE_CHANGE_PASSWORD`, `UNCONFIRMED`).
* **`linked_disabled`**: If the Cognito user exists and is disabled (`Enabled == False`).
* **`orphaned`**: If the profile has a Cognito link (`cognito_sub` is set to a non-sentinel ID) but the Cognito user does not exist.
* **`profile_only`**: If the profile has no Cognito link (`cognito_sub` is empty or `'unlinked'`).
* **`unknown`**: Catch-all default state.

---

## Staff List Response Fields
The `GET /admin/staff` API endpoint now returns the following safe fields for each staff member:
* `identity_state` (string)
* `identity_status_label` (string)
* `is_orphaned_identity` (boolean)
* `is_protected` (boolean)
* `can_manage_identity` (boolean)
* `identity_warning` (string or null)

Raw Cognito Attributes/Structures are shielded and not exposed.

---

## Frontend Badges & Warning Behavior
* **Access Badges:** Map dynamically in `getAccessStatus` on the frontend:
  * `"Protected"` (Teal badge)
  * `"Orphaned Login"` (Grey/disabled badge)
  * `"No Login"` (Dark grey badge)
  * `"Login Active"` (Green badge)
  * `"Invited"` (Yellow badge)
  * `"Login Disabled"` (Red/disabled badge)
* **Orphaned Warning Text:** Cards for orphaned profiles show a warning banner:
  * *“⚠️ This profile references a login that no longer exists.”*
* **Button Disabling Safety:** Account security action buttons (*Resend Invite*, *Send Password Reset*, *Set Temporary Password*) and the *Unlink Login* button are disabled for orphaned profiles.

---

## Expected USmissionhero Display Behavior
* The `USmissionhero` profile references a Cognito sub that does not exist.
* In Staff Management, it will be detected as `orphaned`.
* The card will display the **“Orphaned Login”** badge.
* The card will render the warning banner: *“⚠️ This profile references a login that no longer exists.”*
* All Cognito interaction buttons (*Resend Invite*, *Send Password Reset*, *Set Temporary Password*, and *Unlink Login*) will be disabled.

---

## Backend Unit Tests
A new test suite [`tests/backend/test_r22h_orphaned_identity.py`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r22h_orphaned_identity.py) has been added to test the helper and API list endpoints:
* `test_derive_staff_identity_state_protected`
* `test_derive_staff_identity_state_profile_only`
* `test_derive_staff_identity_state_linked_active`
* `test_derive_staff_identity_state_linked_invited`
* `test_derive_staff_identity_state_linked_disabled`
* `test_derive_staff_identity_state_orphaned`
* `test_list_staff_identity_enrichment` (integrates Cognito listing + DynamoDB profiles query)

All 8 tests, plus 14 existing regression tests (total 22 tests), passed successfully.

---

## Guardrail Confirmation
* No actual invitation or password reset emails sent.
* No temporary passwords set.
* No Cognito users modified or deleted.
* No DynamoDB profiles unlinked or deleted.
* No production care requests or Stripe/calendar changes occurred.
* No database records modified or backfilled.
* No Google Calendar tokens or secrets changed.
* No Stripe changes.
* No TestFlight/App Store changes.
* Git status remains cleanly staged using targeted git add.
