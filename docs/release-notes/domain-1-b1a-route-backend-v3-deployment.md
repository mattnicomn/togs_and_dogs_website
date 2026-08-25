# DOMAIN-1 / B1A-ROUTE Backend V3 Production Deployment

**Date:** 2026-08-25

**Status:** ROUTE-GATE-A COMPLETE / BACKEND DEPLOYED / ROUTE-GATE-B NOT APPROVED

## Approval boundary

Matthew explicitly approved only the exact saved Terraform plan
`infra/prod/domain1-b1a-route-backend-v3-20260825.tfplan`, SHA-256
`871EF0EA349BDAACA1C7330CC5A6B547DD788B99BA14828E38EA340D1A597D00`,
for the 13 shared-package Lambda code updates. The approved RC evidence head was
`5de430cb41536c1fab217309c10e1e4f78bb98ff`; exact package/plan source was
`46ab28779cc3647ef3664f84ee793cf4a6e8539d`.

This approval did not include API Gateway, Web, Cognito, DNS, tenant
configuration, production data, assignment, Start, Complete, Stripe, Calendar,
notifications, Mobile, B1A/B1B/B2/B3, ROUTE-GATE-B, or ROUTE-GATE-C/B1A-LOGIN.

## Pre-apply verification

- RC head and origin matched; worktree, index, and stash were empty.
- Package SHA-256 was
  `5BD46E19ACBA6AB418352517C19D4BF62BFEC7263B704136593F2B04369AC558`
  (Base64 `W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=`), 139,161 bytes and
  exactly 40 eligible backend files with no cache/bytecode/temp entries.
- Terraform `1.14.8`, AWS provider `5.100.0`, archive provider `2.7.1`, and
  unchanged lockfile SHA-256
  `4481E01E8C1DC7FCC5C0204A4EA19CBB8853C33152A65EBDB0D9C99A68009AA2`
  were used.
- Sanitized workload account `********2897`, region `us-east-1`, workspace
  `default`, the production S3 backend and established lock table were verified.
- Remote state was serial `510`, lineage
  `7235fddd-c101-fe62-7669-7b7b3d858955`, with 250 resource blocks.
- All 13 Lambdas were Active/Successful on common CodeSha256
  `x+QHZkoXDKHCB3Ap5nUL3r5zbmSOUFZm3j3tCRxmY1o=`.
- API Gateway was `prod -> atxpw3`, with 51 paths, 96 methods, 96 integrations,
  one authorizer, and 48 authorizer assignments.
- Saved-plan JSON contained 431 no-ops and exactly 13 in-place Lambda updates.
  Each update changed only `source_code_hash` and computed `last_modified` in
  the plan. There were no replacement paths, non-Lambda changes, adds, or
  destroys. All 336 API records, explicitly including deployment and stage,
  were no-op.

## Exact apply

The exact approved saved plan was applied once using the equivalent of:

```text
terraform -chdir=infra/prod apply -input=false -no-color domain1-b1a-route-backend-v3-20260825.tfplan
```

- UTC start: `2026-08-25T16:13:06.8599655Z`
- UTC completion: `2026-08-25T16:14:28.0494479Z`
- exit code: `0`
- Terraform summary: **0 added / 13 changed / 0 destroyed**

No retry, fresh plan, target, variable change, source edit, or state
manipulation occurred.

## Post-apply Lambda and state evidence

All 13 functions—intake, admin, review, assign, job, google-auth, pet,
cancellation, device, ses-feedback, postmark-webhook, stripe-webhook, and
platform—completed bounded waiters and were Active/Successful. Each now has the
common expected CodeSha256
`W9RuGay6arQYNSUXwZ1L9iv+xyY7cEE2WT8rBDaaxVg=`.

Every sanitized configuration fingerprint matched its own pre-apply value;
the deployment-window aggregate remained
`3598C1E3EB715A424E125FBD48E8F4C1335AD7D1297032BB34F231F554092BD9`.
Role, environment, runtime, handler, memory, timeout, VPC, layers,
architecture, tracing, concurrency, tags, ephemeral storage, and other Lambda
configuration remained unchanged.

State advanced `510 -> 513` on the unchanged lineage. Terraform persisted more
than one state snapshot during the multi-function apply. Attribute-level
comparison of the plan's embedded serial-510 state to live serial 513 proved:

- 250 resource blocks before and after;
- no added or removed resource block;
- outputs identical;
- exactly the 13 authorized Lambda resources changed;
- their only state attribute changes were `code_sha256`, `source_code_hash`,
  provider-computed `last_modified`, and computed `source_code_size`.

## API no-op and non-write verification

API Gateway remained exactly `prod -> atxpw3`, with unchanged 51 / 96 / 96 / 1
/ 48 inventory. Deployment-window fingerprints were identical before and after:

- topology:
  `CD3DE0C49DF2DAEF186DBCDDD0BC0F68E4DF8E83C01FD315F41DB885F55D93DB`;
- authorizer:
  `7760FF41A61553D4A96D819F2B7CA177EC7BFD496D8115F6DD843210C1EADF82`;
- stage configuration excluding deployment ID:
  `BCCA43BE80A427F87A7AB62E266CAED3A1C6D651D7BBBAE01DF85A5EF045FF37`.

Unauthenticated compatibility, unknown-slug, and malformed-slug requests to
`/admin/tenant-info` each returned 401 at the authorizer boundary. Thus a slug
alone did not grant authority. A no-claims direct admin initialization check
completed without a Lambda `FunctionError`, import/init error, or timeout and
exited before tenant data access. No credentials were obtained; authenticated
compatibility, test-tenant route, wrong-tenant, or Platform Admin checks were
not attempted because ROUTE-GATE-C/B1A-LOGIN remains unapproved. Their
fail-closed behavior remains covered by the exact deployed package's previously
completed 11/11 explicit negative suite.

The deployment-window API metric contained four expected 4xx responses from
the deliberate unauthenticated checks and zero 5xx responses. Twelve existing
Lambda log groups contained zero import/init errors and zero timeouts;
ses-feedback had no existing log group. All 13 Lambda control-plane health
checks were Active/Successful.

## Final boundary

No Web deployment, login, Cognito, DNS/Route53/ACM/CloudFront, tenant or
production-data mutation, assignment, Start, Complete, Stripe, Calendar,
notification, Mobile, E1/E2/O1, B1A/B1B/B2/B3, ROUTE-GATE-B, or ROUTE-GATE-C
operation occurred. Stripe test-secret rotation remains separate.

**ROUTE-GATE-A COMPLETE — READY FOR ROUTE-GATE-B REVIEW.**

**DO NOT CONTINUE TO WEB WITHOUT SEPARATE APPROVAL.**
