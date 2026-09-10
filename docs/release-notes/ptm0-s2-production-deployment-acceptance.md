# PTM0-S2 production deployment and acceptance disposition

Date: 2026-09-09

S2A.3 and S2D.1: **DEPLOYED — NOT FULLY PRODUCTION-ACCEPTED**.
S2 production acceptance: **PARTIAL / PRELIMINARY — P1 only**.

This record preserves Matthew's independently approved checkpoint. Preparing this
documentation performed no production operation, functional test, fixture creation,
or implementation. Historical S1 acceptance remains valid.

## Approved source and deployed artifact

- Main: `0f50443ebe5325ce8f2c926fe716841abfd14a73`.
- Isolated S2 RC source: `b32b374e45cac09dc7006047954ff60c041b0bf0`.
- RC tree: `e8c1fcbef2e8bc28c8fc690e23293321f2664ea4`.
- Prior deployed S1 baseline: `c31be0ab6f95ba77707f33980cadc0c998dda6e3`.
- Canonical ZIP SHA-256:
  `0849407128C4ADC85F0DB5B6A4BEB78A28E8F09EAA600B4AD10C7167DA421954`.
- Lambda CodeSha256: `CElAcSjErchfDbW2pL63iijo8J6qYAtK0QxxZ9pCGVQ=`.
- Content-manifest SHA-256:
  `B58B8CA611FA0AC9194C6E1EAEF7D45F54D56866CF286875A369AB9A2659AED8`.
- ZIP: 143876 bytes, 41 entries; retained at
  `scratch/ptm0_s2_rc/package/ptm0-s2-rc1-b32b374-canonical.zip`.

Production disposition: `PTM0_S2_RC1_INDEPENDENT_PRODUCTION_DEPLOYMENT_APPROVED`.
The exact approved canonical artifact was independently verified on all 13
production Lambdas in account `358604342897`. All reached Active/Successful with
the approved CodeSha256. Names have prefix `togs-and-dogs-prod-`: intake, admin,
review, assign, job, google-auth, pet, cancellation, device, ses-feedback,
postmark-webhook, stripe-webhook, platform.

Only the security backport was deployed, not main wholesale. Its seven runtime
changes are google_calendar and admin/assignment/cancellation/intake/job/review;
unrelated later-main scheduling remains excluded. Deployment was code-only, with
no Terraform operation or configuration change. `TENANT_RESOLUTION_MODE=multi`
remained unchanged and was reconfirmed by P1. Historical S1 Terraform-state records
are not a current S2 state attestation; no state reconciliation is claimed.

## Acceptance and fixture discovery

P1 disposition: `PTM0_S2_P1_INDEPENDENT_READ_ONLY_ACCEPTANCE_APPROVED`.
Read-only checks confirmed package/health and strict multi on all 13 functions.
Exact-key `test_tenant_alpha` metadata exists with consistent PK/SK/company
ownership. All provider/calendar binding fields are absent; Alpha remains
unconfigured. No secret was selected or described; secret-value access was zero.
This proves prerequisites, not successful provider or workflow execution.

Fixture discovery disposition:
`PTM0_S2_P2_P5_FIXTURE_DISCOVERY_INDEPENDENTLY_APPROVED`.
One projected exact-key read confirmed the documented synthetic Alpha request is
absent, consistent with the [B1A cleanup](b1a-gate-c-synthetic-cleanup.md).
No scans, broad production searches, functional invocations or writes occurred.

| Case | Disposition | Reason |
| --- | --- | --- |
| P2 — invalid ownership/event-reference rejection | DEFERRED / UNEXECUTED | Previously documented controlled Alpha request was cleaned up; no approved replacement exists. |
| P3 — missing envelope cannot create jobs | DEFERRED / UNEXECUTED | No approved existing unlinked Alpha request fixture exists. |
| P4 — safe linked-job replay | DEFERRED / UNEXECUTED | No approved existing parent/linked-job Alpha fixture exists. |
| P5 — admin ownership denial | DEFERRED / UNEXECUTED | No documented controlled synthetic foreign-tenant fixture exists; discovery had insufficient evidence for an authorized exact key. |

These deferrals are **NOT failures** and **NOT successful functional production
acceptance**. Discovery was bounded by documented keys, not an exhaustive inventory.
No ordinary primary-tenant customer record may substitute for a controlled fixture.

No production fixture will be created merely to complete P2–P5 unless Matthew
separately and explicitly approves production fixture creation:
`MATTHEW_APPROVAL_REQUIRED_FOR_PRODUCTION_FIXTURE_CREATION`.
Subsequent functional execution and cleanup require bounded authorization as well.
No Ryan/customer workflow was used for this S2 acceptance work.

## Evidence and remaining work

Existing offline/package evidence remains valid: approved canonical package;
41-entry source/content verification; 13 Lambda import checks; focused packaged
security suite **234 passed, 0 failed, 0 skipped, 21 warnings**. The source backport
regression comparison passed 252 cases against both candidate and untouched S1.
These results do not replace deferred production functional evidence.

Retained local evidence: `scratch/ptm0_s2_rc/package/packaging-record.md` and
`identity.json`; `scratch/ptm0_s2_rc/deployment/deployment-record.md` and
`deployment.json`; `scratch/ptm0_s2_rc/p1-read-only-evidence.json`. Fixture discovery
and independent approval are recorded in task history; discovery intentionally
wrote no repository evidence file. This release note preserves their disposition.

Recommended next step: separately authorize a narrow **S2B planning/contract review**
based on the [S2 architecture findings](../reviews/ptm0-s2-f02-architecture-source-of-truth-review.md).
Inventory passive provider-status and tenant-info/control-plane consumers; define
explicit fail-closed tenant authority, no refresh/save/revoke/Calendar side effects
on passive reads, compatible unknown/stale responses, and tests against the deployed
backport. Preserve boundaries with later OAuth/control-plane slices. Do not implement
or probe production as part of this documentation step.

- S2 acceptance: **PARTIAL / PRELIMINARY — P1 only**.
- S2A.3 and S2D.1: **DEPLOYED — NOT FULLY PRODUCTION-ACCEPTED**.
- S2B, S2C, S2D.2, S2E: **NOT STARTED**.
- F02: **INCOMPLETE**. PTM-0: **INCOMPLETE**.

No Stripe live work, App Store/TestFlight/mobile distribution changes, Ryan tester
changes, second-tenant creation or unrelated production activity is authorized.
This documentation update is unstaged for independent review; no commit/push/merge.
