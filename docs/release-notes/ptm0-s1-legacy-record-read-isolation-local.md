# PTM0-S1 — Legacy / untagged record read isolation

Status: **PTM0_S1_CURSOR_CONFIDENTIALITY_READY_FOR_REVIEW**

Date: 2026-09-02. Local implementation and offline validation only. No deployment,
RC/package preparation, production action, or push. This is not PTM-0 completion
or deployment readiness: the broader baseline suite is not green.

## Origin and checkpoint

- Repository audit: [PTM-0 source-of-truth reconciliation](../planning/ptm-0-source-of-truth-reconciliation-audit.md),
  disposition `PTM0_ARCHITECTURE_CONFLICT_FOUND`.
- Kiro review: [independent architecture review](../reviews/ptm-0-source-of-truth-independent-review.md),
  disposition `PTM0_INDEPENDENT_REVIEW_CHANGES_REQUIRED`.
- Both identify classification C, F01 as a blocker, and S1 as the first narrow
  implementation slice. F02 is a separate blocker, not part of this change.
- Starting `main` and local `origin/main` both resolved to
  `d1b02b070da5fec7c65fea3e6cd245d9ac7f0eb4` (Kiro review commit). Worktree and
  index were clean; stash empty. No fetch or production/network access was used.
- Recorded deployed P1 backend source:
  `ec618b5734d4b271e7dd4b4aa9eecf318411323c`. The starting main admin handler and
  this recorded baseline have identical Git blob
  `92d4f36745c31db594b46ae6c60bde88b54f52bc`. This is repository evidence, not a new
  live deployment attestation. Main contains other intentionally undeployed work;
  do not deploy main wholesale.

## Exact policy and implementation

`common.tenant_read_scope.build_tenant_read_filter(company_id,
allow_primary_legacy=False)` builds a boto3 DynamoDB condition and performs no
I/O, identity resolution, role checks, or mutation. Its default is exact-match
only. Only the four existing compatibility read paths explicitly opt in.

| Stored company association | Resolved primary `tog_and_dogs`, opt-in | Alpha/future tenant |
| --- | --- | --- |
| Exact matching string | Include | Include |
| Another tenant's string | Exclude | Exclude |
| Attribute absent | Include | Exclude |
| DynamoDB NULL or empty string | Exclude | Exclude |
| Whitespace/padded, number, boolean, list, map | Exclude | Exclude |
| Invalid resolved tenant (null, empty, padded, non-string) | Match nothing | Match nothing |

The compatibility tenant is a fixed `tog_and_dogs` constant, not
`DEFAULT_COMPANY_ID`, a request parameter, or a role selection. For invalid
resolved IDs, the expression requires both attribute existence and absence,
which cannot match. Resolver behavior itself is unchanged.

**Absent is not NULL/empty.** The old admin filters used `attribute_not_exists`,
not a falsey-value test. Although the review discusses absent/empty together,
S1 preserves the narrower historical absent-attribute compatibility rather than
expanding primary access to NULL/empty records. Other ownership helpers' existing
falsey compatibility is classified below, not silently rewritten.

### Four confirmed call paths

| GET route / branch | Previous issue | S1 change and preserved contract |
| --- | --- | --- |
| `/admin/export-data` | Every tenant matched own OR absent company | Shared primary-only predicate; owner/admin + export entitlement gates, all-page scan, entity categorization, existing one export audit preserved |
| `/admin/requests?status=ALL` | Every tenant matched own OR absent company; raw evaluated-key disclosure | Shared predicate composed with existing staff worker/client email filters, terminal-state exclusions and REQ marker; bounded confidential pagination below |
| `/admin/requests?status=PENDING_REVIEW` (and other status-specific requests) | Same issues in StatusIndex query | Shared predicate + REQ marker; status key condition, descending order and limit retained; bounded confidential pagination below |
| `/client/requests` | Scan filtered client ID and REQUEST type only | Both existing conditions AND tenant predicate; identity resolution, redaction, sort and existing single-page/`lastKey: null` contract retained |

