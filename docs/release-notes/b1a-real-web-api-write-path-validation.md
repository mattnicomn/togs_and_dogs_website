# B1A Real Web/API Write-Path Validation

**Date:** 2026-09-02

**Status:** B1A REAL WEB/API WRITE-PATH VALIDATION PASS

**Execution disposition:** `B1A_REAL_WEB_API_WRITE_PATH_PASS`

**FULL END-TO-END B1A IS NOT CLAIMED**

## Evidence provenance and authority

This documentation/Git-only closeout records the completed Matthew-approved
production validation and the authoritative sanitized evidence supplied for
closeout. No production check, browser action, AWS call, Terraform operation,
or application/data mutation was repeated during this documentation task.

The [original approval plan](../planning/b1a-real-web-api-write-path-validation-plan.md)
was executed under separate explicit Matthew approval at clean, synchronized
`main` / `origin/main` checkpoint
`64e37128413f06fa508d13d4cea57428de98154a`. Authority was limited to one
successful Profile Only staff creation, bounded read-only verification, and
one exact conditional deletion of that same synthetic item. It is exhausted;
this record is not authority to repeat the run or continue the workflow.

## Real Web/API request and entitlement result

- Execution start (UTC): `2026-09-02T18:23:12.426Z`.
- Browser submit action returned (UTC): `2026-09-02T18:23:14.230Z`.
- Tenant: `test_tenant_alpha`, the existing internal validation tenant.
- Web route: `/t/test-tenant-alpha/admin`.
- API route: `POST /admin/staff` through the authenticated tenant Web UI.
- Identity boundary: privately authenticated intended non-protected Alpha
  owner/admin; strict tenant bootstrap succeeded before operational access.
- Mode: Create Profile Only, not Cognito onboarding.
- POST attempts: exactly **1**, with **0 retries**.
- Successful result: **HTTP 200 success path**, evidenced by the UI message
  `Staff profile created successfully`, the displayed new no-login profile,
  and the verified deployed handler/proxy contract. Raw HTTP response/status
  and session material were not captured. This is not a raw wire-status claim.
- The exact staff ID/key below came from consistent DynamoDB readback, not an
  independently captured raw POST response. The deployed handler returns the
  same newly persisted profile through its HTTP 200 Lambda-proxy response.
- Correlated admin request ID: `2366b8c8-2a43-449b-a4e7-662444b50300`.
- Target entitlement decision: exactly **1** `ENTITLEMENT_ALLOWED` event for
  `check_type=limit`, `limit_key=max_staff`, company `test_tenant_alpha`.
- `protected_admin_bypass=false`; numeric `current_count=0`; numeric
  `max_allowed=1`. The Decimal-backed limit serialized successfully.

No password, token, cookie, Authorization header, JWT, or raw session data is
included in this record.

## Exact persistence and restoration

The sole temporary staff key was:

`COMPANY#test_tenant_alpha / STAFF#staff_eb16cb8b`

The exact marker in both `display_name` and `notes` was:

`SYNTHETIC_B1A_REAL_API_ALPHA_20260902_R181942Z`

The consistently read item matched `company_id=test_tenant_alpha`,
`staff_id=staff_eb16cb8b`, `role=Staff`, `is_active=true`, and
`is_assignable=false`. Its `email`, `cognito_sub`, and `phone` were DynamoDB
NULL values. No login identity was created.

| Checkpoint | Alpha inventory | Staff count | Marker matches | Unexpected items |
| --- | --- | ---: | ---: | ---: |
| Before POST | Exactly 1: tenant metadata only | 0 | 0 | 0 |
| After POST | Exactly 2: metadata + the exact staff key above | 1 | 1 | 0 |
| After cleanup | Exactly 1: tenant metadata only | 0 | 0 | 0 |

Cleanup completed at `2026-09-02T18:27:26.0449366Z`. Immediately before the
delete, a consistent exact-key read reconfirmed the approved record. Exactly
one conditional `DeleteItem` succeeded, with SDK attempts bounded to one
(`AWS_MAX_ATTEMPTS=1`). The condition bound PK, SK, company, staff ID, both
marker fields, role, active/assignable flags, and NULL types for email,
Cognito linkage, and phone. `ALL_OLD` matched the approved synthetic record.

Consistent post-cleanup verification proved the exact staff key absent and
Alpha restored to exactly:

`TENANT#test_tenant_alpha / METADATA`

Final staff count: **0**. Final marker count: **0**. Metadata was preserved,
not rewritten. The browser refresh also showed the synthetic marker absent.
Production mutations during the completed validation were exactly the approved
**one create / one delete pair**, with no other application write.

## Side-effect and error evidence

The recorded validation window had:

