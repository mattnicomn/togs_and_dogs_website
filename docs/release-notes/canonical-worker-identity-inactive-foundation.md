# Canonical Worker Identity — Slice 2A Inactive Backend Foundation

**Date:** 2026-10-29 (America/New_York)
**Disposition:** `WORKER_IDENTITY_SLICE2A_INACTIVE_NOT_INTEGRATED`
**Dependency:** corrected PR47, immutable head `2913f70c955ba6cbc58eaae3df07e974b8a4be30`; original PR47 head `ee28f6279d0203842aa7d0319d56a33b7828de50` remains historical. This branch descends directly from corrected PR47 and its Draft PR targets `contracts/owner-worker-identity-slice1`, not main. Main was verified at `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`. Exact delivery head/PR/check results are bound in the GitHub delivery record.

## Authority and implementation boundary

Matthew authorized local offline contract correction and inactive backend modules with synthetic tests only. No handler imports these modules. No SDK client, transaction invocation, credentials, environment read, enrollment, schema/data migration, API, RBAC or production change exists here. Merely placing files under backend/common does not enable them; future packaging/release still requires separate review. Do not import/wire them from runtime paths under this authorization.

Approved requirement: owners may execute only exact child visits assigned to their verified worker identity. The foundation never grants execution: even a structurally consistent linkage returns `POLICY_PENDING`. Principal construction assumes upstream signature/client/token/membership verification; it validates trusted issuer/subject/tenant shape but cannot prove its own upstream precondition. Never deserialize a client-supplied Principal or trust flags as authority.

## Modules and proposed schema

- [Identity contracts](../../src/backend/common/worker_identity.py): tenant/opaque-ID validation, explicit finite integral Decimal conversion, strict versions/flags, deterministic issuer+subject principal key, worker/link/STAFF consistency and sanitized failure categories.
- [Assignment adapters](../../src/backend/common/assignment_contract.py): exact persisted child/parent keys, tenant/client/membership binding, canonical version/revisions, Start provenance and operation/action/payload/revision binding. Legacy email never becomes canonical identity. Legacy STAFF fields are not copied into identity proof.
- [Inactive store builders](../../src/backend/common/worker_identity_store.py): pure construction of low-level DynamoDB request dictionaries. `InactivePlan` has a request plus mandatory unresolved blockers, no execute method. It is not an authorization/capability; returned dictionaries are inspectable design artifacts, not approved writes.

Proposed WORKER and principal-link records use `COMPANY#<tenant>` partitions, explicit entity/contract version, opaque worker ID, stable STAFF reference, active/assignable flags and monotonic versions. STAFF adds a canonical worker pointer and identity revision. JOB adds canonical worker, assignment contract/revision and execution revision; Start provenance uses canonical started worker/revision. Parent adds workflow revision while preserving list membership storage. These are inactive record adapters, not adopted live schema or migrated records.

Domain revisions reject bool, float, strings, fractional/non-finite/negative/zero/out-of-range values. Only the explicit storage boundary converts finite integral Decimal to exact int. The representation ceiling is 2**63-1, with overflow denied. Version 1 is the sole modeled contract. Missing/unknown/malformed records fail closed; internal reasons are not a public error-disclosure API.

## Transaction shapes and limitations

Create-only linkage plan: conditional Put WORKER + conditional Put deterministic principal link + conditional STAFF pointer/version update. Principal key contention prevents two proposed creates from claiming the same tenant/issuer/subject; STAFF pointer absence and expected identity revision prevent overwrite. This is request-shape evidence, not tested database isolation. No relink or existing-worker enrollment path is implemented. Reverse worker-to-principal cardinality remains pending, not implicitly approved by this create-only shape. Enrollment provenance/actor authorization/audit/receipts must be resolved before any execution.

Assignment plan: condition-check current worker and STAFF eligibility/version/linkage, conditional exact JOB update, conditional parent revision update. Conditions bind tenant, child/parent/client IDs, assignment and execution versions, prior assignment, contract version, status, absence of Start and parent child membership. Assignment revision increases on every modeled write, including assigning the same worker again; ABA cannot reuse the old revision. Parent CAS serializes competing siblings with current membership. Every plan retains actor authorization, policy, writer coverage, audit/receipt and presentation-compatibility blockers.

DynamoDB structure uses one action per distinct item; conditions belong on each updated item, not a second ConditionCheck for the same item. No transaction uses an index or BatchWriteItem. Botocore validates parameter structure without a client/network call; expression token/alias coverage and exact conditions are asserted separately. No service-side expression evaluation, real transaction isolation, IAM permission, throughput, audit durability or business idempotency is claimed. The last assignment operation/digest fields are provenance only, not durable receipts or exactly-once enforcement. See [AWS transaction constraints](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/transaction-apis.html). Additional transaction size/item-limit and contention review remains required before runtime adoption.

## Writer inventory — unresolved integration gate