Omitted admin request status defaults to `PENDING_REVIEW`, **not** `ALL`.
Tests explicitly cover ALL, explicit status, and omitted status.

The client identity resolver queries `COMPANY#<resolved company>/CLIENT#...`
and returns a client ID after subject/verified-email matching. That scopes the
profile lookup, but no global uniqueness constraint binds every request carrying
the same client ID to that company. Tests seed equal client IDs across three
company partitions and use the real resolver, proving a request-level tenant
predicate is necessary. No client-role redesign was performed.

Primary compatibility is justified by the recorded deployed predicates and their
existing legacy-ownership semantics, not by reading current primary workflow
data. The prior client scan also admitted absent-company matching-client records;
the new predicate retains that only for primary. No live record inventory or
claim about actual production legacy-record counts is made.

### Additional-pattern classification

Repository searches covered raw `attribute_not_exists`, boto3 `.not_exists()`,
company/default fallbacks, and missing-company tests in runtime and scripts.

| Occurrence | Classification / disposition |
| --- | --- |
| Three company-equals-OR-absent filters in admin handler | Active tenant-plane list/export predicates; all replaced |
| Client request scan | Active tenant-plane read gap; minimal additional predicate |
| `common/auth.py::validate_tenant_ownership` | Primary/default compatibility for ownership checks; rejects other tenant associations; unchanged, including its pre-existing falsey treatment |
| `admin_handler.py::_resolve_admin_record` | Administrative cleanup resolver; scan post-filters with default-company ownership, and both active purge/action callers supply company plus downstream ownership checks; unchanged |
| `admin_handler.py::is_cognito_user_in_company` | Identity compatibility, not record-list predicate; strict multi exact comparison and existing single-mode legacy fallback unchanged |
| `pet_handler.py` and `common/pet_profile.py` explicit missing/wrong-company exclusions | Already restrictive tenant-plane pet reads; unchanged |
| `platform_handler.py` | Explicit platform group and target-company dispatch; not converted to tenant-read helper; provider detail dependency remains F02 |
| Google safe/default resolution; tenant-info/provider status | F02 provider/control-plane concern; untouched and not executed against production |
| Notification, cancellation and Stripe record/default fallback | Internal provider/write workflow logic outside S1; no source changes or live invocation |
| `scripts/remediate_pet_legacy_attributes.py` | Migration/conditional-update absence checks, not read grants; unchanged, not executed |
| `attribute_not_exists(started_at)` in admin handler | Write idempotency guard, unrelated to tenant association; unchanged |
| `common/db.py::query_by_status` | Generic global query helper, imported but no active call from these paths; not mechanically rewritten |
| Tests, release history, default-tenant fixtures | Evidence/fixtures, not additional active tenant read grants |

## Files in the review delta

Runtime (only these two):

- `src/backend/common/tenant_read_scope.py` — new narrow expression builder and
  bounded confidential page reader.
- `src/backend/handlers/admin_handler.py` — four uses; ALL/status expressions now
  composed as boto3 conditions rather than handwritten placeholder strings.

Tests:

- `tests/backend/test_r11e_tenant_enforcement.py` — replace prefiltered export
  mock with three-tenant, multi-page real-condition evaluation.
- `tests/backend/test_r19k_tenant_isolation.py` — nine list/status/default and
  pagination cases with mixed-company, absent and malformed records.
- `tests/backend/test_ptm0_s1_untagged_isolation.py` — one focused policy/client/
  role/control-plane/side-effect test module plus shared in-memory fixture.

Documentation: this release note. No other tracked file is part of S1.
Versus the recorded deployed P1 source, the S1 runtime delta is the changed admin
handler and new helper above; unrelated main-versus-deployed differences are not
part of this review or an authorized deployment.

## Initial S1 offline validation and evidence (preserved history)

