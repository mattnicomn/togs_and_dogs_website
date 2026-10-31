# Cancellation Adapter Compatibility Foundation - Inactive Acceptance

**Date:** 2026-10-31 (America/New_York). **Disposition:** `CANCELLATION_ADAPTER_FOUNDATION_INACTIVE_NOT_INTEGRATED`.
Matthew authorized SDK-free observation/commit contracts, synthetic legacy classification, field-level writer rules, mocked tests, continuity and one dependent Draft PR. No runtime wiring, migration, policy activation, real storage/provider or production operation.

## Dependency and resume checkpoint

Separate branch `codex/cancellation-adapter-foundation`, directly based on corrected PR51 `cafeba56735a34efe9b59fdf248e3f8835b8631b`, targeting `codex/cancellation-submission-contract`. Retains PR50 `2c5e68cddba1c54f08f00c71a6ef774134bf9cd6`, PR49 `5c1074efd297f40930639d62304504c54398452c`, PR48 `d6fa074ad59bcd748a0553d7a6a33f88832c81a5` and PR47 `efaa31cb3f12e7cdcc6fe9c1cfb32b15a2a15bee`. Separate PR46 remains `06ee9d628ac57d1a988e264ec74c26fe41174125`; main verified `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`. Exact new head/PR/check evidence belongs in the delivery record, avoiding self-reference.

