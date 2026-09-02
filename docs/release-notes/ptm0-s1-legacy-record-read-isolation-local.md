# PTM0-S1 — Legacy / untagged record read isolation

Status: **PTM0-S1 LOCAL IMPLEMENTATION READY FOR INDEPENDENT REVIEW**

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
| `/admin/requests?status=ALL` | Every tenant matched own OR absent company | Shared predicate composed with existing staff worker/client email filters, terminal-state exclusions and REQ marker; scan cursor retained |
| `/admin/requests?status=PENDING_REVIEW` (and other status-specific requests) | Same issue in StatusIndex query | Shared predicate + REQ marker; status key condition, descending order, limit and cursor retained |
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

- `src/backend/common/tenant_read_scope.py` — new narrow expression builder.
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

## Offline validation and evidence

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

## Security boundaries and deferred work

- Alpha/future callers cannot inherit absent primary records through these four
  filters; wrong-company tags and malformed stored associations are excluded.
- Primary absent compatibility remains opt-in and fixed; helper default rejects
  absent records even for primary. A query parameter cannot select compatibility.
- Platform-only role receives 403 on tenant admin list/status/export routes.
  Explicit platform target dispatch remains separate and does not call this
  helper. This proves no S1 privilege expansion, **not** that pre-existing F03
  mixed-role availability bypass or F04 email elevation is fixed.
- Existing identity, role, redaction, sorting, status, pagination and export
  auditing behavior remains; S1 adds no write/provider/notification call.
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
Review the exact diff from `d1b02b0`, reproduce the 41 focused cases, confirm
default-deny and absent-only primary policy, verify the four real filter call
sites, client-ID collision and pagination tests, and inspect the baseline versus
candidate failure inventories. Verify the two-file deployed-source delta and
that F02-F07, role/lifecycle behavior and all write call sites are untouched.
Only then request the next explicit approval. Local readiness does not authorize
push, packaging, deployment, further slices, or production validation.