Python 3.13.3; pytest 9.0.2; boto3 1.42.56; Moto 5.0.0 in-memory DynamoDB. No installs.
The focused fixture requires Moto in the local test environment; it is not an
application/runtime dependency and was already available on this workstation.
Tests evaluate actual boto3 conditions on mixed, unfiltered table records, not
preselected mock output. Pagination includes empty filtered pages, stable
filters, continuing cursors, eventual completion, and no duplicate return IDs.

The ignored local launcher `scratch/ptm0_s1_offline_validation.py` removes inherited
AWS/Google/Stripe/Postmark variables, supplies dummy AWS credentials and
nonexistent local config/credential paths, disables metadata access and pytest
plugin auto-loading, uses a fake table, and sets process-local strict multi mode
with entitlement enforcement. Socket/DNS/HTTP transports are blocked before
dispatch. These are test-process settings only; no application/deployment
configuration or production `TENANT_RESOLUTION_MODE` was changed.

Every S1 fixture mocks the unrelated availability/export-feature gate to isolate
F01, uses a Moto table, and asserts no database mutation/provider call. Existing
export audit is mocked and asserted exactly once, **not removed**. Therefore
this note does not claim that a real production export is a zero-write endpoint.
List exclusions and platform-only denials assert no audit or other side effect.
Existing dedicated entitlement/disabled-tenant suites are also run unchanged.

| Run | Passed | Failed | Skipped | Blocked external transport attempts |
| --- | ---: | ---: | ---: | ---: |
| Unchanged starting main, full `tests/backend` | 895 | 200 | 0 | 153 |
| Test-first red run, before runtime changes | 7 | 30 | 0 | 0 |
| Initial focused green run | 37 | 0 | 0 | 0 |
| Final focused run including role/filter preservation | 41 | 0 | 0 | 0 |
| Final full `tests/backend` | 936 | 199 | 0 | 153 |

Red failures: 14 exposed actual route leaks (2 exports, 6 admin list/status,
3 client paths, 3 exclusion-only reads); 15 awaited the not-yet-created helper;
1 awaited its control-plane non-use assertion. Primary list/export compatibility
already passed before implementation.

**Full-suite comparison:** zero candidate-only failing IDs, zero changed failure
categories among the 199 retained failures. The only removed failing node was
the old `test_admin_handler_export_filters_by_company`, replaced with three
realistic, evaluated export cases. This is a stronger replacement test, not
evidence that S1 runtime alone fixed the old fixture. No unrelated baseline test
was modified or deselected from the full run. Identical blocked-attempt counts
are not proof all failures are network-related; baseline also includes strict
tenant/mock, generated-contract and other pre-existing assertion failures.

### Relevant modules in the complete final run

| Module (under `tests/backend`) | Passed | Failed |
| --- | ---: | ---: |
| `test_r11e_tenant_enforcement.py` | 16 | 2 |
| `test_r19k_tenant_isolation.py` | 12 | 6 |
| `test_client_household_compatibility.py` | 17 | 0 |
| `test_client_household_handler_integration.py` | 27 | 0 |
| `test_client_pet_index_query_cutover.py` | 18 | 9 |
| `test_r18l_client_booking_limits.py` | 15 | 2 |
| `test_r8z_admin_per_visit_visibility.py` | 1 | 4 |
| `test_r9a_admin_lifecycle.py` | 1 | 5 |
| `test_r20e_disabled_tenant_enforcement.py` | 14 | 0 |
| `test_r17l_platform_admin.py` | 12 | 0 |
| `test_platform_protected_admin.py` | 1 | 7 |
| `test_r17b_entitlement_enforcement.py` | 9 | 0 |
| `test_r17d_entitlement_wiring.py` | 20 | 0 |
| `test_r17g_entitlement_observability.py` | 6 | 0 |
| `test_tenant_route_context.py` | 14 | 0 |
| `test_public_intake_tenant_routing.py` | 35 | 0 |
| `test_ryan_slice_e3a_child_start_and_occurrences.py` | 24 | 0 |

