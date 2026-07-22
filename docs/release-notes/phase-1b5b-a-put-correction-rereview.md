# Phase 1B.5B-A: PUT Validation-Order Correction — Re-Review

**Date:** 2026-07-22
**Reviewer:** Kiro
**Status:** READY FOR PHASE 1B.5B-A DEPLOYMENT PLANNING APPROVAL

---

## Correction Commit Reviewed

`4b6a0f3` — fix(backend): restore pet PUT tenant validation order

## Prior Issue (Resolved)

At `68e1d85`, two candidate-only regressions existed:
1. `test_pet_handler_put_same_tenant_succeeds` — expected 200, got 400
2. `test_pet_handler_put_cross_tenant_blocked` — expected 403, got 400

Both now PASS. ✅

---

## Validation-Order Assessment: CORRECT

The PUT path now follows the correct order:
1. Role authorization (owner/admin/staff)
2. Trusted company_id resolution from auth context
3. Submitted client_id presence check
4. **Same-tenant client validation** (GetItem on `COMPANY#{company_id}, CLIENT#{client_id}`)
5. Pet creation (NEW) or existing-pet resolution
6. Ownership and field update

Cross-tenant requests are rejected at step 4 with 403 — before any pet lookup.

---

## Same-Tenant PUT: ✅ 200

Independently reproduced:
```
test_pet_handler_put_same_tenant_succeeds PASSED
```

## Cross-Tenant PUT: ✅ 403

Independently reproduced:
```
test_pet_handler_put_cross_tenant_blocked PASSED
```

---

## Full Backend-Suite Comparison

| Metric | Parent Baseline | Candidate (654486b) | Delta |
|--------|----------------|---------------------|-------|
| Collected | 752 | 769 | +17 (new test file) |
| Passed | 683 | 700 | +17 (all new tests pass) |
| Failed | 69 | **69** | **0 (exact match)** |
| Warnings | 102 | 108 | +6 (new test deprecation warnings) |

**Zero candidate-only regressions.** The 69 failures are the identical pre-existing baseline set.

---

## Frontend Unchanged: CONFIRMED

`git diff --name-status 8de7953..654486b -- web/src web/tests` produces no output.

- Legacy: 96 passed, 0 failed
- Component: 96 passed, 0 failed
- Combined: **192 passed, 0 failed**

---

## Recommendation: **READY FOR PHASE 1B.5B-A DEPLOYMENT PLANNING APPROVAL**

All criteria met:
- ✅ Validation order correct (tenant check before pet lookup)
- ✅ Same-tenant PUT returns 200
- ✅ Cross-tenant PUT returns 403
- ✅ 69 failures exactly match parent baseline
- ✅ Zero candidate-only regressions
- ✅ Frontend unchanged and healthy (192/192 pass)
- ✅ No DELETE route, no hard delete

---

## Next Matthew Approval Gate

**Matthew approves Phase 1B.5B-A deployment planning:**
1. Backend: Terraform plan (expected: 0 add, 13 change, 0 destroy)
2. Frontend: S3 sync + CloudFront invalidation
3. After deployment: Matthew validates Add Pet / Edit Pet / Archive/Restore in the client drawer

---

## Commits

| Item | Value |
|------|-------|
| Starting review commit | `654486b` |
| Correction commit | `4b6a0f3` |
| Ending commit | (this review) |