- **0** unexpected records or notification-ledger artifacts;
- **0** Postmark sends or other downstream notification activity;
- **0** Calendar actions; Alpha remained `none / not_configured`;
- **0** Cognito mutations;
- **0** asynchronous workflow activity;
- **0** Lambda ERROR / Exception / Traceback events attributable to the run;
- **0** P1 Decimal serialization errors.

The final Lambda log sweep covered `2026-09-02T18:23:10Z` through
`2026-09-02T18:33:02.563Z` across the 12 existing production log groups:
admin, assign, cancellation, device, google-auth, intake, job, pet, platform,
postmark-webhook, review, and stripe-webhook. Error/exception/traceback and
Decimal patterns returned zero. The unused ses-feedback Lambda had no log
group; its invocation metric sum was zero. This is not a claim to have scanned
a nonexistent thirteenth log group.

Intake/review/assign/job START counts were zero. Admin notification, Postmark,
Calendar, Step Functions, and job indicators were zero. The event-name-only
Cognito review through `2026-09-02T18:34:01Z` found zero mutations and only
read operations (`ListGroups`, `ListUsersInGroup`). No raw logs or session
exports are committed.

Local execution qualifications: a form locator was corrected before submission
(zero POSTs at that point); a PowerShell parse error occurred before any cleanup
AWS call, followed by the sole actual delete; and the missing ses-feedback log
group was resolved by read-only listing plus its zero invocation metric. These
were not POST/delete retries or production Lambda failures.

## Unchanged health and isolation

- All **13/13** Lambdas: `Active / Successful` before and after validation.
- All **13/13** retained approved `CodeSha256`
  `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=`.
- `TENANT_RESOLUTION_MODE=multi`: unchanged on all 13.
- API: `a022yxuiue / prod -> atxpw3`, unchanged.
- Exact staff route: resource `q1j32y`, `COGNITO_USER_POOLS`, authorizer
  `r0gk6r`, `AWS_PROXY`, integration POST to `togs-and-dogs-prod-admin`.
- Terraform state: serial **516**, lineage
  `7235fddd-c101-fe62-7669-7b7b3d858955`, unchanged.
- Lambda configuration and infrastructure baselines remained unchanged.
- Primary-tenant isolation: **PASS**. No `tog_and_dogs` workflow data was used,
  modified, or deleted; the approved write and cleanup were Alpha-only.

USMissionHero LLC remains the platform/operator; `tog_and_dogs` remains Ryan's
Togs & Dogs tenant; `test_tenant_alpha` remains internal validation only. No
tenant metadata, provisioning, Cognito, DNS, Stripe/Google configuration,
deployment, Ryan testing, Mobile distribution, or public App Store change was
part of the run or this closeout.

## What is closed, and what is not

The previously outstanding **successful authenticated persisted-write gap is
closed**: tenant Web UI -> real HTTP/API Gateway/Cognito -> admin Lambda ->
strict active-tenant resolution -> non-bypass entitlement -> Alpha DynamoDB
persistence -> successful UI result, followed by exact restoration.

This evidence supplements, and does not relabel, the earlier records:

1. [Gate-B reconciliation and API read-only validation](b1a-api-gateway-read-only-validation.md):
   Gate B exercised backend business logic with constructed direct-Lambda
   events; staff was seeded directly after the Decimal failure; M&G completion
   was required before approval; two approved Postmark deliveries and
   `calendar_skipped` were observed. The later real API check was read-only.
2. [Original Gate-C cleanup](b1a-gate-c-synthetic-cleanup.md): eight exact
   artifacts from the August run were removed under separate approval.
3. [P1 acceptance](p1-decimal-entitlement-serialization-production-acceptance.md):
   the guarded real-route 403 proved Decimal logging but deliberately stopped
   before persistence. Today's successful staff write closes that distinct gap.

**FULL END-TO-END B1A IS NOT CLAIMED.** Intake, Meet & Greet, approval,
asynchronous job creation, assignment, downstream notifications, and downstream
Calendar behavior remain unproven through the full real Web/API workflow.
Zero side effects on the staff-only route do not prove those downstream paths.

## Next-work classification

**A — future optional confidence test.** The approved minimum representative
write proof is complete, P1 is accepted, and the backend workflow already has
separate evidence. No specific newly released capability has been identified
that requires repeating the entire workflow as a release gate. This is not
classification C for the full workflow: unexercised external routes are not
automatically equivalent to direct-Lambda evidence.

Keep the remaining real-route workflow as optional, unexecuted confidence
work. If a future capability or full-E2E claim needs that evidence, define a
targeted gate with its own risk, notification/Calendar, exact cleanup, and
Matthew approval boundaries. Existing customer-tenant/PTM prerequisites remain
in force. Recommended next decision: select a separately scoped roadmap item,
such as repository-only PTM-0 source-of-truth reconciliation, without replaying
this test or starting any production workflow automatically.