The R11E residual failures are `test_review_handler_same_tenant_approved` and
`test_pet_handler_get_same_tenant_succeeds` (AssertionError on baseline and
candidate). The R19K residual failures are `TestGoogleCalendarTenantGate`'s
`test_default_tenant_status_connected`, `test_non_default_tenant_status_not_connected`,
`test_non_default_tenant_disconnect_noop` (blocked transport RuntimeError),
`test_non_default_tenant_initiate_oauth_blocked`,
`test_non_default_tenant_callback_blocked` (500-versus-403 assertion), and
`TestTenantInfoEndpoint::test_tenant_info_default_company` (AssertionError).
All eight predate S1 under identical full-suite conditions. No F02 test/source
behavior was changed to make them pass.

### Commands and retained local evidence

```powershell
# Before implementation, then repeated unchanged against the candidate:
python scratch/ptm0_s1_offline_validation.py scratch/ptm0_s1_baseline_full.json tests/backend
python scratch/ptm0_s1_offline_validation.py scratch/ptm0_s1_candidate_full.json tests/backend

# Final focused selection:
python scratch/ptm0_s1_offline_validation.py scratch/ptm0_s1_focused_final.json tests/backend/test_r11e_tenant_enforcement.py tests/backend/test_r19k_tenant_isolation.py tests/backend/test_ptm0_s1_untagged_isolation.py -k "s1 or export_filters_by_company"

python -X pycache_prefix=scratch/ptm0_s1_bytecode scratch/ptm0_s1_compile_import.py
git diff --check
```

The baseline command above describes the already-recorded pre-change run; do
not overwrite its evidence by rerunning it on modified main. Reports contain
test IDs, phases, outcomes, and sanitized failure categories, not production
data. Full raw stdout is not persisted. The local-only launchers and generated
reports are ignored scratch artifacts, not runtime/release files.

SHA-256 evidence fingerprints:

- `ptm0_s1_baseline_full.json`:
  `C7A0431CA207A76AFEFD9C6750E68D891564AA5AEAC74D56F3BE22B98A7D4873`
- `ptm0_s1_red.json`:
  `5A325B2F66FED257A6622720314283146245B629CE84EE19CFF0FD6F38C3C6B4`
- `ptm0_s1_focused_final.json`:
  `BE924CFB50460301D026AAEB6F3752DD7FF7526D9B1B9C94594DECA05DC7E86B`
- `ptm0_s1_candidate_full.json`:
  `CD3FD1A650C5E3806396DA5F1A757F212EF2C2F579CDE336DF25C2D1906492C2`

Compile/import result: five changed Python files compiled, both runtime modules
imported under the offline guard, zero transport attempts. Initial compilation
into the default cache hit Windows access denied; a separate ignored bytecode
directory succeeded. `git diff --check` passed; normal LF/CRLF advisory warnings
do not indicate content errors or authorize release-package reconciliation.

## Independent review finding and local cursor correction

Independent review of `eb81742ced04b2939e35d6b7d67df84934300397` returned
`PTM0_S1_INDEPENDENT_REVIEW_CHANGES_REQUIRED`: MEDIUM pagination metadata
disclosure. DynamoDB filters returned `Items`, but `LastEvaluatedKey` can identify
an excluded evaluated record. Both an empty filtered page and a nonempty page
ending on an excluded record exposed request/client keys; the StatusIndex cursor
also exposed status/creation-time keys. The same raw-cursor behavior was
reproduced on the pre-S1 baseline. **This was pre-existing, not introduced by
S1**, but it prevented a response-wide isolation claim.

S1 scope is expanded narrowly to close that disclosure without changing the
approved tenant predicate, identity/role/entitlement policy, or F02. Starting
correction state was verified: clean `main` at `eb81742`, parent and local
`origin/main` at `d1b02b070da5fec7c65fea3e6cd245d9ac7f0eb4`, ahead exactly one,
empty index/stash. Commit strategy **B** preserves the reviewed candidate and
adds one local follow-up commit. No fetch, push, or history rewrite is needed.

