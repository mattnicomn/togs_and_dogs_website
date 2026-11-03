# Shared REQUEST Write-Safety Contract — S0a Inactive Acceptance

**Date:** 2026-11-01 (America/New_York). **Disposition:** `REQUEST_WRITE_SAFETY_S0A_INACTIVE_NOT_INTEGRATED`.

Matthew explicitly approved ONE new dependent Draft PR, stacked on PR54, delivering the **smallest reviewable first slice (S0a)** of the shared REQUEST write-safety contract: three PURE decision/construction functions in `src/backend/common/request_write.py`, offline tests, and docs. Design direction only — no runtime activation, no caller adoption, no execution, no AWS.

## Dependency and scope

Branch `codex/request-write-safety-contract` is based on PR54 head `cbbee7fb73bdab20b169ed0445e8fc535f9f1770` (target branch `codex/cancellation-absent-identity-guard`). No PR51/52/53/54 branch is edited; this PR adds two new files and docs on the NEW branch only. Main verified `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`.

S0a implements EXACTLY three functions and NOTHING that executes:
- `classify_adoption(snapshot) -> AdoptionDisposition`
- `build_update(key, expected, plan, disposition) -> UpdateSpec | Refusal`
- `interpret_failure(evidence) -> FailureClassification`

## What S0a is — and is not

S0a is the pure **decision surface** of a REQUEST mutation: it decides whether a row may be fenced, constructs (but never issues) the conditional `UpdateItem` spec, and classifies a write failure. It opens no boto3/SDK client, performs no network/DB call, imports no handler, is imported by no production module, and contains no create/delete/tombstone/transaction execution. Those are later, separately approved slices (S0b create-only, S0c delete+tombstone, S0d coupled transactions), plus the read-only deployed-fleet inventory.

**A helper cannot protect legacy writers.** It only fences writes that call it. S0a makes no claim about unfenced, out-of-repo, old-artifact, queued or manual writers. This limit is a hard contract term, not a caveat.

## Security contract (as implemented)

1. **Legacy adoption — compatible ≠ safe-to-adopt.** `classify_adoption` returns `ADOPT_ELIGIBLE` only when the row carries a well-formed `legacy_write_revision` (and, when present, a well-formed `record_incarnation`). Missing or malformed version/lifetime metadata → `QUARANTINE_UNVERSIONED`; a non-REQUEST / missing-tenant / malformed snapshot → `REFUSE_INELIGIBLE`. A missing revision is **not** treated as a safe zero. There is **no SEEDING / override / bypass** parameter anywhere in the API.
2. **Quarantine is a refusal.** `build_update` refuses any disposition other than `ADOPT_ELIGIBLE` (`ADOPTION_REFUSED`), so an unversioned row cannot produce a fence.
3. **Conditions.** Every generated `UpdateItem` condition binds `attribute_exists(PK/SK)`, `company_id = :tenant` (tenant at write-time), `legacy_write_revision = :rev`, incarnation `= :inc` when present, and `status = :source_status` ONLY when the caller declares a status transition. The update ALWAYS advances the revision (`SET legacy_write_revision = :next`).
4. **PR54-complete ownership coverage for protected clients.** When `protected_client` is set, present/absent identity evidence must be well-formed, duplicate-free, DISJOINT, and EXHAUSTIVE over `{client_email, linked_client_profile_id, cognito_sub}`, and the present fence must include a subject/profile identity (email alone is rejected). Present fields are equality-fenced; absent fields get `attribute_not_exists`, so an insert-without-revision-bump is still rejected. Contradictory/incomplete/malformed evidence is refused.
5. **Identity immutability.** A plan may never SET/REMOVE an identity field or a reserved field (`PK/SK/company_id/client_id/request_id/legacy_write_revision/record_incarnation`); ownership is proven via the present/absent coverage, never by mutating an identity field.
6. **Named SET/REMOVE only; unknown fields preserved.** There is no whole-item/upsert form; the update names only plan fields + optional audit append + the revision advance, so concurrent unknown fields survive.
7. **Failure semantics.** `interpret_failure` defaults to `INDETERMINATE`. A bare `conditional_check_failed` is INDETERMINATE (cause unobservable). A transaction cancellation is INDETERMINATE unless it carries a `ConditionalCheckFailed` reason AND a deliberate re-read proving the specific divergence. Specific results (`STALE`, `TENANT_MISMATCH`, `RETIRED`, `ABSENT`) are returned only when evidence-backed (per-item reason or re-read). No blind retry; no silent upsert.
8. **Structural vs provenance.** All checks are STRUCTURAL shape/coverage checks. They do NOT authenticate provenance — a well-formed snapshot/plan is a shape, not proof that a trusted adapter observed it. Real provenance/freshness/authentication remain separate pending gates.

