# Release 22I — Orphaned Identity Detection Production Deployment and Validation

**Release Date:** 2026-07-10
**Status:** PASS
**Type:** Production Backend Lambda & Frontend S3/CloudFront Deployment
**Scope:** Deploy Release 22H orphaned identity detection and safe display logic to the production environment, verify display states, and validate button-disabling safeguards.

---

## 1. Summary of Accomplishments

All pre-deploy validations, backend testing, infrastructure updates, frontend compilation, S3 bucket syncing, and CDN invalidation were executed successfully. 

During validation, the detection logic was adjusted to ensure that if a protected profile (such as `USmissionhero` associated with `mbn@usmissionhero.com`) is orphaned (i.e. its matching Cognito user does not exist in the Cognito User Pool), it is correctly flagged and rendered with the `orphaned` state, displaying the warning banner and disabling risky Cognito account actions.

---

## 2. Pre-Deploy Verification & Caller Identity

* **SSO Authentication Checked:**
  ```json
  {
      "UserId": "AROAVG7T4AZYXQLTIEKJU:multi_account_user",
      "Account": "358604342897",
      "Arn": "arn:aws:sts::358604342897:assumed-role/AWSReservedSSO_AdministratorAccess_11c170f9e933c874/multi_account_user"
  }
  ```
* **Git Status:** Clean tree at commit `bbafde5` (extended with post-test hardening commit `a323419`).
* **Tenant Counts & Isolation:**
  * Active tenants: exactly 2 (`tog_and_dogs` and `test_tenant_alpha`).
  * `TENANT_RESOLUTION_MODE` set to `multi`.

---

## 3. Testing & Frontend Compilation Results

* **Backend Unit Tests:** Run via `pytest`. All 32 tests passed successfully, including targeted tests:
  * `tests/backend/test_r22h_orphaned_identity.py`
  * `tests/backend/test_r22b_resend_invite_fix.py`
  * `tests/backend/test_r8s_login_controls.py`
  * `tests/backend/test_r8u_staff_cleanup.py`
  * `tests/backend/test_r19k_tenant_isolation.py`
* **Vite Production Build:** Compiled successfully in the `web/` workspace:
  * JS Asset: `/assets/index-DJdi5Mdz.js`
  * CSS Asset: `/assets/index-fLn3j3dM.css`
  * `web/dist/index.html` matches the built bundle references.

---

## 4. Infrastructure & Deployment Execution

### Backend Lambda Code Update
1. Deleted stale `infra/prod/backend.zip` to force fresh source code packaging.
2. Ran `terraform plan -out=tfplan-22i` and confirmed 13 Lambda functions to be updated in-place (no resource creations or destructions, except naturally rebuilding the API Gateway deployment to flush endpoint cache).
3. Ran `terraform apply tfplan-22i` successfully:
   * **Apply Result:** `Resources: 0 added, 13 changed, 0 destroyed` (initial attempt) followed by API Gateway Deployment replacement (`1 added, 1 changed, 1 destroyed`).
4. Deleted local `.tfplan` files.

### Frontend S3 Sync & CDN Invalidation
1. Synced `web/dist/` assets to production S3:
   * `aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete`
2. Created CloudFront invalidation:
   * Invalidation ID: `I7E3176W3Y4J1SJ5T0KCFN9GE8` (Distribution `E35L00QPA2IRCY`)
   * Status: **Completed**
3. Confirmed production index.html references the fresh bundle over the wire:
   * `<script type="module" crossorigin src="/assets/index-DJdi5Mdz.js"></script>`

---

## 5. Production Validation Results

An API listing invoke was simulated on the production backend lambda `togs-and-dogs-prod-admin` for the `tog_and_dogs` tenant to evaluate the returned profiles:

* **USmissionhero (mbn@usmissionhero.com):**
  * `identity_state`: `"orphaned"`
  * `identity_status_label`: `"Orphaned Login"`
  * `is_orphaned_identity`: `true`
  * `is_protected`: `true` (remains protected under fallback safeguards)
  * `can_manage_identity`: `false` (disables all Cognito actions)
  * `identity_warning`: `"This profile references a login that no longer exists."`
  * **Result:** **PASS** — Warning text will display on the card, and buttons are safely gated on the frontend.
* **Admin Root (admin@toganddogs.com):**
  * `identity_state`: `"protected"`
  * `identity_status_label`: `"Protected"`
  * `is_orphaned_identity`: `false`
  * `is_protected`: `true`
  * `can_manage_identity`: `false`
  * **Result:** **PASS** — Remains protected.
* **Ryan York (ryanwyork@gmail.com):**
  * `identity_state`: `"linked_invited"`
  * `identity_status_label`: `"Invited"`
  * `is_orphaned_identity`: `false`
  * **Result:** **PASS** — Valid user display did not regress.
* **Tenant Isolation:** Maintained. `/admin/tenant-info` and `/platform/tenants` confirm proper scoping for multi-tenant mode.

---

## 6. Guardrails Confirmation

* No Cognito users, groups, or passwords were created, modified, or deleted.
* No invitations, password resets, or temporary passwords were sent or generated.
* No tenant metadata or database records were mutated.
* No Stripe, Google Calendar tokens, or scheduling data was altered.