### Occurrence classification

| Path / occurrence | Disposition |
| --- | --- |
| Admin ALL scan: incoming `startKey`, outgoing `lastKey` | Corrected; public continuation must match the last authorized returned row |
| Admin status/default StatusIndex query: same fields | Corrected; validates/reconstructs all four index continuation fields |
| Client request list | Existing single scan; always `lastKey: null`; no raw continuation; runtime unchanged by correction |
| Export | Internal all-page iteration; response contains only requests/clients/pets/staff/jobs; no cursor; runtime unchanged by correction |
| Admin `_resolve_admin_record` | Internal cleanup resolution, not a public list cursor; unchanged |
| `common.pet_profile` and `common.tenant_read_adapter` | Internal iteration, no public cursor at these occurrences; unchanged |
| Platform handler cursors | Separate explicit control-plane scope; not used by these tenant list/export/client paths; unchanged |

The existing three client identity-collision and three multi-page export cases
remain green. Export still has its existing audit (mocked locally); it was not
invoked against production. No export/client pagination redesign was made.

### Approved bounded design and API behavior

Matthew explicitly approved bounded server-side traversal and a generic
fail-closed cap response, with **no shared-key encryption or new cryptographic /
key-management infrastructure**.

- `MAX_TENANT_PAGE_READS = 16`: at most 16 scan/query calls per incoming admin
  list request, including the first. No caller/environment setting raises it.
  An initial 10-read trial hit the existing 13-record isolation fixture before
  its authorized row; the final fixed 16-read bound preserves all original 41
  tests without changing them. This is a local safety choice, not production
  volume/capacity evidence.
- Leading excluded pages are consumed internally, retaining the same complete
  tenant/role/status predicate, index, sort direction and input evaluation limit.
  The existing ALL limit is 1,000; status/default uses the existing requested
  limit (default 20). This change does not redefine those input limits.
- An outgoing key is allowed only when its exact field set and values match the
  **last returned authorized row**. Construct the public key from that row:
  `PK/SK` for ALL; `PK/SK/status/created_at` for StatusIndex. It equals the actual
  final underlying evaluated key, so the next call resumes at the correct point.
  Primary's explicitly authorized absent-company rows may supply this key.
- If collected authorized rows are followed by an excluded evaluated key, retain
  those rows internally and switch subsequent reads to `Limit=1` until a safe
  boundary or exhaustion. This avoids overfilling the original result limit.
  Do not stop merely because `Items` is nonempty, and do not publish the excluded
  tail key. A defensive overflow check also fails closed.
- Exhaustion yields HTTP 200 with collected authorized rows and `lastKey: null`;
  if no authorized rows were found, it yields the normal empty result/no cursor.
  A safe boundary or exhaustion on the 16th read succeeds.
- Cap reached without a safe boundary, repeated/cyclic key, or invalid key field
  set yields **HTTP 503** through the existing `common.response.error` JSON/CORS
  envelope, with body exactly
  `{"error": "PAGINATION_TRAVERSAL_LIMIT_REACHED"}`. There is no partial-success
  page, cursor, count, tenant ID, request/client ID, index value, timestamp or
  underlying evaluated key in that response. No diagnostic key logging is added.
  This uses the existing generic error model, not a new response envelope.
- The cap bounds application read amplification; existing SDK retry/timeouts
  are unchanged. It is not a hard wall-clock bound. DynamoDB's per-read size
  bound still applies. At most the original result limit is retained for return;
  internal continuation keys are bounded by the read cap.

**Confidentiality and bounded-resource safety take precedence over guaranteed
continuation through an arbitrarily long sequence of unauthorized records.**
Repeating the same request over an unchanged over-cap dataset may return the same
503; clients are not promised that retries will succeed. No partial page falsely
signals completion. An opaque/encrypted-token design is deferred to separately
approved future work only if production evidence justifies it. No snapshot or
cross-request consistency guarantee beyond existing DynamoDB behavior is added.

