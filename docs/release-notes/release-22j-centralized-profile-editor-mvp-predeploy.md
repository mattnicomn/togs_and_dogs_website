# Release 22J — Centralized Profile Editor MVP Pre-Deploy

**Release Date:** 2026-07-10
**Status:** PASS (Pre-Deploy Checkpoint)
**Type:** Frontend UI Refactoring (No Backend, Cognito, or S3 deploy yet)
**Scope:** Centralize all staff configuration, Cognito account security management, and danger zone actions inside a centralized Profile Editor side drawer. Simplify active staff cards to show only profile summaries and a single "Manage" action.

---

## 1. Summary of Changes

This release consolidates staff configuration and identity management into a clean, modern side-drawer interface. By stripping out cluttered buttons from the Active Staff List cards, we have simplified the staff dashboard and improved administrative safety.

No database migrations, backend lambda changes, Cognito user modifications, or infrastructure updates occur.

---

## 2. Component Implementation Details

### Staff Card Simplification
* Removed all inline security buttons (*Resend Invite*, *Send Password Reset*, *Set Temporary Password*) and inline danger actions (*Turn Off Login Access*, *Unlink Login*, *Delete Profile*, *Delete Login Account*) from the staff card surface.
* Added a **"+ Add New Staff"** primary button at the top header of the Active Staff List to trigger profile creation.
* Staff cards now render a streamlined profile summary (Display Name, virtual/protected/you badges, Access Level, Email, Assignable status, access badges, and orphaned warnings) and a single primary button: **"Manage"**.
* Clicking the card body or the "Manage" button slides open the editor drawer.

### Side Drawer Layout & Navigation
* **overlay container:** Features a dark transparent overlay backdrop (`rgba(0, 0, 0, 0.6)`) with a blur filter (`backdrop-filter: blur(4px)`) to dim the dashboard context while maintaining visible list perspective behind the drawer.
* **slide-out panel:** A fixed right-side panel (`520px` width, auto-scaling to `100%` viewport width on mobile) styled inside [Admin.css](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/Admin.css).
* **Unsaved-Changes Guard:** Tracks changes by snapshotting the form fields on opening (`initialFormValues`). If the form is modified and the user clicks the Close button (X) or click-backdrops without saving, a native browser `window.confirm` dialog is shown: *"You have unsaved changes. Are you sure you want to close?"*

---

## 3. Section-by-Section Drawer Behavior

1. **Profile Details:**
   * Contains editable fields: Display Name, Phone, Access Level select, Assignment Color select, Assignable checkbox, and internal Staff Notes textarea.
   * Disables the Access Level dropdown for protected platform admins.
   * Includes the submit button at the bottom of the section. On success, it clears prompts, resets editing states, closes the drawer, and refreshes the staff list.
2. **Login Identity:**
   * Renders read-only fields for Email Address, Cognito Username, and dynamic Access Status badges.
   * Shows a prominent warning banner for orphaned profiles: *“⚠️ This profile references a login that no longer exists.”*
3. **Tenant & Role:**
   * Displays read-only scoping parameters: Company ID, access level, and assignability.
4. **Account Security:**
   * Centralizes *Resend Invite*, *Send Password Reset*, and *Set Temporary Password* actions.
   * Links to existing API and confirmation flows.
   * Fully disables security actions for orphaned profiles and protected profiles.
5. **Protected Account Guardrails:**
   * Renders a warning banner for protected admin accounts explaining: *“This account is protected to prevent accidental lockout or loss of platform support access.”*
6. **Danger Zone:**
   * Moves *Unlink Login*, *Turn Off/Restore Login Access*, *Delete Login Account*, and *Delete Profile* into a red-bordered, dedicated safety box.
   * Fully disables unlink/disable/delete buttons for protected platform accounts and self-modifications.
7. **Audit History:**
   * Displays a read-only placeholder: *“Audit history will appear here in a future release.”*

---

## 4. USmissionhero Display Behavior

* Displays as **Orphaned Login** because its Cognito user link is missing.
* Displays the red orphaned warning banner in the Login Identity section.
* Displays that it is a protected identity (marked as `is_protected: true`).
* All account actions and danger zone buttons (*Resend Invite*, *Send Password Reset*, *Set Temporary Password*, *Unlink Login*, *Delete Profile*) are disabled or blocked in the editor drawer.
* No actual Cognito or database mutation occurred during implementation.

---

## 5. Deferred Governance Roadmap

* **controlled protected platform admin management:** In a future release, a platform-admin-only, fully audited, confirmation-gated interface will be added to securely add or deprecate protected support accounts, including validation rules that prevent removing the last active protected administrator. This feature is deferred and will NOT be implemented in 22J.

---

## 6. Build and Test Verification

* **Frontend Build:** Successfully built Vite bundle via `npm run build` with zero errors.
  * JS Chunks compiled under the limit, creating `dist/assets/index-PksocsNs.js`.
* **Backend Unit Tests:** Ran `pytest` suite and confirmed all 32 tests passed (including targeted orphaned status and protected status tests).
