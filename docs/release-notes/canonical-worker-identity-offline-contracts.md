# Canonical Worker Identity — Slice 1 Offline Contract and Test Record

**Date:** 2026-10-29 (America/New_York)
**Disposition:** `WORKER_IDENTITY_SLICE1_OFFLINE_ONLY_NOT_INTEGRATED`
**Base:** main `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`.
**Authority:** local pure helpers, synthetic tests, documentation and Draft PR delivery only. No live authorizer, handler, assignment writer, schema, IAM or data change.

## Approved requirement and dependency

Matthew approved: an owner may Start/Complete only an exact child visit assigned to that owner's verified worker identity. Ownership is not permission to execute every tenant visit. Email, display name, guessed IDs and client role assertions must never qualify an owner.

This Slice 1 is independent of unmerged [PR46](https://github.com/mattnicomn/togs_and_dogs_website/pull/46), reviewed at `06ee9d628ac57d1a988e264ec74c26fe41174125`. It does not copy or change PR46 runtime code. Future mobile integration must explicitly depend on its then-verified head and preserve child-bound notes, confirmed started state, exact-child resolution and safe refresh. See [PR46's acceptance tracker](https://github.com/mattnicomn/togs_and_dogs_website/blob/06ee9d628ac57d1a988e264ec74c26fe41174125/docs/release-notes/android-booking-workflow-remediation.md).

## Current-source findings (not changed)

- Authenticated backend identity comes from authorizer claims; mobile exposes username/email plus cached role, not a verified worker execution context.
- STAFF records carry staff identity and Cognito linkage, but assignment `worker_id` is email-shaped. The mobile picker can fall back to names; that is not owner identity proof.
- Start/Complete accept owner/admin/staff today; assigned-worker email checks apply to staff. Start conditions do not fence reassignment, while Complete uses separate read/update operations.
- Existing assignment validation can proceed when its lookup throws. New canonical eligibility must fail closed; this offline package does not repair or reuse that path as proof.
- Parent rollup, review/cascade and assignment paths are separate writers. A new read endpoint alone cannot enforce mutation-time ownership.

## Proposed schema and identity contract — not adopted or migrated

| Record | Proposed identity/invariants |
| --- | --- |
| WORKER | Server-issued opaque `wrk_` + 32 lowercase hexadecimal characters; tenant; stable staff reference; explicit active/assignable flags; monotonic version |
| PRINCIPAL_WORKER_LINK | Trusted issuer + subject + tenant; canonical worker/staff references; explicit active flag; monotonic version; enrollment/audit provenance |
| STAFF | Add canonical worker pointer; preserve existing staff ID and history; reciprocal worker/staff references must agree |
| JOB | Add `assigned_worker_id`, canonical assignment contract/version, monotonic `assignment_revision`; preserve existing email-shaped `worker_id` for legacy compatibility |

Use tenant-partitioned WORKER and principal-link items, with deterministic principal key derived from issuer/subject. Enforce one active link per principal per tenant transactionally; no initial GSI is assumed. ID generation, uniqueness enforcement, parsing and JWT verification are NOT implemented by these tests. Canonical worker IDs do not change on rename/email change. Link replacement or pool migration requires separate verified enrollment, revocation/versioning and audit; it is not automatic relinking.

An owner needs independently verified linkage to an active assignable worker before canonical child assignment. Merely being owner, receiving a token or sharing an email with an old STAFF profile is insufficient. Who may enroll/link, proof requirements and approval workflow remain pending. No self-enrollment or Cognito group change is authorized.

## Executable offline specification

[Pure test-only model](../../tests/backend/worker_identity_contract.py) and [synthetic regressions](../../tests/backend/test_worker_identity_contract.py) live under tests/backend, outside runtime source. Only standard-library imports; no AWS SDK, environment reads, I/O, JWT processing, DB client or handler integration in the model.

The frozen records represent already-validated synthetic snapshots. Boolean trust flags are test preconditions, not security attestation: runtime must derive claims/role/tenant through a trusted authorizer and configured issuers/client/token checks, never accept these records or flags from a request body. Defaults do not establish caller trust, active linkage, canonical assignment or hydration. The active-link count represents a future uniqueness proof, not a trusted client field.

`assess_owner` checks trusted/current caller, explicit owner role, tenant equality, exact child/parent identity, hydration, canonical non-email assignment, unique active linkage, issuer/subject equality, active/assignable worker, reciprocal identities and exact valid revision. It returns:

| Outcome | Meaning |
| --- | --- |
| ELIGIBLE_AT_SNAPSHOT | Approved requirement satisfied in the supplied synthetic snapshot; NOT mutation authority |
| DENIED | Explicit missing/mismatched/inactive/unverified/stale evidence; no grant |
| POLICY_PENDING | An unresolved execution/replay policy; no grant |
| EXISTING_STAFF_PATH_REQUIRED | Delegate to unchanged established staff behavior; never treat as authorization |

Internal denial categories include untrusted/expired caller, missing principal/tenant, role not owner, wrong child/parent, wrong tenant, unhydrated visit, legacy-only/unassigned visit, ambiguous/unlinked/revoked linkage, inactive/unassignable worker, missing/invalid canonical identity, reciprocal/principal mismatch, stale/invalid revision, invalid state and changed commit fence. Runtime error mapping must avoid cross-tenant disclosure; these test reasons are not a proposed public diagnostic API.

Email cannot qualify owner execution even when disguised as canonical worker ID. Existing staff authorization is not duplicated or tightened here; the model delegates it rather than claiming to reproduce it. Existing admin behavior remains outside this new owner grant and needs a compatibility decision before integration.

## Proposed API envelopes — not live routes or published contracts

- Caller context: trusted tenant/role, verified linked canonical worker ID, linkage/worker versions and eligibility. A client-supplied worker, subject, email or role cannot establish this context.
- Exact-child read: job/request/tenant binding, canonical assigned worker, assignment contract version (only version 1 modeled), monotonic revision and authoritative execution state. Missing/future contract versions are ineligible.
- Owner Start/Complete proposal: existing exact job/request operation plus expected assignment revision and durable operation identity; Complete binds notes to that child. Server derives the caller worker; no client worker selection. Legacy staff payload compatibility remains separate and unchanged.
- Response: authoritative state/timestamps, assignment revision, operation result and explicit replay/conflict outcome once its policy is ratified. Error mapping must not disclose other tenants; final transport status mapping and replay response schema remain pending.

No HTTP route, serializer, client configuration or application payload changes exist in Slice 1. Later account/pool migration needs verified link replacement while retaining canonical worker identity; bulk email backfill and copying production data to DEV are not authorized. API routing, IAM and any GSI need separately reviewed infrastructure scope; no new index is assumed by this design.

## Atomic enforcement, concurrency, audit and replay contract

`capture_fence` / `assess_atomic_fence` model binding to principal, canonical worker/staff, child/parent/tenant, linkage/worker versions, assignment revision and parent revision. This is an in-memory comparison, NOT atomic storage enforcement. A backend transaction must independently condition all participating records, active flags, trusted membership/role, parent identity/state and valid child transition at commit time. Parent revision alone is not proof of tenant, state or membership.

Place conditions on each updated item; do not issue ConditionCheck plus Update for the same item. Link/worker deactivation must advance versions. Missing records, stale versions, partial lookup, conditional failure and ambiguous tenant fail closed. No retry may switch the intended child, actor, assignment revision or notes to a different operation.

Assignment-writer coverage required before activation:

| Writer family to audit | Required postcondition |
| --- | --- |
| Canonical assignment/reassignment handler | Validated canonical worker + monotonic revision in the conditional write |
| Legacy assignment clients/handler | Invalidate canonical owner eligibility and advance revision; no silent email conversion |
| Review rollback/unassign and REQ→JOB cascade | Advance assignment/parent versions and clear/update canonical assignment consistently |
| Generic admin job updates, imports, scripts and repair paths | Enumerate and constrain; no writer may preserve a stale canonical grant |
| Staff/owner completion and cancellation | Participate in the agreed parent/child version protocol without changing staff authorization |

This is a minimum inventory requiring closure, not a claim that every writer is already audited or modified. `legacy_assignment_invalidation` models the postcondition of an already-authorized write; it does not authorize reassignment, especially after Start.

`completion_rollup_cas` demonstrates no lost sibling completion under parent compare-and-swap and no duplicate counting. It models set semantics only, NOT a production list-to-set migration. Actual child completion, rollup and required audit/outbox must commit consistently, with all relevant writers following the same version protocol and transaction size/throughput reviewed. The tests do not prove DynamoDB transaction behavior or current production correctness.

Bind audit/idempotency to tenant, verified principal, canonical worker, exact child, action, assignment revision and payload digest. Preserve original timestamps, one completion/count/audit effect, and per-child notes. Same operation identity with a changed payload must conflict. DynamoDB client-token windows alone are not durable business idempotency. Actual receipt retention, replay response permissions, conflict-retry rules and audit/outbox mechanism remain design decisions; no receipt DB implementation or production audit change exists here.

## Explicit pending policy decisions — no runtime fallback

- Enrollment operator, immutable linkage proof, replacement/revocation and ownership of uniqueness.
- Owner Complete without recorded Start: model returns POLICY_PENDING.
- Replay response policy, including access to old receipts after revocation/reassignment: pending. A revoked caller cannot qualify for a NEW mutation; this does not decide disclosure of an old receipt.
- Reassignment after Start, preservation/transfer of execution history and who may perform it: pending; modeled started/revision disagreement cannot grant execution.
- Existing admin compatibility, trusted role precedence and owner+staff dual-role handling: no owner-to-legacy-staff fallback may evade the restriction; runtime adapter still requires approval.
- Parent version protocol, retry/repair behavior, batch size, rollout controls, migration/backfill and rollback retention.

## Validation and evidence

Run offline with Python 3.11 standard library: `python -B -m unittest discover -s tests/backend -p test_worker_identity_contract.py -v`. The existing backend pytest CI also collects these unittest cases without CI configuration changes. Local result: **57/57 PASS** on Python 3.11, standard library only. Exact CI count/run/head is recorded in the Draft PR evidence; no full application suite was rerun locally for this test-only/documentation slice.

Tests cover positive linked owner Start/started Complete; tenant/issuer/subject and reciprocal mismatch; missing/expired/untrusted identity; denied roles; delegated staff; no email/name qualification; inactive/revoked/ambiguous linkage; wrong child/parent; legacy/unassigned/unhydrated jobs; invalid/stale revision and terminal states; immutable records; pending policies; deterministic reassignment/ABA/revocation/disable/version races; replay non-grant; legacy invalidation; sibling CAS conflicts and duplicate counting. A static import-boundary test checks that runtime Python source does not import the test model.

No sleep, external account, customer fixture, token, screenshot, private path or credential is used. Race tests are explicit before/after snapshots, not scheduling simulations or proof of real transaction isolation.

## Subsequent slices and approval gates

1. **Slice 2 proposed:** local canonical identity/linkage and assignment schema adapters, uniqueness and fail-closed writer integration, with synthetic tests; no live enrollment/backfill. Requires explicit approval of pending enrollment/identity decisions and permission to modify backend paths. Keep owner execution disabled; stop if writer coverage cannot be closed.
2. **Slice 3:** separately approved transaction-time owner mutation enforcement, audit/replay and compatible parent rollup. Requires the remaining policy/concurrency decisions, offline compatibility evidence and independent review.
3. **Slice 4:** mobile server-verified context and narrow gate, explicitly dependent on PR46's then-current reviewed branch/head if still unmerged. Preserve its note, replay, selection and refresh fixes.
4. **Release:** separately approve AWS/IAM/API routing/schema deployment as needed, enrollment/backfill, exact release artifacts, device testing/build/distribution and Ryan testing. No approval is supplied by this document.

Additive readers/fields precede writers; historical email data stays readable. No automatic backfill may grant owner execution. Rollback must preserve records/history and disable the new owner path rather than restoring broad owner execution. Detailed operational rollback and mixed-version writer compatibility must be reviewed before release.

PR43/44/45/46, worktrees, original/rollback evidence and historical release outcomes remain unchanged. Canonical CLEAN/RC integration gates and separate MERGE AUTHORIZATION still apply; inactive PR45 cannot approve an exception. No merge, Ready, policy activation, runtime integration, migration, AWS/Terraform, production, tenant, quote/payment, mobile build/distribution or Ryan action is performed.

## Corrective offline checkpoint � 2026-10-29

The original 57-test result above is historical. Readiness review found coercive equality for started assignment provenance and operation-unbound snapshot fences. The correction validates every domain revision as an exact positive integer bounded by 2**63-1; explicit DB-boundary parsing accepts finite integral Decimal values only, never floats, booleans or strings. Unsupported contract versions remain denied. This bound is a representation limit, not an adopted business policy.

Fences now bind action, opaque operation identity, a 64-character lowercase SHA-256 payload digest, assignment revision and execution revision, in addition to principal/worker/child/parent and version fields. Operation fields are required; no default operation identity is manufactured. Payload hashing and trusted operation derivation remain future adapter obligations, not client assertions. The fence is still only a synthetic comparison, not a capability, durable receipt or database transaction.

New regressions cover both directions of Start/Complete reuse, changed operation/payload, stale execution versions, bool/int equality, floats, Decimal parsing, malformed values and forged fence revisions. Policy-pending outcomes remain non-grants. No runtime import, handler, RBAC, enrollment or storage change is made. The corrected immutable head, exact test count and CI comparison are bound in PR47's delivery record. Slice 2A will branch from that corrected head as an explicitly dependent, inactive foundation; it cannot activate owner execution or resolve the pending policies or canonical integration/RC gates.