### Test-first evidence and final regression comparison

Before any runtime correction, the new `test_s1_cursor_response_confidentiality`
matrix (16 cases) and `test_s1_cursor_response_confidentiality_on_mixed_page`
matrix (8 cases) all failed on excluded identifiers in the response. The original
41 tests still passed. These red cases use real Moto filtering over tagged
primary/absent legacy records for Alpha and a future tenant, both ALL and
StatusIndex, with excluded-only, later-authorized and mixed nonempty pages.

The correction adds **77 cases** in the existing focused test file:

- 24 reproduced disclosure cases;
- 18 exact-cap generic-error cases, with and without collected partial data,
  for three tenants and ALL/explicit/default status;
- 12 exhaustion/safe-boundary cases before and on the cap;
- 9 exact continuation/no-skip/no-duplicate/termination cases, including primary
  absent-company keys and unchanged filters/limits;
- 6 NULL/empty/whitespace/padded/numeric/boolean/list/map/wrong-company response
  confidentiality cases;
- 8 repeated/cyclic/extra-field/missing-field continuation failure cases.

Assertions cover the entire serialized response, not only request bodies.
Original S1 tests and both R11E/R19K files are unchanged by this correction.

| Run | Passed | Failed | Skipped / xfail / xpass | External transports |
| --- | ---: | ---: | --- | --- |
| Cursor test-first red | 0 | 24 | 0 | 0 |
| Original focused selection before correction | 41 | 0 | 0 | 0 |
| Corrected focused selection: original 41 + 77 new | 118 | 0 | 0 | 0 |
| Corrected complete backend suite | 1,013 | 199 | 0 / 0 / 0 | 153 attempts blocked before dispatch; zero actual calls |

Full-suite comparison against independently replayed `eb81742` and `d1b02b0`:
**zero new failing IDs, zero changed categories, zero changed normalized full
failure reasons, zero changed normalized error/exception/denial output** among
the 199 retained failures. Normalization removes UUID/time/memory-address noise.
No baseline failure was fixed or hidden by this cursor correction, and no
pagination/tenant failure remains in the focused selection. The initial S1
export-fixture replacement described above remains the only removed failing
baseline node versus `d1b02b0`.

R11E remains **16 passed / 2 pre-existing failures**; R19K remains **12 / 6**.
All other relevant module results in the initial validation table above are
unchanged: disabled-tenant 14/14, Platform Admin 12/12 (protected-admin module
still 1/7), tenant-route 14/14, public-routing 35/35, E3A 24/24, entitlement
9/9 + 20/20 + 6/6. The focused module alone is now 106/106.

Five S1 Python files compile and both runtime modules import under the offline
guard. A separate import overlay loads recorded P1 source
`ec618b5734d4b271e7dd4b4aa9eecf318411323c` plus only the current admin handler and
tenant-read helper: **19 modules imported, Python 3.11 syntax accepted, newer-main
module fallback prohibited, zero external transports**. Local execution remains
Python 3.13.3, not a live Lambda/Python 3.11 runtime attestation. There is no new
runtime dependency, encryption key, package, or infrastructure requirement.

Corrective delta: only this note, `src/backend/common/tenant_read_scope.py`,
`src/backend/handlers/admin_handler.py`, and
`tests/backend/test_ptm0_s1_untagged_isolation.py`. The original six-file S1 delta
against `d1b02b0` is preserved. `git diff --check` passes. **F02_UNTOUCHED = YES**.
Production actions, production access, Terraform operations, pushes, deployments,
packages and S2 work remain **ZERO**. PTM-0 is still incomplete.

Retained ignored local evidence SHA-256:

- `ptm0_s1_cursor_red.json`:
  `9D91408A7D40D55A9CEEE310CADF34F6F4B104E7FA5663C2E0D3D5B4DD08C4F0`