Read [corrected PR51](cancellation-submission-contract.md#corrective-replay-checkpoint---2026-10-30), [PR50 atomic workflow](slice-2bc-atomic-workflow-contract.md), [PR49 onboarding](staff-onboarding-staging-recovery-contract.md), [PR48 inactive foundation](canonical-worker-identity-inactive-foundation.md), and [PR47 offline identity](canonical-worker-identity-offline-contracts.md). Their historical release outcomes and independent blockers are preserved. Latest recorded production acceptance remains W3-C2 within its approved scope, not this package.

## Readiness findings carried forward

Existing booking access permits owner/admin/staff and client booking-email matching; it is not immutable subject-to-client proof. Claims extraction does not authenticate credentials by itself. Role resolution has a legacy email fallback; item tenant ownership has a missing-company fallback; tenant-active checks can bypass/fail open. None is silently converted into trusted evidence or changed here. Production status/ownership/role/revocation semantics require explicit approval before any adapter is wired.

REQUEST creation lacks this selected workflow's incarnation/revision/lifetime protocol. Cancellation, review, assignment, job/PET/client linking, admin lifecycle, quote/payment paths, notification metadata and maintenance writers share REQUESTs. Older packages and untracked operational writers are not closed by adding one new Lambda path. Field-disjoint writes can still upsert or bypass identity retirement. Whole-store rollback or byte-identical recreation by an unfenced writer cannot be distinguished by these predicates. PR51's read_id/digest/verified flags alone do not prove coherent authenticated observations.

The [new foundation](../../src/backend/common/cancellation_adapter_foundation.py) and [writer rules](../../src/backend/common/cancellation_writer_inventory.py) are standalone standard-library modules. No source module imports them, and they do not import parent inactive contract modules. Parent import boundaries remain unchanged. Tests compose the contracts explicitly; merely packaging these files grants no runtime capability.

## Observation ports and trust boundary

`ObservationPort` specifies observation only; `VerificationPort` specifies provenance verification; neither has a production implementation. Query binds tenant/client/request, trusted issuer/principal subject, effective role, operation and exact reason digest. Principal observations carry concrete persisted booking identity bindings, tenant-active/revocation state and principal/tenant/revocation epochs. Observation carries REQUEST, lifetime, reservation and operation receipt as immutable typed snapshots, with an explicit observation interval and coherence claim.

Validation requires a non-default verifier, exact query/principal/target binding, current explicit lease interval, strict epochs/flags, and an exact `ObservationAttestation` returned by the verifier. Boolean true, client JSON, an arbitrary shared observation ID or a changed snapshot with an old fingerprint fails. Every relied-upon identity field must be present as a nonempty string matching the trusted principal binding. No names/email are used to manufacture canonical identity. Snapshot freezing preserves unknown dictionaries/lists and finite Decimal values without converting money/revisions through float.

The [test-only authority/commit port](../../tests/backend/cancellation_adapter_fakes.py) verifies issued immutable observations against its private in-memory registry and current synthetic security state. It copies all resource rows together for a modeled coherent snapshot. It attests a stored receipt only when its synthetic commit journal proves publication by the atomic fake writer; a prepared row plus unrelated revision progression is insufficient. This registry is synthetic provenance, NOT real authentication, a cryptographic storage signature, Cognito verification or AWS isolation proof. Tests can deliberately corrupt the registry to demonstrate that structural version checks still refuse bad receipts; a fully compromised trusted verifier cannot be repaired by a digest.

The fixture's five-tick lease and epoch rules are deterministic test parameters, not a new real freshness/revocation policy. A real server-owned verifier must enforce trusted issuer/token/principal/role/tenant evidence, current booking ownership, revocation and tenant-state freshness, protected storage provenance, and a defined coherent observation protocol. Separate reads or an identical read_id alone are insufficient. Cross-system identity freshness cannot be assumed atomic with database reads. Observation/verification dependencies must never be chosen or supplied by clients. No real adapter, credentials, production reads or SDK client are supplied here.

## Conditional commit port

`ConditionalCommitPort` defines an SDK-free interface with no execution implementation. `prepare_commit` returns an immutable inspectable command, never calls that port, and retains INACTIVE_NO_RUNTIME, SOURCE_STATUS_POLICY_PENDING, REAL_ADAPTER_PENDING, ALL_WRITERS_PENDING and retention/rollout blockers. An explicit synthetic source-status assumption/reference is mandatory; a structural classifier candidate is not cancellation eligibility. No business allowlist is adopted.

Command binds exact query, observation, source revision/incarnation, original timestamp/warning, fixed field-preserving set/append patch, create-only stored receipt and required atomic guards. Validation recomputes the command and refuses altered fields/guards/receipt/identity. It requires the exact existing REQUEST, strict expected revision/incarnation, source status/start date, actual booking identity fields, audit LIST-or-absent, marker absence, reservation absence, live permanent lifetime, create-only receipt and atomic REQUEST/receipt publication. Oversize refuses before commit. No defaults, enrollment, backfill or reservation/lifetime construction make a legacy row appear compliant.

Only the test fake implements commit. It bridges the validated command into PR51's unchanged four-item transaction shape and evaluates full conditions and actual UpdateExpression through pure Moto Item/parser/validator/executor helpers. It checks exact receipt and patch compatibility, preserving concurrent unknown fields and audit entries. No SDK client, AWS service/table, transaction invocation, external provider or network is used. The fake publishes copied rows and modeled journal at one logical point; this is not proof of real transactional durability or thread isolation.

Outcomes are COMMITTED, REFUSED or UNKNOWN. `OutcomeAttestation` must bind the exact command, logical operation and report; fabricated committed/refused reports and boolean attestations fail. COMMITTED additionally requires a verified current observation and exact stored receipt binding, original source + 1 committed revision <= current revision, correct immutable lifetime and original response. REFUSED requires authoritative non-commit AND quiescence, not merely one failed attempt. UNKNOWN never triggers another commit or a fresh operation key.

A second coordinator observing the same proven operation returns the stored result without another mutation/audit. A changed-payload key collision refuses; an unproven existing receipt remains UNKNOWN. Timeout before hypothetical publication and timeout after publication both return UNKNOWN; a later authoritative stored observation may resolve the latter, while a blind retry is blocked. Historical replay returns original message/urgent_warning without reopening later admin state. Rollback never deletes receipts or pretends delivered effects were reversed. This selected operation has no JOB/PET/Calendar/Cognito/notification effects at all.

## Synthetic legacy classification

| Representative shape | Disposition / required follow-up |
| --- | --- |
| Exact IDs, tenant, valid incarnation/revision, live witness, supported structural status, audit absent/LIST | Protected-path candidate only; still requires verified observation, explicit pending status assumption and all rollout gates. |
| Missing company metadata, incarnation, revision or witness | Staged adoption required; no tenant, revision, incarnation or witness defaults supplied. |
| Explicit IDs absent but legacy keys exist; BOOKED/SCHEDULED/JOB_CREATED or missing status | Legacy compatibility policy required; no key guessing or automatic alias normalization. |
| Linked profile differs from submission client | Legacy compatibility policy required; preserve provenance, never relink or move PET/client ownership. |
| NULL/malformed audit, invalid revision/incarnation, unknown status/ownership format | Manual investigation required, without repair. |
| Wrong tenant/client/request/key, any canonical/partial/NULL marker, any reservation, retired/reused/expiring/malformed lifetime | Protected refusal. |
| Unknown valid fields, including finite Decimal metadata | Preserved exactly; unknown fields alone do not authorize a write. |

Classifier returns all reason codes and the most restrictive applicable category: protected refusal, manual investigation, staged adoption, legacy policy, then candidate. Classification does not authenticate ownership and never edits its inputs. Multiple defects may therefore produce a stricter result than any single missing field. Unsupported/mixed storage shapes are not silently made current. Data prevalence is unknown: no real customer records were inspected.

## Field-level writer compatibility inventory

The executable [inventory](../../src/backend/common/cancellation_writer_inventory.py) has 26 named entries pinned to PR51 source call sites, each with exact file/function/line, target, read/write fields or bounded branch patterns, behavior, revision domain, preservation and coupling. [Tests](../../tests/backend/test_cancellation_adapter_foundation.py) verify paths/functions/call-site anchors and exercise each category. These are design requirements, not alterations to any writer or certified deployed reachability.

| Group | Entries / classification |
| --- | --- |
| Intake create and generic DB | Whole record or generic writes require lifetime/identity and field-preserving adaptation. |
| Submission, Calendar/failure/audit/approval metadata | Compatible only with specified atomic guards: existence/exact tenant/key, no upsert, selected revision/incarnation, reservation/lifetime, truthful refusal and no unconditional fallback. Disjoint fields alone are insufficient. |
| Review, assignment, job membership, admin rollup/lifecycle, PET links and child cascade | Coordinated complete affected-set and post-commit effect protocols required. |
| Client-profile linkage | Identity adaptation and booking-authorization invalidation required. |
| Admin purge and zombie cleanup | Unsafe delete/recreation until atomic retirement and permanent non-reuse are implemented and independently approved. |
| Quote/payment, Stripe/manual-external, targeted JOB/PET cleanup and malformed-audit cleanup | Explicitly excluded pending separate approval; preserve domain-specific revisions/semantics. Current REQUEST exclusions do not establish future journal-prefix safety. |

Every assessment remains activation_ready=False even if all proposed guards are supplied: runtime rollout, existing source behavior and all-writer evidence are not inferred from a checklist. Status/audit/identity conflicts are explicit. Field-disjoint metadata writes still require existence/lifetime protection, because an unguarded Update may recreate a missing row. Payment/quote revision domains are not this workflow revision; no unrelated commercial behavior change is authorized.

Known older source: documented non-admin PR22 RC `b94455ac530e3ecca9a2fc2ddc69ed54902b84db`, with later W3-C2 admin source `263b3e744a2815f0d9da781b2589ce643d2750f6`. Neither contains this protocol. Inventory explicitly retains old Lambda/alias/trigger/queued/in-flight execution, operational credentials/scripts/import/manual writes and cleanup/restoration as blockers. No live deployment inventory was performed, and tracked source cannot certify absence of untracked writers. The characterization test deliberately shows byte-identical recreation without witness retirement can still commit; global ABA is NOT solved.

## Validation and acceptance

**62 new foundation methods / 374 combined focused tests PASS** (312 inherited PR47-51 contracts). Tests cover complete and forged observations, wrong issuer/subject/tenant/client/request, stale epochs/leases, changed/removed/NULL identity, incoherent snapshots, uncommitted receipts, replay and source revisions, timeout/no retry, legacy classifier categories, witness conflict/retirement, reservation/marker races, concurrent unknown fields/audit, field-writer rules, old-version/operational gaps, ABA characterization, no mutation/effects on refusal and import/network boundaries. Actual PR51 expressions/patch/receipt compatibility are evaluated only in tests. Source modules use only the standard library; no production source imports them or any parent model under this package.

Fresh exact PR51 guarded baseline is **77 failed / 2376 passed**. Final guarded full suite: **77 failed / 2438 passed**, exactly 62 additional passes. All 77 sorted failure-summary signatures, including multiplicity, match that exact PR51 baseline; zero newly failing signatures. Existing Windows Overnight/DST baseline differences are retained, not repaired/suppressed. Python syntax, strict UTF-8, documentation links, sensitive-pattern review and scoped source/security review are required. Author-agent self-review is not independent human approval.

Standard GitHub CI targets main only, so this PR51-dependent Draft lacks hosted backend/web/mobile/shared jobs. Security is recorded only as actually observed at the exact delivered head. No trigger/base/ruleset weakening. Canonical required-check/CLEAN/RC integrity/structured Matthew MERGE AUTHORIZATION gates remain unchanged; PR45's proposal is inactive. PR19 remains source-only reconstructed, original plan/ZIP MISSING; retained release/rollback evidence is untouched.

## Remaining approval boundary

Before any future handler integration: approve source-status/resubmission, role/fallback and linked-client compatibility, real revocation/freshness policy, key/API/pending UX and retention/recovery. Implement and independently validate real server-owned access/provenance/coherent-read adapters; resolve legacy classification/adoption without guessing; close or explicitly contain every unsafe writer and mixed version; prove witness/receipt protection and restoration behavior; verify the exact principal's transactional IAM and all serialization/item limits; define rollout/drain/rollback and secure journal retention. No actual permission, schema, lifecycle record or migration is changed by this package.

The smallest future endpoint remains cancellation-request submission only, excluding final cancellation, child/PET mutations, provider dispatch, Cognito and owner execution. It is not ready to wire. The next owner authorization should name one remaining adapter/writer/compatibility slice and its pending policy decisions explicitly; it must not treat this Draft as deployment, migration or production-testing authority.

Stop at this dependent Draft. No merge, Ready, handler/client wiring, AWS/Terraform/IAM/Cognito, production/data operations, live receipt/reservation/enrollment, Stripe/tenant, Android/distribution or Ryan testing occurred. Exact ending commit/head/PR/checks are in the delivery record; parents/main and all retained evidence are preserved.