| Writer | Current source / required follow-up |
| --- | --- |
| Assignment handler | Email lookup can fail open; separate child/parent writes. Route all canonical changes through reviewed fail-closed conditional writers. |
| Review handler | Parent assignment set/remove, completion and cascade must participate in lifecycle/revision protocol; prevent parent completion bypass. |
| REQ-to-JOB cascade | Unfenced per-child updates and tolerated partial failures; canonical invalidation/parent coordination required. |
| JOB creation | Conditional creation and parent membership protocol; never overwrite existing assignments. |
| Admin Start/Complete | Existing broad owner/admin path, separate completion/rollup; later exact-child authorization transaction required. |
| Admin archive/delete/unarchive/purge | Prevent stale eligibility resurrection and unversioned parent/child lifecycle changes. |
| Cancellation | Parent/cascade race protocol, including cancellation versus Start/Complete. |
| STAFF create/onboard/link/edit/disable/unlink/delete | Eligibility/linkage versions must change atomically or deny canonical records; full-record puts cannot erase metadata. |
| Scripts/repairs/imports | Seed and maintenance writers must exclude canonical records or use separately approved adapters. No dedicated assignment-import endpoint identified; external/manual writers not ruled out. |

No writer above was changed. Generic DB helpers remain unchanged. Coverage is not closed, so owner execution and canonical writes cannot be activated. Existing legacy staff behavior is unchanged; no email backfill or owner-to-staff fallback is introduced.

## Policies still pending

Proposed test assumptions only: no owner Complete without Start, no ordinary reassignment after Start, no dual-role owner fallback, revoked users cannot make new mutations, canonical writes fail closed. None becomes a live policy through this package. Owner execution remains pending, including well-formed cases.

Matthew must decide enrollment operator/proof, link replacement and reverse cardinality, admin compatibility, trusted role/revocation source, replay/receipt disclosure after revocation, exceptional started-visit recovery/cancellation, audit/outbox durability, retry/parent protocol, receipt retention, mixed-version rollout and rollback compatibility. Unknown decisions cannot grant eligibility.

## Validation and acceptance

Focused Python 3.11 offline result: **116 passed**, comprising corrected PR47 **67** plus foundation **49**. Synthetic suites cover parsing, tenant/issuer/subject, canonical/legacy boundaries, dual-role non-fallback assumption, inactive/revoked linkage, uniqueness contention keys, pointer no-overwrite, stale versions/ABA/parent races, started/terminal non-grants, exact transaction conditions, duplicate-item rejection, operation/payload binding, non-mutating builders, and static unwired/no-SDK/import boundaries. Three request variants (linkage, assigned child and explicit NULL unassigned child) pass botocore's TransactWriteItems input-shape validation without a client or request.

Full guarded backend baseline: corrected PR47 77 failed / 2131 passed. Final foundation: **77 failed / 2180 passed**, all 77 full failure-summary signatures identical to corrected PR47; 49 additional passes and zero newly failing tests. Three local-only failures versus Linux CI are existing Overnight/DST cases present in both local runs. Corrected PR47 CI run 40974366467 reports 74 failed / 2134 passed, with all 74 full failure-summary signatures unchanged from original PR47 run 40972055556; web remains 54 errors / 9 warnings with all 63 diagnostics identical. Mobile typecheck/tests, shared and security pass. Final focused coverage is 116 tests (67 corrected contracts plus 49 foundation cases). Exact final delivery heads/checks are bound in the Draft delivery record. The existing workflow filters pull requests to main, so this dependent-base Draft does not trigger the standard web/backend/mobile/shared workflow. No workflow, ruleset or base was altered to manufacture a green result. Security checks are reported as actually observed. This gap requires normal CI revalidation at a future approved base transition; local tests do not substitute for all merge gates.

Author-agent self-review only; no independent human review claimed. No device, build, distribution, Ryan test or live integration validation performed.

## Migration, rollback and next approval gate

Additive readers precede writer rollout; email-only jobs remain owner-ineligible. No automatic enrollment or backfill. Prevent old writers from preserving a canonical grant; do not activate until all writer paths are covered. Rollback must retain immutable identity/revisions/history and disable the owner path, never restore broad owner execution or old unfenced writers. No rollback operation is performed here.

Future mobile integration separately depends on [PR46](https://github.com/mattnicomn/togs_and_dogs_website/pull/46) at reviewed head `06ee9d628ac57d1a988e264ec74c26fe41174125`, if still unmerged. Preserve exact-child notes, started-state synchronization, stale/refresh/replay guards; Android build/distribution/Ryan testing remain separate approvals.

Next package requires explicit Matthew policy decisions and exact file authorization for assignment, lifecycle and STAFF writer integration; stop on incomplete coverage, schema ambiguity or backend authorization expansion. Later owner execution/receipts/rollup, mobile context, deployment/enrollment/migration, device acceptance and distribution are distinct gates. PR43/44/45/46 and retained evidence stay unchanged. PR19 original historical plan/ZIP remain MISSING; source reconstruction is not artifact recovery. CLEAN/RC and structured MERGE AUTHORIZATION gates remain active; proposed PR45 policy is not activated.

Resume: retain corrected PR47 and this separate dependent Draft; exact head/CI evidence lives in their delivery records. No merge, Ready, AWS/Terraform, production, payment/Stripe, tenant, W1, Ryan, mobile or policy activation was authorized or performed.
