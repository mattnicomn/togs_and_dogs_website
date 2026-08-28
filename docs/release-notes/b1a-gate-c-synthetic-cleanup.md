# B1A Gate-C Synthetic Cleanup

**Date:** 2026-08-28

**Starting checkpoint:** `main` at `f75f1624ad1c3f294595f07c875b7ec20a94dd28`

**Run marker:** `SYNTHETIC_B1A_ALPHA_20260827`

**Disposition:** Gate-C cleanup complete; Alpha baseline restored

## Authorization and hard preconditions

Matthew explicitly approved deletion of only the eight documented synthetic B1A items. Before any delete, repository hygiene passed (`HEAD == origin/main`, clean worktree/index, empty stash), API Gateway remained `prod -> atxpw3`, and all 13 production Lambdas were `Active` / `Successful`.

A consistent read-only Alpha inventory returned exactly nine items: `TENANT#test_tenant_alpha / METADATA` plus the eight approved cleanup keys. There were zero missing or unexpected Alpha records. A separate all-eight preflight verified each exact PK/SK, `company_id = test_tenant_alpha`, run linkage, and exclusion of tenant metadata before the first delete.

## Exact cleanup results

Each item received another consistent `GetItem` immediately before a key-specific conditional `DeleteItem`. Every delete required exact PK, exact SK, and exact Alpha company ownership and returned the expected old key.

1. Removed `JOB#43fa73ef-48ed-4309-9d79-c3fdae19c9f1` / `REQ#3fba9817-ccb2-460e-9430-1a65edda79c4`.
2. Removed `PET#3dc14dec-b15f-4790-880a-ad4c7975031d` / `CLIENT#750d5e1a-a4cb-4a2c-bf56-b8854d727326`.
3. Removed `CLIENT#750d5e1a-a4cb-4a2c-bf56-b8854d727326` / `METADATA`.
4. Removed `REQ#3fba9817-ccb2-460e-9430-1a65edda79c4` / `CLIENT#750d5e1a-a4cb-4a2c-bf56-b8854d727326`.
5. Removed `COMPANY#test_tenant_alpha` / `STAFF#staff_alpha01`.
6. Removed `NOTIF#2e3345d7-e669-4ef2-8ef3-a25cc5f7d59f` / `REQUEST#3fba9817-ccb2-460e-9430-1a65edda79c4`.
7. Removed `NOTIF#209486c5-f4e5-4605-b6f4-d579f63e7ab3` / `REQUEST#3fba9817-ccb2-460e-9430-1a65edda79c4`.
8. Removed `NOTIF#9b3d4011-b014-4775-b38a-41d62b927919` / `REQUEST#3fba9817-ccb2-460e-9430-1a65edda79c4`.

No scan result, prefix, wildcard, or batch selection drove deletion.

## Post-cleanup verification

Consistent reads proved:

- Alpha inventory is exactly one item.
- The sole item is `TENANT#test_tenant_alpha / METADATA`.
- All eight synthetic keys return absent.
- The Alpha Cognito identity still exists, is enabled and `CONFIRMED`, retains its Alpha tenant mapping, and remains in two existing groups.
- API Gateway remains stage `prod`, deployment `atxpw3`.
- All 13 production Lambdas remain `Active` / `Successful`.

The eight conditional deletes were tenant-bound to `test_tenant_alpha`. No `tog_and_dogs` record was read as workflow data, modified, or deleted. No email, Postmark, Calendar, workflow endpoint, intake/review/assign Lambda invocation, deployment, AWS configuration, Cognito mutation, DNS, Mobile, Stripe, or additional production write occurred.

## B1A status after cleanup

Gate-B backend workflow evidence and its deviations remain historical: direct DynamoDB staff creation after the `Decimal` serialization failure, the deployed Meet & Greet prerequisite, and direct Lambda invocation with constructed API Gateway-style events. The later real API Gateway/Cognito-authorizer read-only validation remains passed.

This cleanup does not establish full Web workflow validation. A separately scoped and approved real Web/API write-path validation remains outstanding. The P1 `POST /admin/staff` entitlement-log `Decimal` serialization defect remains open and unchanged.
