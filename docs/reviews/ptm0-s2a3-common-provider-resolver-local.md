# PTM0-S2A.3 common provider resolver — local implementation/review

Date: 2026-09-04

Disposition: **PTM0_S2A3_LOCAL_IMPLEMENTATION_READY_FOR_INDEPENDENT_REVIEW**

Local candidate only. Not independently approved, committed, pushed, packaged,
planned, or deployed. This is not a standalone production-release approval.
F02 remains UNRESOLVED; PTM-0 remains INCOMPLETE. S2B–S2E are NOT STARTED.
S1/F01 remains complete. S2A.1 and S2A.2 remain complete/approved/closed.

## Checkpoint and scope

Starting branch `main`, HEAD and local `origin/main`:
`2f78dc98c620db7bdf6d819e75678cbc93145795`.
Tracked worktree clean; index and stash empty. The only initial untracked files
were the pre-existing S2A.2d evidence records below; both were preserved:

- `docs/reviews/ptm0-s2a2d-r1-targeted-convergence-verification.md`
- `docs/reviews/ptm0-s2a2d-terraform-convergence-plan-preflight.md`

Matthew authorized common provider ownership enforcement and focused offline
tests, not later handler repairs. Caller inventory was completed before edits.
Only `src/backend/common/google_calendar.py` changes runtime behavior.
`calendar_metadata.py`, all handlers, Terraform, Web and Mobile are unchanged.

## Caller inventory (pre-edit source locations)

GC = `src/backend/common/google_calendar.py`; GA =
`src/backend/handlers/google_auth_handler.py`. Locations refer to the starting
commit, so remain reproducible despite inserted common code.

| Call site | Context / classification | Local impact and deferred dependency |
| --- | --- | --- |
| GC `_get_stored_tokens` :71 | Optional company forwarded; formerly primary fallback | None/invalid binding now raises before value read; explicit owned input compatible |
| GC `_save_tokens` :83,86 | Optional company; repeated resolution for merge | Resolve once, read/merge/write against one canonical ARN; no None fallback |
| GC `_refresh_access_token` :131,148,150 | Provider exchange before validation; optional revocation target | Validate before app credentials/refresh; bound save/revocation do not re-resolve |
| GC `_mark_token_revoked` :171,174 | Explicit local None-to-default conversion | Conversion removed; invalid input fails before reads/writes |
| GC `_get_valid_token` :194,221 | Optional company to read/refresh | Validate before cached token use; same canonical ARN through refresh |
| GC `sync_calendar_event` :490,491 | `item.get('company_id')`, potentially None | Compatible with explicit tagged items; missing/invalid owner returns calendar_failed, no provider action |
| GC recursive sync :574 | Same item on remote 404 | Same context checked again for the new operation; retry algorithm unchanged |
| GC `delete_event_detailed` :627 and wrapper :655 | Optional company to valid-token helper | Missing/invalid binding returns `(False, False, fixed_error_code)`, never success/already-gone |
| GA `get_stored_tokens` :33 and `save_tokens` :55 | Wrappers themselves convert None to primary | Later-slice dependency: common cannot recover identity provenance after a wrapper supplies primary; unchanged |
| GA `save_tokens` :60 | Calls its own get wrapper, then writes | Handler double-resolution remains deferred; common bound helpers do not silently rewrite this handler |
| GA `disconnect_auth` :154,170 | `get_company_id_safe`; resolver plus common revocation | Explicit owned target compatible; safe-helper fallback remains deferred; public locator preserved to retain legacy equality guard |
| GA `initiate_auth` :192 | `get_current_company_id(event)` | Compatible when resolved tenant has valid binding; entitlement check remains after resolver |
| GA callback :275,314 | `state_record.get('company_id')`, potentially None; handler save wrapper | Resolver blocks invalid/missing company before state deletion/exchange. Expiry/replay/atomic-consume logic NOT repaired (S2B) |
| GA status :342,351,395 | `get_company_id_safe`; own read/save wrappers | Wrapper identity fallback and passive GET refresh/write remain S2C/later-context dependencies |
| GA health :420,431,455,472 | Scheduled explicit-primary intent or safe-helper fallback | Compatible with explicit primary metadata/tag; handler refresh and scheduled semantics unchanged |
| `intake_handler.py:302` | Sync from persisted item | Explicit tagged item compatible; no handler edit |
| `job_handler.py:164,268` | Sync from existing/new job item | Tagged item compatible; legacy missing context denied; propagation deferred to S2D |
| `assignment_handler.py:206` | Sync from merged request/body data | Common validates supplied tenant, cannot recover overwritten provenance; S2D body-merge repair deferred |
| `review_handler.py:308` | Sync from merged item | Same S2D provenance dependency |
| `admin_handler.py:3272` | Sync from edited/merged item | Same S2D context/merge dependency |
| `review_handler.py:345,364` | delete_event with event/request IDs only | Currently omits tenant; now fails closed; S2D propagation NOT implemented |
| `admin_handler.py:3283,3294` | delete_event with event/request IDs only | Same missing-context denial; some caller return handling remains imperfect and deferred |
| `cancellation_handler.py:248` | delete_event_detailed omits known company | Now fails closed; S2D propagation NOT implemented |

