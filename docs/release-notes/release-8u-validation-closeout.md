# Release 8U: Staff Profile Duplicate/Test Account Cleanup & Guardrails — Validation Closeout

This document serves as the master closeout report for **Release 8U**, confirming the successful deployment and production validation of staff assignment guardrails and orphaned test records archival.

---

## 1. Overview & Purpose
The purpose of Release 8U is to address duplicate/test staff profile confusion and enforce strict assignment constraints in the scheduling system:
1. **Production Data Cleanup:** Archived duplicate/orphaned test bookings that referenced a deleted typo staff email (`mattnicomn10@yahoocom`) to prevent confusing dashboard state.
2. **Assignment Dropdown Filter:** Hardened GET `/admin/staff` to dynamically set `is_assignable = False` for profiles that have invalid email formats or lack a linked Cognito account.
3. **API Level Assignment Guardrails:** Added robust email format and eligibility checks in POST `/admin/assign` to reject assignments to unregistered, inactive, or unlinked profiles at write time.

---

## 2. Release & Commit Details

- **Planning Commit:** `41e1ffc` (`docs: plan release 8u staff profile duplicate cleanup`)
- **Implementation Commit:** `edd9731` (`fix(admin): add staff assignment guardrails and archive typo test records`)
- **Closeout Commit:** `docs: close out release 8u validation`

---

## 3. Files Changed

- [src/backend/handlers/admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py) — Enforce runtime assignment eligibility filters
- [src/backend/handlers/assignment_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/assignment_handler.py) — Add worker_id and profile eligibility validation
- [tests/backend/test_r7g_assignment_multiday.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r7g_assignment_multiday.py) — Updated mock payloads to valid emails and mocked DB staff profile queries
- [tests/backend/test_r8u_staff_cleanup.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r8u_staff_cleanup.py) [NEW] — Automated test suite for Release 8U eligibility and validation guardrails

---

## 4. Production Data Cleanup

Two orphaned test records created during Release 8T validation referencing the deleted typo email (`mattnicomn10@yahoocom`) were archived in the production DynamoDB table `togs-and-dogs-prod-data`:
- **Archived Request:** `REQ#d9c4d980-bf21-4cc3-a08b-2a4628dad112` (SK: `CLIENT#client_1697162f`)
- **Archived Job:** `JOB#21d63d97-26a5-4585-bdae-c1573e615e15` (SK: `REQ#d9c4d980-bf21-4cc3-a08b-2a4628dad112`)
- **Archived Reason:** `Test record created during R8T validation - worker_id references removed typo profile`
- **Verification:** Verified directly from production DynamoDB that both records show `status = 'ARCHIVED'` and include the correct `archived_reason`.

---

## 5. Deployment Summary

- **Deployment Method:** Terraform apply (Lambda source-package update only)
- **Deployment Command:**
  ```powershell
  & "C:\Users\mattn\AppData\Local\Microsoft\WinGet\Packages\Hashicorp.Terraform_Microsoft.Winget.Source_8wekyb3d8bbwe\terraform.exe" apply release8u-staff-cleanup-guardrails.tfplan
  ```
- **Resources Changed:** 0 added, 11 changed (Lambda updates in-place), 0 destroyed
- **Frontend Assets / CDN:** No S3 sync or CloudFront cache invalidation was required.

---

## 6. Verification & Validation Details

### A. Automated Local Verification
- **Targeted Tests:** `pytest tests/backend/test_r8u_staff_cleanup.py` $\rightarrow$ **✅ PASS (10/10 tests passed)**
- **Regression Tests:** `pytest tests/backend/test_r7g_assignment_multiday.py` $\rightarrow$ **✅ PASS (3/3 tests passed)**
- **Full Backend Suite:** `pytest tests/backend/` $\rightarrow$ **✅ PASS (296/296 tests passed)**
- **Web App Compile Check:** `npm run build` $\rightarrow$ **✅ PASS**

### B. Production Validation Walkthrough
Validation was performed by invoking the deployed production Lambdas using the `usmissionhero-website-prod` credentials profile:

| Validation Step | Expected Behavior | Status |
|-----------------|-------------------|--------|
| **1. Staff List Visibility** | `GET /admin/staff` successfully returns all 5 valid staff profiles. | ✅ Passed |
| **2. Eligible Staff Linkage** | Test account `mattnicomn10@yahoo.com` is returned with `is_assignable = True` and linked Cognito sub. | ✅ Passed |
| **3. Typo Email Guardrail** | `POST /admin/assign` with typo worker_id format (`mattnicomn10@yahoocom`) is rejected. | ✅ Passed (400 Bad Request) |
| **4. Non-existent Profile Guardrail** | `POST /admin/assign` with unregistered worker_id (`ghost_profile@example.com`) is rejected. | ✅ Passed (400 Bad Request) |
| **5. Data Cleanup Integrity** | Confirm typo-referencing `REQ#` and `JOB#` records are `ARCHIVED` and no other records are changed. | ✅ Passed |

---

## 7. Scope Guardrails
- **No mobile changes:** Zero files modified in `/mobile`.
- **No web frontend changes:** Zero files modified in `/web`.
- **No Terraform structural changes:** Zero resource types added, destroyed, or modified in local Terraform configurations.
- **No S3/CloudFront invalidations:** Static assets were not synced and CloudFront caches were not invalidated.

---

## 8. Follow-up Notes
- Use `mattnicomn10@yahoo.com` as the primary staff mobile test account going forward.
- Ensure all test staff profiles created have valid email structures, is_assignable set to true, and are linked to active Cognito profiles to satisfy the new API validation guardrails.
- Administrative users retain full visibility of all profiles in Staff Management (even if they have invalid formatting) to allow admins to repair bad profiles.