## Offline tests

`tests/backend/test_request_write.py` (40 cases) is AWS-free and deterministic. Besides refusal/classification assertions, it includes a minimal evaluator for the closed clause grammar `build_update` emits and **evaluates the actual generated `ConditionExpression` against synthetic stored-item states** (not just strings): valid state passes; stale revision, cross-tenant, diverged incarnation/source-status, changed/removed present identity, and inserted-absent-identity-without-revision-bump all fail. Coverage also includes quarantine/missing-metadata, the unversioned-writer race characterization, ownership coverage (incomplete/partial/contradictory/duplicate/unknown/email-only), malformed plans/inputs, indeterminate vs evidence-backed failures, and no-upsert / no-SDK / no-execution properties.

## Validation

Scoped run (S0a + the four inherited cancellation suites): **293 passed, 23 subtests passed** (217 inherited + 76 S0a), Python 3.13.3, pytest 9.0.2. S0a is additive and imported by nothing, so the inherited suites are unchanged. Full guarded backend not run here; recorded `FULL_BACKEND_NOT_VERIFIED` (prior PR53 74-failure baseline retained at `D:\petcare-rollback\pr53-evidence\13e9f5d\`).

## Final hardening — corrections 1 and 2 (2026-11-01)

A final verification pass flagged two provenance/adoption-discipline sharp edges. Both are now closed in the module itself; it stays pure, inactive, and imported by nothing. No seeding/adoption override was introduced - both changes strictly tighten.

- **C1 — mandatory incarnation on eligible writes.** `build_update` now requires a valid, non-None `ExpectedState.incarnation` whenever the disposition is `ADOPT_ELIGIBLE` (an eligible row by definition carries a well-formed `record_incarnation`; `classify_adoption` quarantines any row that lacks/malforms it). A missing/malformed incarnation is refused (`MALFORMED_INCARNATION`) BEFORE any `UpdateSpec` is generated, and the incarnation pin (`#inc = :inc`) is now emitted unconditionally, so the lifetime fence can never be silently omitted. Regressions confirm an item with a changed or removed incarnation FAILS the actual generated condition.
- **C2 — persisted identity must match the key.** `classify_adoption` now requires an exact `REQ#<request_id>` / `CLIENT#<client_id>` key AND that the persisted `request_id` / `client_id` attributes equal the identifiers encoded in PK/SK. A missing, malformed, or mismatched identifier returns `REFUSE_INELIGIBLE` (`REQUEST_ID_KEY_MISMATCH` / `CLIENT_ID_KEY_MISMATCH` / `MALFORMED_KEY_IDENTIFIER`) rather than quarantine or eligibility, so an internally inconsistent row is never adopted. (The PR55 Finding-A write-time binding already rejected such a row at the condition; C2 closes the classification layer too.)

Preserved unchanged: mandatory tenant/revision/incarnation fencing; PR54-complete protected-client coverage; strict key/expected consistency; quarantine-by-default legacy handling; named SET/REMOVE updates and `audit_log` append safety; evidence-backed failure classification; pure, side-effect-free, inactive, imported-by-nothing module. 11 new negative/positive regressions added (5 for C1, 6 for C2), evaluating generated conditions against synthetic stored REQUEST items; the original 65 cases are retained without weakened assertions.

## Corrective maintenance — independent-review findings A–D (2026-11-01)

An independent security review of the initial S0a commit (`99be204`) reproduced four contract defects offline. All were corrected on this branch; module stays pure, inactive, and imported by nothing.

- **A — REQUEST key / expected binding.** `build_update` previously accepted any truthy `PK`/`SK` and never tied the key to `ExpectedState`. It now parses an EXACT REQUEST key (`REQ#<id>` / `CLIENT#<id>`, well-formed identifiers, no extra attributes) via `_parse_request_key` and refuses otherwise (`MALFORMED_KEY`); optional `ExpectedState.request_id`/`client_id`, when supplied, must match the key (`KEY_EXPECTED_MISMATCH`); and the generated condition now binds `request_id = :reqid AND client_id = :cliid` alongside `company_id = :tenant`. This is a STRUCTURAL consistency check, not proof of trusted provenance.
- **B — failure evidence.** `interpret_failure`/`_classify_from_reread` no longer classify `ABSENT`/`RETIRED`/`STALE`/`TENANT_MISMATCH` from incomplete or malformed re-read evidence. A valid `ExpectedState` baseline is required; a MISSING re-read (`observed_row=None` with no explicit signal) is distinguished from an OBSERVED absence (`observed_row=None` AND `tombstone_present=False`); `tombstone_present` must be an exact `bool` (truthy ints/strings/lists are `MALFORMED_TOMBSTONE_EVIDENCE` → INDETERMINATE); a transaction `ConditionalCheckFailed` reason alone never names the failed clause and stays INDETERMINATE without a full re-read.
- **C — audit conflicts.** `audit_log` is now owned exclusively by the `append_audit` path; a plan that SETs or REMOVEs `audit_log` directly is refused (`AUDIT_FIELD_CONFLICT`), eliminating the two-actions-on-one-path DynamoDB ValidationException. Safe append-only audit behavior is preserved.
- **D — input shape safety.** `set_fields`, `remove_fields`, `present_identity`, `absent_identity` (both protected and non-protected paths) and `cancellation_reasons` must be real sequences (tuple/list); a `str`/`bytes` or non-iterable is refused cleanly (`MALFORMED_PLAN_COLLECTION` / `OWNERSHIP_EVIDENCE_SHAPE` / `MALFORMED_CANCELLATION_REASONS`) instead of raising `TypeError` or silently iterating a string into per-character REMOVE fields.

Regressions: 25 new offline cases reproduce every proven defect (including evaluating the generated condition's new `request_id`/`client_id` clauses against synthetic items). The original 40 S0a cases remain meaningful; the one that asserted "`observed_row=None` → ABSENT" was split into stronger variants (observed-absence vs missing-reread vs missing-expected) — a tightening, not a weakened assertion.

## Remaining approval gates

- **S0b** create-only fencing; **S0c** delete + transactional separate-key permanent tombstones (ABA); **S0d** coupled `transact_write_items`.
- **Deployed-fleet inventory** (separately-authorized, read-only AWS audit): which Lambdas/artifacts write REQUEST, whether all writers adopt the helper, drain/ordering before any adoption is trusted. Until then no legacy row is safe-to-adopt and no caller adoption is authorized.
- Caller adoption slices (payment → cancellation → ownership → intake → lifecycle), each its own PR with explicit live-workflow-impact approval.

S0a remains inactive and not merge-ready. No parent-branch edits, runtime integration, AWS/Terraform/Cognito/IAM, migration/backfill, Stripe/tenant, distribution, or Ryan testing occurred.


## S0b — create-only REQUEST + permanent lifetime (2026-11-01)

**Disposition:** `REQUEST_WRITE_SAFETY_S0B_INACTIVE_NOT_INTEGRATED`. Matthew authorized ONE new dependent Draft PR stacked on **PR55 head `1aae47463a6a393652f263d0e0243d3d29dad3af`** (branch `codex/request-write-create-safety`, target `codex/request-write-safety-contract`). No PR51–55 branch is edited. The module stays pure, inactive, and imported by nothing; nothing executes.

S0b adds exactly one function and its data types to `common/request_write.py`:
`build_create(key, intent, lifetime_evidence) -> CreateSpec | Refusal`, with `CreateIntent`, `LifetimeEvidence`, `CreateSpec`.

**A — REQUEST creation.** Exact `REQ#`/`CLIENT#` key (reuses `_parse_request_key`); `intent.request_id`/`client_id` and the item's own `PK/SK/request_id/client_id` must match the key (`KEY_INTENT_MISMATCH` / `ITEM_IDENTIFIER_CONFLICT`); `item.company_id` must equal `intent.tenant` (`TENANT_MISMATCH`); the builder initializes `legacy_write_revision=1` and writes `record_incarnation` itself (a caller item carrying either is refused, `RESERVED_FIELD_IN_ITEM`); caller-supplied `incarnation` and `created_at` are shape-validated (`MALFORMED_INCARNATION` / `MALFORMED_CREATED_AT`) — the pure builder does **not** mint entropy or clock time.

**B — lifetime evidence (tagged state, not free booleans).** `LifetimeEvidence.state` is one of `LIFETIME_ABSENT`/`LIFETIME_ACTIVE`/`LIFETIME_RETIRED`/`LIFETIME_NOT_OBSERVED`; the evidence `token` must equal the builder's deterministically derived token, `retired` must be an exact bool, and the `state` must be internally consistent with `retired`/`record`. Only a well-formed, token-bound `LIFETIME_ABSENT` permits a plan; `ACTIVE` → `LIFETIME_PRESENT`, `RETIRED` → `KEY_RETIRED`, `NOT_OBSERVED` → `LIFETIME_NOT_OBSERVED`, anything uncertain/malformed → `MALFORMED_LIFETIME_EVIDENCE`. Structural validation is **not** provenance authentication.

**C — atomic contract.** The lifetime token is byte-identical to the inactive cancellation contracts' token encoding (`sha256(json.dumps([tenant, pk, sk], sort_keys, separators=(",",":"), ensure_ascii))`); the canonical encoding was confirmed consistent across all three contracts before implementation, and a test asserts byte-equivalence against each. `build_create` returns ONE `CreateSpec.transact_items` of **two create-only Puts** (REQUEST + `LIFETIME#<token>/PERMANENT`), each with `ConditionExpression = "attribute_not_exists(PK) AND attribute_not_exists(SK)"`. No unconditional PUT/upsert, no `TableName`, no client, no separately executable write guidance — construction only; execution is deferred to S0d. The two Puts are self-fencing at commit, so a stale `LIFETIME_ABSENT` can never double-create or overwrite.

**D — historical ABA.** The builder never infers a never-used key from a missing REQUEST: a genuinely fresh key and a key whose REQUEST+lifetime were purged by an unfenced path are observationally identical (both absent), proven by a characterization test. `LIFETIME_ABSENT` is necessary but **not sufficient**; only a durable, never-deleted retirement tombstone (written by S0c on delete and never hard-deleted) distinguishes a purged key, and a `LIFETIME_RETIRED` observation refuses recreation (`KEY_RETIRED`). **No global ABA prevention is claimed** while unfenced deleters (the live unconditional purge, cleanup scripts, old artifacts) remain active. No seeding/migration/legacy bypass exists.

**Validation.** Scoped run (S0a+S0b + the four inherited cancellation suites): **323 passed, 23 subtests passed** (217 inherited + 106 S0a/S0b: 76 S0a + 30 new S0b), Python 3.13.3, pytest 9.0.2. Tests evaluate the actual generated create-only conditions against synthetic persisted items (collision, stale-lifetime, concurrency), prove canonical-token equivalence, and characterize fresh-vs-purged ABA ambiguity. The 76 S0a and all inherited assertions are preserved without weakening (one S0a stdlib-import assertion was broadened to include `hashlib`/`json`, both standard library; one inherited "unwired" grep is satisfied by not naming sibling modules in source). `FULL_BACKEND_NOT_VERIFIED` retained (PR53 74-failure baseline at `D:\petcare-rollback\pr53-evidence\13e9f5d\`).

**Remaining gates (unchanged):** S0c delete + transactional separate-key permanent tombstone (the ABA counterpart S0b depends on); S0d real execution; the separately-authorized read-only deployed-fleet inventory; and per-path caller adoption — each its own approval. S0b alone provides exclusive-create + lifetime-aware refusal, not global ABA. Inactive, imported by nothing, not merge-ready.


## S0b corrective maintenance — review findings A, B, C (2026-11-01)

An independent targeted review of PR56 S0b (`4c96cb0`) confirmed two contract defects and one incomplete-validation gap. All corrected on `codex/request-write-create-safety`; module stays pure, inactive, imported by nothing; nothing executes.

- **A — created_at validation.** `_valid_iso_utc` previously accepted any non-empty string (e.g. `"banana"`, `"2026-13-99"`, whitespace), so a garbage `created_at` built a CreateSpec. It now performs genuine ISO-8601 UTC validation (stdlib `datetime.fromisoformat`, with `Z` normalized to `+00:00`): accepts a complete date-and-time in UTC (`Z` or `+00:00`); rejects impossible dates, arbitrary strings, whitespace/surrounding-whitespace, date-only or time-only values, naive timestamps, and non-UTC offsets, and non-strings — all → `MALFORMED_CREATED_AT`. The caller's exact validated string is used verbatim; no clock is minted or rewritten.
- **B — created_at ownership.** `build_create` previously overwrote any `item.created_at` with `intent.created_at` silently. `created_at` is now builder-owned: any `CreateIntent.item` containing `created_at` is refused (`RESERVED_FIELD_IN_ITEM`), even when equal to `intent.created_at`. Only the validated `intent.created_at` populates the REQUEST item — single source of truth, consistent with `legacy_write_revision`/`record_incarnation`.
- **C — lifetime record validation.** For `LIFETIME_ACTIVE`/`LIFETIME_RETIRED`, the builder now requires a well-formed observed record: `record` must be a dict with `PK == "LIFETIME#"+token`, `SK == "PERMANENT"`, `record.retired` an exact bool agreeing with `evidence.retired`, and the retired value agreeing with the ACTIVE/RETIRED tag. Missing/malformed/contradictory evidence now yields `MALFORMED_LIFETIME_EVIDENCE` rather than a clean `LIFETIME_PRESENT`/`KEY_RETIRED`. Both ACTIVE and RETIRED still ALWAYS refuse creation — no CreateSpec is ever produced from an observed lifetime (exhaustively test-asserted).

**Preserved:** canonical lifetime-token byte equivalence; single atomic two-Put create-only transaction; tenant/REQUEST identity consistency; `legacy_write_revision=1` init + incarnation validity; fail-closed lifetime handling; historical-ABA disclaimer; structural-not-provenance limitation; pure/inactive/no-execution design.

**Validation.** Scoped run (S0a+S0b + four inherited cancellation suites): **338 passed, 23 subtests passed** (217 inherited + 121 S0b-module: 76 S0a + 30 original S0b + 15 new A/B/C regressions), Python 3.13.3. The 76 S0a, 30 original S0b, and all inherited assertions are retained without weakening (one S0a stdlib-import allowlist broadened to include `datetime`, standard library). `FULL_BACKEND_NOT_VERIFIED` retained.


## S0c — permanent retirement + atomic lifetime tombstone (2026-11-01)

**Disposition:** `REQUEST_WRITE_SAFETY_S0C_INACTIVE_NOT_INTEGRATED`. Matthew authorized ONE new dependent Draft PR stacked on **PR56 head `a213704fbc75ad65485c04b02ddd2a84bc299ebc`** (branch `codex/request-write-retire-safety`, target `codex/request-write-create-safety`). No PR51–56 branch is edited; the module stays pure, inactive, imported by nothing; nothing executes.

S0c adds `build_retire(key, expected, lifetime_evidence) -> RetireSpec | Refusal`, `classify_retire_failure(evidence) -> FailureClassification`, and data types `RetireExpected`, `ChildJobEvidence`, `RetireSpec`, `RecordObservation`, `RetireFailureEvidence`.

**A — atomic two-operand retirement.** `build_retire` constructs ONE `transact_items` of exactly two conditional `Update`s: (1) the permanent lifetime record is **retired in place** (`retired` False→True, set `retired_at`/`retired_revision`, condition `attribute_exists(PK) AND retired=:false AND incarnation=:inc`; never deleted); (2) the REQUEST is fenced (tenant, exact key identity request_id/client_id, revision, incarnation, validated-UTC `retired_at`, and a mandatory not-already-retired guard `(attribute_not_exists(retired_lifetime) OR retired_lifetime=:false)`), marked `retired_lifetime=True`, and its `legacy_write_revision` advanced. Canonical lifetime token reused byte-identically. No unconditional update/delete, no `TableName`/client/SDK/execution.

**B — lifecycle untouched.** `status.py` is not modified; `ARCHIVED`/`DELETED` remain reversible while the lifetime is active. Permanent retirement is the distinct `lifetime.retired` + REQUEST `retired_lifetime` pair. Restore refusal and S0a write-fences are NOT implemented here (future adoption).

**C — child evidence.** `_ACTIVE_JOB_STATES` (JOB_CREATED/ASSIGNED/APPROVED) → `ACTIVE_CHILDREN_PRESENT`; `_REOPENABLE_JOB_STATES` (CANCELLED/COMPLETED — they can transition back to executable) → `REOPENABLE_CHILDREN_PRESENT`; `_DURABLY_INACTIVE_JOB_STATES` (ARCHIVED/DELETED — no status-machine path to executable) may pass the structural gate. Validates child identity/key relationship, status, duplicates, shape, and a complete-child-set attestation; incomplete/malformed → refuse. A parity test asserts the mirrored sets match the live `common/status.py` enum + `JOB_TRANSITIONS`. Attestation is NOT provenance; the gate does NOT protect against stale evidence, unfenced writers, or concurrent JOB execution/billing.

**D — failure evidence.** Separate key-bound `RecordObservation`s for REQUEST and lifetime with states `NOT_OBSERVED`/`OBSERVED_ABSENT`/`OBSERVED_PRESENT`/`MALFORMED`. `classify_retire_failure` requires a valid, key-bound, internally-consistent observation (snapshot PK/SK match the observation key; lifetime key well-formed) before returning `ALREADY_RETIRED`, `REQUEST_ABSENT`, `STALE`, `TENANT_MISMATCH`, `INCARNATION_DIVERGED`, or `LIFETIME_MISSING`. Unknown/malformed/contradictory/incomplete evidence → `INDETERMINATE`. No blind retry; no inferred successful retire/delete.

**Validation.** Scoped run (S0a+S0b+S0c + four inherited cancellation suites): **368 passed, 23 subtests passed** (217 inherited + 151 request-write: 121 S0a/S0b + 30 new S0c), Python 3.13.3. Tests evaluate the two-operand conditions against synthetic REQUEST and lifetime state, cover all child dispositions/duplicates/incomplete-set, evidence-backed vs indeterminate failures, ABA/TOCTOU/stale-child characterization, and atomic no-partial-plan / no-execution checks. The 76 S0a, 45 S0b, and all inherited assertions are retained without weakening (no new imports; stdlib-only allowlist unchanged). `FULL_BACKEND_NOT_VERIFIED` retained.

**Safe live adoption still requires (none in this PR):** the S0a `retired_lifetime` atomic write-fence; restore-after-retirement refusal; the atomic JOB/assignment/payment **execution barrier** (proven necessary — assignment/job/payment paths do not consult the parent lifetime); Stage-2 child reconciliation; S0d real `transact_write_items` execution; and the read-only deployed-fleet verification. **No claim of fleet-wide ABA closure, provenance authentication, or runtime child safety.**


## S0c corrective maintenance — review findings A, B (2026-11-01)

An independent review of PR57 S0c confirmed two classification defects (the own-key-binding introduced during the initial S0c implementation). Both corrected on `codex/request-write-retire-safety`; module stays pure, inactive, imported by nothing.

- **A — authoritative target-key binding.** `classify_retire_failure` previously validated each observation against its OWN key, so an unrelated-but-self-consistent record could classify against a different target. `RetireFailureEvidence` now carries an explicit `target_request_key`. The classifier validates it with the strict REQUEST-key parser, requires a valid `expected.tenant`, derives the canonical lifetime token from the expected tenant + the target REQUEST PK/SK, and requires `request_obs.key` to equal the exact target REQUEST key and `lifetime_obs.key` to equal the exact derived `LIFETIME#<token>/PERMANENT` key. `OBSERVED_PRESENT` snapshots must carry the matching PK/SK. Unrelated keys are rejected even when internally consistent or sharing an incarnation — so an **unrelated retired lifetime can never yield `ALREADY_RETIRED`**. Target identity is never derived from the optional `RetireExpected.request_id`/`client_id` nor from observation-supplied keys.
- **B — strict observation consistency.** Each supplied observation is validated by state: `NOT_OBSERVED` (no snapshot, no false absence; a `None` observation is treated as not-observed); `OBSERVED_ABSENT` (exact target key, no snapshot); `OBSERVED_PRESENT` (exact target key + snapshot with required fields of exact permitted types — lifetime `retired: bool`, `incarnation: str`; REQUEST `company_id: str`, `legacy_write_revision: int`, `record_incarnation: str`); `MALFORMED` never supports a diagnosis. Both observations are checked for conflicts (a present-unchanged REQUEST plus a retired lifetime is contradictory) BEFORE any specific classification. Missing/malformed/wrong-target/incomplete/contradictory evidence → `INDETERMINATE`. No success inferred from cancellation; no blind retries.

**child_set_complete clarification:** `child_set_complete` is ONLY a caller assertion that it enumerated the children; the inactive contract does NOT and cannot independently prove complete enumeration of JOB records. It is structural attestation, not provenance.

**Validation.** Scoped run: **377 passed, 23 subtests passed** (217 inherited + 160 request-write: 121 S0a/S0b + 39 S0c), Python 3.13.3. Added regressions: wrong target REQUEST key / wrong lifetime token (self-consistent rows) → INDETERMINATE; unrelated retired lifetime same incarnation → never ALREADY_RETIRED; OBSERVED_ABSENT carrying a snapshot, NOT_OBSERVED carrying a snapshot, PK/SK-mismatched present snapshot, wrong-type/missing required fields, contradictory REQUEST/lifetime observations, missing/malformed target key, bare cancellation → INDETERMINATE; and correct key-bound ALREADY_RETIRED / REQUEST_ABSENT / STALE / TENANT_MISMATCH / INCARNATION_DIVERGED / LIFETIME_MISSING. No weakened assertions. `FULL_BACKEND_NOT_VERIFIED` retained.

**Unchanged mandatory adoption dependencies:** the atomic JOB/assignment/payment execution barrier, S0a `retired_lifetime` write-fence, restore-after-retirement refusal, Stage-2 child reconciliation, S0d execution, and deployed-fleet verification. No claim of runtime child safety, fleet-wide ABA closure, or provenance authentication.


## S0c corrective maintenance — classifier envelope validation (2026-11-01)

A final read-only classifier audit confirmed one defect: `classify_retire_failure` validated the target key, observations, and consistency, but did NOT validate the evidence *envelope* (`evidence.kind` / `cancellation_reasons`), so an invalid `kind` (garbage/None/non-string) or malformed `cancellation_reasons` could still yield a specific diagnosis (e.g. `ALREADY_RETIRED`) from an otherwise-valid observation. Corrected on `codex/request-write-retire-safety`; module stays pure, inactive, imported by nothing.

- **A — evidence kind.** `classify_retire_failure` now accepts ONLY the exact kinds `"reread"` and `"transaction_cancellation"` (exact-string membership, no aliases/normalization); unknown/empty/None/non-string kinds → `INDETERMINATE` (`UNKNOWN_EVIDENCE_KIND`) BEFORE any observation is classified.
- **B — cancellation metadata.** `cancellation_reasons` must be a sequence (tuple/list, reusing the S0a `_is_sequence` contract). For `transaction_cancellation`: at most two entries (positional mapping to the two S0c operands — lifetime, REQUEST), each a `str`; unsupported count → `UNSUPPORTED_CANCELLATION_COUNT`, non-str entry → `MALFORMED_CANCELLATION_ENTRY`; zero entries = insufficient information (not proof). For `reread`: no cancellation reasons are permitted (`REREAD_WITH_CANCELLATION_REASONS` otherwise). A generic cancellation reason is **never** used to infer which conditional clause failed — the specific cause always comes from a key-bound reread. Malformed metadata yields `INDETERMINATE` even when a lifetime/REQUEST reread would otherwise support a specific diagnosis.

**Preserved unchanged:** authoritative target REQUEST-key binding; canonical lifetime-token derivation; strict snapshot/observation consistency; both-observation conflict checks; deterministic evidence-backed classifications; default `INDETERMINATE`; no inferred success / no blind retry; the pure two-operand retirement spec; permanent lifetime tombstone + REQUEST `retired_lifetime` marker.

**Validation.** Scoped run: **384 passed, 23 subtests passed** (217 inherited + 167 request-write: 121 S0a/S0b + 46 S0c), Python 3.13.3. Added regressions: unknown/empty/None/non-string kind → INDETERMINATE even with a valid retired-lifetime observation; malformed container, malformed entry, unsupported count → INDETERMINATE; `reread` carrying reasons → INDETERMINATE; valid `transaction_cancellation` 2-entry envelope and valid `reread` still classify; zero-reason valid envelope with no observation → INDETERMINATE. No weakened assertions. `FULL_BACKEND_NOT_VERIFIED` retained.


## S0a retirement write-fence (2026-11-01)

**Disposition:** `REQUEST_WRITE_RETIREMENT_FENCE_INACTIVE_NOT_INTEGRATED`. Matthew authorized ONE new dependent Draft PR stacked on **PR57 head `13064bd11b54d5c02b120b7f61e9f625c02eaee4`** (branch `codex/request-update-retirement-fence`, target `codex/request-write-retire-safety`). No PR55–57 branch is edited; the module stays pure, inactive, imported by nothing; nothing executes. This closes the one cross-contract compatibility gap from the integration-readiness report: S0a `build_update` previously had no awareness of the S0c permanent-retirement marker.

**A — retirement evidence (fail-closed; corrected 2026-11-01).** `ExpectedState` gains a tagged `retirement_marker` (`RETIREMENT_ABSENT` / `RETIREMENT_FALSE` / `RETIREMENT_TRUE` / `RETIREMENT_NOT_OBSERVED`, default `NOT_OBSERVED`). `build_update` enforces fail-closed:
- `RETIREMENT_TRUE` → `Refusal("RETIRED_REQUEST")`.
- `RETIREMENT_FALSE` → eligible for a guarded update.
- `RETIREMENT_ABSENT` → eligible under the documented legacy-compatibility assumption — an **actually observed** missing `retired_lifetime` attribute.
- `RETIREMENT_NOT_OBSERVED` → **`Refusal("RETIREMENT_EVIDENCE_NOT_OBSERVED")`** — an unperformed lookup is NOT observed absence; **omitted/default evidence always refuses** and never authorizes an update.
- unknown / None / malformed / wrong-type → `Refusal("MALFORMED_RETIREMENT_EVIDENCE")`.

The default `retirement_marker` remains `NOT_OBSERVED`, but that state is refused unless a caller supplies valid observed evidence explicitly. **Why an observed `ABSENT` differs from `NOT_OBSERVED`:** `ABSENT` means a lookup was performed and the `retired_lifetime` attribute was genuinely not on the row (eligible under legacy compatibility); `NOT_OBSERVED` means no lookup happened at all, so there is no evidence either way and the update must fail closed. Observed absence is never inferred from a missing lookup; there is no seeding/bypass override. This is a structural shape check, not provenance.

**B — atomic retirement write-fence.** EVERY successful `build_update` now emits the mandatory condition clause `(attribute_not_exists(#rl) OR #rl = :false)` where `#rl → retired_lifetime`, `:false` is the exact boolean False — present on all updates, not only declared status transitions. So a concurrent S0c retirement that commits after the caller's read makes the update fail closed at commit. Synthetic-record evaluation: absent marker → true; exact False → true; exact True → false; non-bool marker → false; concurrent retirement → false. Tenant, REQUEST identity, revision, incarnation, source-status, ownership and audit fences are preserved.

**C — reserved retirement metadata.** `retired_lifetime` and `retired_at` are added to `RESERVED_FIELDS`; a `WritePlan` that SETs or REMOVEs either (including an attempt to clear the marker) → `RESERVED_FIELD`. All prior reserved/immutable protections are preserved.

**D — compatibility.** S0b `build_create` and S0c `build_retire` (semantics, transaction shape, failure classifications) are unchanged; no live `RequestStatus`/`status.py`/handler/restore/JOB/payment/`db.py` change.

**Validation.** Scoped run (S0a+S0b+S0c + four inherited cancellation suites): **404 passed, 23 subtests passed** (217 inherited + 187 request-write), Python 3.13.3. All previously reported 384 scoped tests + 23 subtests retained without weakening (the S0a test evaluator was taught to parse the single parenthesized OR group — a harness change, not a contract weakening). The NOT_OBSERVED fail-closed correction added explicit negative tests (explicit RETIREMENT_NOT_OBSERVED, omitted/default evidence) and updated inherited fixtures to supply an explicit observed tag; no assertion was weakened. `FULL_BACKEND_NOT_VERIFIED` retained.

**Remaining live-adoption prerequisites (none in this PR):** restore-after-retirement refusal in the live UNARCHIVE path; the atomic JOB/assignment/payment execution barrier; Stage-2 child reconciliation; S0d real `transact_write_items` execution; read-only deployed-fleet verification; per-path caller adoption. No runtime child safety, fleet-wide ABA closure, or provenance authentication claimed.