Runtime search included every caller of the resolver, stored-token/save/refresh/
revocation/valid-token helpers, sync and both delete functions. The naming helper
`get_tenant_secret_path` has no runtime callers after correction and is retained
only as a compatible utility, never used as ownership evidence.

The common layer trusts the explicit string supplied by its caller, not a new
identity-proof object. It cannot distinguish legitimate primary context from a
primary string manufactured by an unchanged handler fallback. These known
later-slice defects prevent claiming end-to-end F02 completion, not implementing
the authorized common boundary locally. No unsafe fallback was retained in the
common resolver to make those callers pass.

## Before and after

Previously: None became DEFAULT_COMPANY_ID; tenant metadata owner/key was not
checked; any truthy explicit reference was accepted without DescribeSecret;
primary could inherit the legacy secret even without metadata; an enabled
ordinary tenant got a derived name without an explicit reference. Refresh could
contact Google before resolution. Save/revocation re-resolved for merge.

Now the ownership contract is:

`explicit tenant == exact tenant metadata owner == exact secret CompanyId tag`

1. Require an unmodified string matching the existing provisioning ID shape
   `[a-z0-9_]{3,64}`. No trimming, case conversion or default after failure.
2. Read the base table with `ConsistentRead=True`, exact key
   `TENANT#<company_id> / METADATA`, projecting only PK, SK, company_id and
   calendar_secret_ref. Require a dictionary with all three exact identity fields.
   The old db helper is not used because it neither requests strong consistency
   nor preserves metadata-access failure distinction.
3. A PRESENT calendar_secret_ref must be a valid name or full Secrets Manager
   ARN. Null/empty/whitespace/malformed presence never means absent.
4. Only literal `tog_and_dogs`, verified metadata and a genuinely ABSENT ref can
   enter Option B. That branch uses the configured reviewed legacy token locator
   (`GOOGLE_USER_TOKENS_NAME`, established legacy name if unset). It still checks
   ownership. No DynamoDB reference backfill or generic DEFAULT_COMPANY_ID branch.
5. Ordinary tenants with absent reference return unconfigured, even if Google is
   enabled. Alpha and future tenants never derive/inherit the primary locator.
6. Validate locator shape. A configured full legacy ARN anchors account and
   partition; require that boundary plus the Secrets Manager client's region.
   If only a local legacy name is configured, accept local names but reject ARN
   references without an account anchor. Name lookups are local to the SDK account.
   This conservative ARN-without-anchor rejection is intentional fail-closed
   behavior, not new IAM/configuration provisioning. Recorded production uses a
   full ARN, but no production read was performed in this task.
7. DescribeSecret only, then require a full canonical ARN, matching Name/locator,
   expected region/account/partition where anchored, and no pending deletion.
8. Require a well-formed tag list with exactly one exact-case `CompanyId` and a
   non-empty string value equal to the validated tenant. Missing, duplicate,
   case-conflicting, malformed or foreign ownership fails closed. Arbitrary
   legitimate secret names remain supported; path text is not ownership proof.
9. Return a validated binding internally. Preserve the historical public locator
   return interface for existing handlers, particularly disconnect's comparison
   with GOOGLE_USER_TOKENS_NAME. Returning a different canonical ARN for a name
   there would accidentally bypass that existing guard. Common operations use
   the canonical ARN and pin it through read/refresh/save/revocation. No positive
   cross-request ownership cache is introduced.

DescribeSecret is not an atomic lock over future tagging or metadata changes.
Canonical ARN pinning prevents an in-operation reference change from redirecting
a write; each new operation revalidates. Ownership assignment remains controlled
infrastructure/administrative responsibility. No crypto, registry or new IAM is
introduced. Existing app-credential reads and token refresh policy are unchanged;
ownership validation adds metadata reads, not a new secret-value access path.

### Errors and public behavior

- Unconfigured: resolver None; token read `{}`; save False; no secret lookup.
- Invalid context/metadata/reference/tag structure:
  `ProviderBindingError('INVALID_TENANT_PROVIDER_BINDING')`.
- DynamoDB or DescribeSecret inaccessible:
  `ProviderBindingError('PROVIDER_METADATA_INACCESSIBLE')`, suppressing underlying
  SDK exception details.
- Well-formed owner differs: `ProviderBindingError('PROVIDER_OWNERSHIP_MISMATCH')`.
- Sync's existing auth-error catch returns calendar_failed using the safe code.
- Delete specifically catches binding denial and returns false/false; it does
  not misrepresent denied access as completed deletion.
