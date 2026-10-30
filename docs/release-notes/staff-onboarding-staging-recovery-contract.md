# STAFF Onboarding Staging and Recovery — Local Contract and Acceptance

**Date:** 2026-10-30 (America/New_York)
**Disposition:** `STAFF_PROVISIONING_CONTRACT_MOCKED_NOT_INTEGRATED`
**Authority:** Matthew explicitly approved local-only contract implementation, mocked tests, continuity and one dependent Draft PR. No live operations or deployment.
**Base:** verified PR48 `d6fa074ad59bcd748a0553d7a6a33f88832c81a5`, branch `codex/worker-identity-foundation`; PR47 remains `efaa31cb3f12e7cdcc6fe9c1cfb32b15a2a15bee`; PR46 remains `06ee9d628ac57d1a988e264ec74c26fe41174125`. Main verified at `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`. Current head/PR and actual check evidence are bound in the delivery record to avoid a self-referential source hash.

## Investigated source and boundary

The existing admin handler is unchanged. Profile-only create writes STAFF directly; onboarding/create_or_link creates Cognito identity/group before its STAFF put; existing-user fallback can resolve by email and add a group before persisting a link. Manual link similarly changes group before the profile write. Disable/enable, deletion and edit/security paths contain additional external-before-write sequences. Invitation dispatch follows the onboarding put but lacks this proposed durable outbox contract. Current duplicate display-name/email and Cognito-sub checks are query/read checks; tier limits count active legacy staff. These observations are source evidence, not live reproduction or a new permission grant.

[Pure contract](../../src/backend/common/staff_provisioning_contract.py) is standard-library-only and imported by no runtime module. It does not import PR48's inactive helpers, preserving their unwired boundary. [Synthetic persistence/identity/invitation doubles](../../tests/backend/staff_provisioning_fakes.py) and [acceptance regressions](../../tests/backend/test_staff_provisioning_contract.py) implement the mocked coordinator only under tests. No SDK/network/client, database, Cognito group or account, invitation or reservation is used outside memory.

This package is not a live replacement for create, create_or_link, link_existing, edits or invitations. Existing handler/auth/tenant/role/assignment/entitlement and legacy STAFF behavior is byte-for-byte unchanged. Protected-account checks and established owner/admin admission are modeled as server-verified preconditions; client JSON cannot establish them. The initial mock supports target role staff only; owner/admin target-role staging remains policy pending rather than broadening privileges.

## Internal lifecycle and eligibility

| Internal state | Meaning | Active/assignable |
| --- | --- | --- |
| PROVISIONING_PENDING | Conditional profile/operation/uniqueness/quota admission has committed in the simulated store | Both explicitly false |
| IDENTITY_PROVISIONING | Durable identity/group intent or confirmed identity awaits reconciliation/finalization | Both explicitly false |
| PROVISIONING_FAILED | Known failure, ownership conflict, revocation or abandonment | Both explicitly false |
| ACTIVE | Verified identity binding and group confirmation persisted; outbox created in same simulated commit | Active true; assignability follows approved request flag |

These are proposed internal provisioning states, not request/booking statuses or live schema adoption. ACTIVE means STAFF profile provisioning only: it does not prove Cognito account confirmation, successful authentication, invitation delivery, password completion or portal access. `PROFILE_READY_ONLY` is not backend assignment permission. Owner execution always returns false; no canonical worker enrollment, assignment or execution gate is activated. Legacy dictionaries are delegated to existing behavior rather than reinterpreted or mutated.

Pending profiles always carry explicit false flags; a future adapter must never omit them and rely on today's legacy default-true checks. Existing STAFF records cannot be auto-enrolled or email-promoted. Reader/edit/assignment integration and partial-marker refusal remain separately gated Slice 2B work.

## Persistence, uniqueness, reservations and concurrency contract

The modeled first commit contains: exact tenant/STAFF/incarnation profile; stable operation receipt bound to the complete request and initiating subject; tenant-scoped normalized display-name/email uniqueness digests plus opaque target handle; versioned tier-capacity admission; and permanent exact-key reservation. A duplicate operation with identical input returns the same profile; changed payload, target, initiating subject or tenant conflicts. Real adapters must compute normalization/digests and request hashes from validated server input, not trust client hashes or proof flags.

Quota admission compares an authoritative tier/count snapshot and serializes concurrent requests through a quota revision. Active legacy count plus outstanding staged/active profiles cannot exceed the cap. Pending/failed/abandoned claims remain conservatively held in this model; automatic slot/uniqueness release is deliberately absent and needs an approved recovery policy. Existing active-only production counting is unchanged; future integration must reconcile pending-slot accounting explicitly.

Every later simulated commit checks the complete prior version/snapshot, exact reservation incarnation, current revocation and marker state. Presence of any canonical marker, including malformed/NULL, refuses progression. An external effect is preceded by a committed intent. No error retries an unconditional profile write. Late responses cannot finalize a changed/revoked profile. Group confirmation is bound to the persisted subject and target group.

Reservations follow the approved non-expiring/non-reuse policy at the contract boundary only. They are constructed/validated and stored solely in synthetic memory. Abandonment keeps reservation, receipt and claims; it never deletes an identity. No live reservation lifecycle, TTL setting, table/index or migration is implemented. Identical backing-store rollback/recreation and persistence atomicity are not proven by an in-memory model; durable protection still requires the later writer/reservation implementation.

## External identity ownership and recovery