- `ptm0_s1_cursor_previous41.json`:
  `BE924CFB50460301D026AAEB6F3752DD7FF7526D9B1B9C94594DECA05DC7E86B`
- `ptm0_s1_cursor_focused.json`:
  `EFD0C033C9EF5BF4461334C8C8E2E91AFA5C1AC63F9D5403536E07E8591A9B5B`
- `ptm0_s1_review_replay_cursor-.json` (full outcomes and normalized hashes):
  `89F2D0862EEF8098684A58B05DDBB15EF56E4FFCEEAB9EFDC986A8140A8A6537`
- `ptm0_s1_cursor_deployed_overlay.json`:
  `36D2399E5AD26DD2E6C0934B0D3B36B057E438B6D18D24DF3353459D6DA895DD`

Reproduction commands for the corrected checkout:

```powershell
python scratch/ptm0_s1_offline_validation.py scratch/ptm0_s1_cursor_focused_rerun.json tests/backend/test_r11e_tenant_enforcement.py tests/backend/test_r19k_tenant_isolation.py tests/backend/test_ptm0_s1_untagged_isolation.py -k "s1 or export_filters_by_company"
python scratch/ptm0_s1_offline_validation.py scratch/ptm0_s1_cursor_full_rerun.json tests/backend
python -X pycache_prefix=scratch/ptm0_s1_cursor_bytecode scratch/ptm0_s1_compile_import.py
git diff --check
```

Do not overwrite the red/baseline reports. Evidence/tooling stays ignored and is
not staged. Full failure-reason comparison used an in-memory pytest report hook
with the same transport fence and assertion rewriting, including setup skips and
xfail/xpass reporting; only sanitized categories/hashes were retained.

## Security boundaries and deferred work

- Alpha/future callers cannot inherit absent primary records through these four
  filters; wrong-company tags and malformed stored associations are excluded.
- Primary absent compatibility remains opt-in and fixed; helper default rejects
  absent records even for primary. A query parameter cannot select compatibility.
- Platform-only role receives 403 on tenant admin list/status/export routes.
  Explicit platform target dispatch remains separate and does not call this
  helper. This proves no S1 privilege expansion, **not** that pre-existing F03
  mixed-role availability bypass or F04 email elevation is fixed.
- Existing identity, role, redaction, sorting, status and export auditing
  behavior remains; pagination is corrected as documented above. S1 adds no
  write/provider/notification call.
- Production mutations, production reads, AWS service calls, Terraform
  operations, deployments, packages, tenant changes, Cognito changes, and
  notifications are all zero. SDK activity was local mocked testing only.
- Web, Mobile, infrastructure, Google/OAuth/Calendar, Stripe, entitlement and
  provisioning source/configuration are untouched. No Ryan testing changes.

Explicit deferrals: **F02** Google/provider fallback; **F03** lifecycle,
entitlement availability/defaults and platform bypass; **F04** legacy email role
elevation; **F05** Cognito/profile membership synchronization; **F06** atomic
provisioning/default activation; **F07** atomic/immutable audit guarantees.
No automatic PTM0-S2 work is authorized or started.

## Review handoff

Keep the six-file delta local and unpushed pending independent Kiro/AG review.
Review the exact follow-up diff from `eb81742` and cumulative diff from
`d1b02b0`, reproduce all 118 focused cases, confirm
default-deny and absent-only primary policy, verify the four real filter call
sites, client-ID collision and pagination tests, and inspect the baseline versus
candidate failure inventories. Verify the two-file deployed-source delta and
that F02-F07, role/lifecycle behavior and all write call sites are untouched.
Specifically re-review whole-response confidentiality on empty and mixed pages,
the last-authorized-row key equality/field allowlist, safe StatusIndex resume,
the 16-call cap and generic 503 with no partial page, exact exhaustion, repeated
keys/cycles, primary absent compatibility, and original 41-test preservation.
Only then request the next explicit approval. Local readiness does not authorize
push, packaging, deployment, further slices, or production validation.