- Handler methods without a binding-error mapper can propagate the safe error
  rather than produce their old success. Mapping/caller changes are deferred.

No error includes the reference, ARN, ownership tag, or metadata row. Normal
legacy token read/save failure return policy remains, with common SDK failure
logs sanitized. Private bound helpers are internal to this module; their callers
must validate before use. No handler was changed to invoke those helpers.

## Offline validation and expectation classification

Runner: ignored local `scratch/ptm0_s2a3/offline_tests.py`, using dummy credentials,
EC2 metadata disabled and socket/HTTP send denial. Normal mode also denies
unmocked SDK operations. `--moto` allows SDK dispatch into in-process Moto while
retaining socket and botocore HTTP send denial. No AWS/Google service requests
are possible in these runs. All token strings are fabricated fixtures.

Baseline comparison mode `--baseline-common` executes the exact common module
from `git show 2f78dc98c620db7bdf6d819e75678cbc93145795:src/backend/common/google_calendar.py`
in memory before collection. No checkout, reset or repository-history alteration.
Unmodified comparison tests and all other runtime files remain at that baseline.

| Selection | Final outcome |
| --- | --- |
| New `test_ptm0_s2a3_provider_binding.py` | 93/93 PASS |
| 21G; 6G token/retry/health/all-day; 9C banner; 7D hardening; 21D defaults; Google RBAC | 81/81 PASS |
| Above combined | 174/174 PASS |
| 17D entitlement, 7E cancellation/multi-day, 18P cancellation, Ryan slice-B regression | 83 PASS / 1 pre-existing FAIL, 84 total |
| 20E disabled-tenant, 17L Platform Admin, protected-admin boundaries | 34/34 PASS |
| S1 untagged-isolation complete file (Moto) | 106/106 PASS |
| 11E + 19K complete files (Moto) | 28 PASS / 8 pre-existing FAIL, 36 total |
| Python compileall over src/backend and tests/backend | PASS |
| Offline imports | PASS via collection/execution of all selections above |
| git diff --check | PASS |

These separate final selections cover **425 passes / 9 known baseline failures**
across 434 distinct cases. Do not describe the entire repository test suite as
green. No full-repository regression suite or deployment-package test is claimed.

New coverage includes all authorized ownership cases, canonical region/account/
partition/alias checks, disabled deletion outcomes, missing metadata for primary/
Alpha/future, no default-environment fallback, no cross-operation cache, read
ordering, cached-token validation and single-bound-ARN refresh/revocation/save
despite a concurrent reference change. SDK/app-config/provider mocks assert no
value or external-provider access on invalid/mismatched ownership.

Existing test changes:

- **Security correction:** optional/missing company success fixtures now supply
  explicit primary. Ordinary-tenant enabled-only fixtures now declare an explicit
  owned reference; no derived-name fallback is blessed. 9C status fixtures now
  supply a company claim instead of depending on the unchanged handler fallback.
- **Expected compatibility updates:** strongly read Item-shaped metadata including
  PK/SK/company_id, mocked DescribeSecret ownership, and private bound helper mocks
  preserve existing refresh/revocation/retry/status/RBAC assertions. The primary
  disconnect preservation assertion remains unchanged and passes.
- **Stronger existing assertions:** two all-day sync tests now reach scheduling
  validation with explicit owned context and require skip results, rather than
  passing accidentally on an unrelated authentication error.
- **Regression:** no newly introduced failing case remains in the executed
  selections after the scoped fixture corrections. No production behavior was
  weakened to satisfy tests.

The original nine-file Google/calendar baseline, before edits, was 59 PASS /
22 FAIL: older tests made unmocked tenant metadata calls that the offline guard
blocked. The final corresponding selection is 81/81. Those are harness gaps,
not evidence of a production call or authorization to weaken resolution.

The broader baseline/candidate comparison both produced 83 PASS / 1 FAIL:
`test_r7e_multi_day_jobs.py::test_multi_day_jobs_inherit_visit_window` raises
`KeyError: 'visit_window'` at the same assertion. It and job-handler runtime are
unchanged. No scheduling fix was attempted.

The unchanged 11E/19K baseline and candidate both produced 28 PASS / 8 FAIL:

- `test_review_handler_same_tenant_approved`: expected 200, TenantDisabled 403.
- `test_pet_handler_get_same_tenant_succeeds`: expected 200, TenantDisabled 403.
- 19K Google gate `test_default_tenant_status_connected`,
  `test_non_default_tenant_status_not_connected`,
  `test_non_default_tenant_initiate_oauth_blocked`,
  `test_non_default_tenant_callback_blocked`,
  `test_non_default_tenant_disconnect_noop`: unmocked tenant metadata access
  blocked locally (baseline raw offline-denial, candidate sanitized metadata-
  inaccessible error; initiation/callback produce 500 rather than expected 403).