Proof binds trusted issuer, tenant, subject, operation, STAFF ID, incarnation, request digest and opaque identity handle. Existing linking additionally requires the exact approved subject. Email/name is only a duplicate-check input; neither qualifies ownership. `Proof.verified` and admission flags are synthetic trusted preconditions, not signature verification or an API input schema.

CREATE uses a preallocated operation/target handle. CREATE_OR_LINK without an approved existing subject cannot adopt an already-existing identity; LINK_EXISTING and approved existing-user resolution require proof of the exact subject before group work. Existing identity/group membership is never deleted or removed; group ensure is modeled for only the approved target and preserves other groups. No unrelated account compensation exists.

After an ambiguous create/group timeout, the coordinator re-reads the durable intent and requests authoritative reconciliation. It never blindly recreates an identity. The mock provider exposes operation-bound receipts/membership evidence; this is a test contract, NOT a claim that Cognito supplies a durable create-idempotency token or this provenance API. Real ownership provenance, handle mapping and authoritative absence/unknown semantics must be designed and independently verified before any runtime wiring. If proof is unavailable or mismatched, remain non-active and require manual recovery; do not infer ownership from UsernameExists/email matching.

| Failure | Modeled recovery |
| --- | --- |
| Stage/intent persistence refuses | No identity/group call occurs |
| Create succeeds, identity-confirmation write fails | Retain intent; verify ownership-bound receipt on retry; one create attempt |
| Identity/group succeeds, ACTIVE finalization fails | Persisted confirmations permit persistence-only retry; no invitation outbox until finalization succeeds |
| Group succeeds, confirmation write fails | Reconcile exact subject/group; avoid repeating the successful effect |
| Known group failure | Persist FAILED; retry only with current context, retained intent and authoritative membership reconciliation |
| Unknown timeout cannot be reconciled | Stay non-active, no blind retry or automatic invitation |
| Existing-user conflict | FAILED/manual recovery; pre-existing identity untouched |
| Revocation/marker/incarnation conflict during an effect | Later commits refuse; no activation/invitation; do not pretend an already-issued external call was undone |
| Abandonment | Non-active retained evidence; no destructive compensation or automatic identity reuse |

External calls and database writes are not one distributed transaction. Effect intent is the recovery boundary, not a guarantee that a late revocation can cancel an already-issued external request. Cancellation priority and administrative reconciliation remain pending runtime decisions.

## Invitations and duplicate suppression

ACTIVE finalization and one versioned welcome outbox entry are a single simulated commit. Dispatch atomically claims PENDING using the ACTIVE profile version and current protection checks before a mocked send. Duplicate/restarted coordinators observe SENT/INFLIGHT/UNKNOWN and do not send again. If send succeeds but acknowledgement persistence fails, INFLIGHT remains; if the response is ambiguous, UNKNOWN remains. Both require explicit reconciliation, never automatic resend. Revocation before claim blocks dispatch.

This provides modeled at-most-once coordinator attempts, not guaranteed exactly-once provider delivery. It can deliberately leave an invitation unsent after a pre-send crash. Real Postmark dispatch, secure invitation material, delivery receipts, proof-based recovery/resend and revocation-versus-send ordering require separate design; no plaintext credentials or temporary passwords are persisted by this contract. Profile provisioning and invitation completion remain distinct facts.

## Validation and scope

Focused evidence: **47 new onboarding cases pass**, and **176 combined identity/onboarding cases pass** (129 inherited plus 47). Tests use synthetic subjects/opaque handles and MemoryState backing across coordinator restarts, deterministic before/after race snapshots, mocked failures and a network-connect tripwire. No sleeps, live clients, customer records, secrets or actual provider operations. Source/import boundary tests verify the model stays unwired and standard-library-only; existing PR48 no-import tests remain unchanged and passing.

The exact PR48 guarded backend baseline is **77 failed / 2193 passed**. New guarded full-suite result: **77 failed / 2240 passed**, with all 77 full failure-summary signatures identical to the exact PR48 baseline; 47 additional passes, zero newly failing tests. Exact head/check evidence is bound in the delivery record. Existing baseline failures are not repaired or suppressed. The dependent-base Draft does not trigger the standard workflow because it targets main only; security is reported as observed. No CI/ruleset change or green-CI claim is manufactured. Author-agent self-review only; no independent human approval claimed.

## Slice 2B resume and remaining gates

The Cognito-before-STAFF-write issue now has a mocked, fail-closed staging/reconciliation specification; the live blocker is not repaired. After owner acceptance, explicitly resume Slice 2B from this then-verified dependent head in a separate worktree/branch, preserving the PR48 -> PR47 ancestry. Do not copy these changes into PR48 or modify PR46. Carry the writer inventory and permanent-reservation checks into the approved protective package; keep enrollment/owner execution disabled.

Before runtime onboarding integration: approve/verify real ownership proof and idempotency/reconciliation mechanism, pending-slot/claim release, privileged target-role behavior, quota/uniqueness transaction implementation, legacy STAFF adapter/read compatibility, external-effect recovery, invitation material/delivery/resend semantics and all writer coverage. Any required IAM/API/Cognito/schema/deployment or data action needs separate authorization. No permission grant is inferred from existing shared-role TransactWriteItems source configuration.

CLEAN/required-check/RC and structured merge-authorization gates remain unchanged; PR45 is not activated. PR19 reconstructed source remains source-only and original plan/ZIP remain MISSING. All other PRs, worktrees and rollback evidence are preserved. No merge, Ready transition, deployment, migration, actual reservation/enrollment, owner execution, AWS/Terraform, production, Stripe/tenant, Android or Ryan operation is performed.