- 19K `test_tenant_info_default_company`: the same incomplete metadata mock causes
  NOT_CONNECTED instead of CONNECTED on both versions.

These extra pre-existing test defects were not repaired or hidden. The dedicated
21G and new S2A.3 suites provide explicit owned/unconfigured/denied metadata
coverage instead. An exploratory mixed run was interrupted when the SDK-level
guard also blocked Moto's simulated CreateTable. No completion count is claimed
for that run; the corrected HTTP/socket-guarded Moto runs above supersede it.

### Reproduction commands

From the repository root, using the ignored runner described above:

```powershell
python scratch/ptm0_s2a3/offline_tests.py tests/backend/test_ptm0_s2a3_provider_binding.py tests/backend/test_r21g_google_token_isolation.py tests/backend/test_r6g_calendar_token.py tests/backend/test_r6g_calendar_retry.py tests/backend/test_r6g_calendar_health.py tests/backend/test_r6g_calendar_all_day.py tests/backend/test_r9c_google_calendar_banner.py tests/backend/test_r7d_calendar_hardening.py tests/backend/test_r21d_calendar_metadata_defaults.py tests/backend/test_google_auth_rbac.py
python scratch/ptm0_s2a3/offline_tests.py tests/backend/test_r17d_entitlement_wiring.py tests/backend/test_r7e_cancellation.py tests/backend/test_r7e_multi_day_jobs.py tests/backend/test_r18p_cancellation_cascade_fix.py tests/backend/test_ryan_slice_b_check_in_transactions.py
python scratch/ptm0_s2a3/offline_tests.py tests/backend/test_r20e_disabled_tenant_enforcement.py tests/backend/test_r17l_platform_admin.py tests/backend/test_platform_protected_admin.py
python scratch/ptm0_s2a3/offline_tests.py --moto tests/backend/test_ptm0_s1_untagged_isolation.py
python scratch/ptm0_s2a3/offline_tests.py --moto tests/backend/test_r11e_tenant_enforcement.py tests/backend/test_r19k_tenant_isolation.py
python -m compileall -q src/backend tests/backend
git diff --check
```

The common-baseline comparisons used the same applicable selection plus
`--baseline-common`, before modifying the 17D fixture. The 11E/19K files remain
entirely unmodified. Focused tests were also run separately during implementation.

## Exact candidate files and final boundaries

Modified tracked:

1. `src/backend/common/google_calendar.py`
2. `tests/backend/conftest.py` (opt-in owned-primary fixture; not global autouse)
3. `tests/backend/test_google_auth_rbac.py`
4. `tests/backend/test_r17d_entitlement_wiring.py`
5. `tests/backend/test_r21d_calendar_metadata_defaults.py`
6. `tests/backend/test_r21g_google_token_isolation.py`
7. `tests/backend/test_r6g_calendar_all_day.py`
8. `tests/backend/test_r6g_calendar_health.py`
9. `tests/backend/test_r6g_calendar_retry.py`
10. `tests/backend/test_r6g_calendar_token.py`
11. `tests/backend/test_r9c_google_calendar_banner.py`

New, untracked candidate:

12. `tests/backend/test_ptm0_s2a3_provider_binding.py`
13. `docs/reviews/ptm0-s2a3-common-provider-resolver-local.md` (this record)

Local ignored runner created: `scratch/ptm0_s2a3/offline_tests.py`. Compile/test
bytecode is local ignored output, not a release archive. Existing S2A.2d evidence
remains untracked and unchanged; it is not part of this candidate's modifications.

- S2B OAuth expiration/replay/atomic consumption: UNCHANGED / NOT STARTED.
- S2C passive status GET refresh/write separation: UNCHANGED / NOT STARTED.
- S2D review/assignment/admin body company merges and Calendar deletion caller
  propagation: UNCHANGED / NOT STARTED.
- S2E Platform explicit-target behavior: UNCHANGED / NOT STARTED.
- F02 UNRESOLVED; PTM-0 INCOMPLETE. No end-to-end ownership-completion claim.
- Tenant-resolution configuration, production provider metadata, tenant count,
  Stripe/Google configuration, Ryan behavior, Web and Mobile: unchanged by task.
- Production/AWS/Google/provider access: ZERO. Real secret values accessed: ZERO.
- Production writes, Terraform operations, packaging and deployments: ZERO.
- Staged files, commits, pushes: NONE. No remote Git operation was performed.
- Ending HEAD/local origin/main unchanged at the starting SHA. Index/stash empty.
  Worktree intentionally contains only the unstaged tracked changes and untracked
  records/tests listed above. Not claimed clean.

Stop for independent local review. No S2B–S2E implementation or production action
is authorized by this candidate or its passing focused tests.
