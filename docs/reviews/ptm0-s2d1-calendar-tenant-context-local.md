# PTM0-S2D.1 completed local implementation — current disposition

Date: 2026-09-08

**PTM0_S2D1_COMPLETE_LOCAL_IMPLEMENTATION_READY_FOR_INDEPENDENT_REVIEW**

This section supersedes the held partial disposition recorded below. It incorporates
the held S2D.1 subset and the explicitly authorized S2D.1B prerequisite implementation.
Architecture authorization supplied by the user:
`PTM0_S2D1B_INDEPENDENT_NARROW_PREREQUISITE_APPROVED`.
The completed implementation itself is NOT yet independently reviewed or committed.

## Starting checkpoint and preserved work

Branch main; HEAD and local origin/main:
`3272267c224505240be20656c4111fd02733a998`.
Index and stash empty. Started with six unstaged tracked files from the partial
candidate, its two untracked tests/docs, the untracked S2D.1B architecture record,
and the two pre-existing S2A.2d evidence documents. No remote Git operation occurred.

The held assignment/cancellation changes, review Calendar propagation and failure
retention, and their tests are preserved. Review gains only the producer envelope
change in this phase. Previous implementation/review history is retained below.

## Completed runtime contract

Admin POST /admin/requests lifecycle branch:

- Before direct/swapped/healed selection can lead to status update, audit or Calendar
  action, require explicit canonical authenticated custom:company_id, resolve through
  existing get_current_company_id, then compare exact canonical persisted owner to
  both values. Missing caller cannot be manufactured by single-mode fallback.
- Every selected result must have exact PK/SK matching the resolved keys. All lookup
  paths converge on the same check. Foreign/missing/malformed ownership fails per
  record. Authorized records in a mixed batch continue; rejected records have no
  status/audit/Calendar side effects.
- Global _resolve_admin_record behavior is unchanged (including unrelated PURGE).
  Its scan's legacy missing-owner convention cannot bypass the strict post-check.
  Tenant-resolution mode, role policy and Platform behavior are unchanged.
- Sync pins the validated current_item company in the existing item interface.
  Parent deletion supplies it as company_id. Child deletion requires exact child
  key, parent/request relationship and owner equality before passing child company.
  Completed children are still preserved. False/exception retains the event reference
  and records a generic Calendar failure in the existing failures list. Database
  lifecycle success count remains a database result, not proof of Calendar cleanup.

Job producer contract:

- Review sends expected_company_id from the already ownership-validated persisted
  request; canonical/nonmissing owner is required before invocation. Body owner is
  never used. Existing review propagation is retained.
- Admin-created intake sends its validated resolved company_id in the direct job
  payload. Public/portal intake sends item.company_id in Step Functions input after
  the existing domain/auth resolution and request persistence.
- modules/workflow/main.tf CreateJob passes state input directly without Parameters;
  the extra field reaches the job consumer without a Terraform change.

Job consumer contract:

- Require canonical explicit stored request owner and exact REQ/CLIENT keys;
  optional stored request_id/client_id fields must agree when present.
- A supplied expected_company_id must be canonical and exactly match the request
  owner. A malformed supplied field (including null) is not a legacy omission.
- New jobs copy only that validated request owner. New creation without an expected
  owner returns EXPECTED_COMPANY_ID_REQUIRED_FOR_CREATION. No auth/default resolver
  is called by job_handler.
- Preflight all planned occurrences before pet creation, job writes or Calendar use.
  Existing children require exact JOB key, REQ relation and request-owner equality.
  A foreign later occurrence prevents earlier provider side effects too.
- Linked no-op replays validate every referenced child before returning. Canonical
  recovery reuses the same deterministic IDs and validated persisted children.
- Legacy input with no expected field may recover only a fully existing, ownership-
  validated occurrence set (or validate a linked no-op replay). If any new child
  is needed, the entire invocation fails before side effects and needs producer
  reissue. No primary fallback, implicit owner fill, or mixed recovery/creation
  escape path exists. Recovery-only runs do not invoke pet/profile creation.
- The persisted request is the source for inherited google_event_id. An absent/null
  input hint is ignored; a non-null hint is accepted only if exactly equal to the
  stored reference. Conflicting hints fail before side effects.

The asynchronous envelope is a constraint supplied by existing trusted services,
not authentication for arbitrary external JSON. Ownership is checked against stored
records. No new public job endpoint or new trust in request-body tenant data exists.

## Final complete Calendar mutation caller inventory

Locations are current candidate source. Sync's existing interface receives company
inside item; deletion receives company_id explicitly. No common interface changes.

| File under src/backend/handlers | Call/function | Trusted Calendar context |
| --- | --- | --- |
| review_handler.py:310 | handler sync | Validated persisted request owner pinned over Calendar copy |
| review_handler.py:351 | handler parent delete | Explicit validated request owner |
| review_handler.py:375 | handler child delete | Explicit child owner equal validated parent |
| cancellation_handler.py:254 | handle_admin_decision parent/child delete | Validated parent owner; children admitted only on exact owner equality |
| assignment_handler.py:208 | handler sync | Validated persisted job owner pinned over Calendar copy |
| admin_handler.py:3292 | handler lifecycle sync | Strictly validated current_item owner |
| admin_handler.py:3303 | handler lifecycle parent/single-job delete | Explicit strictly validated current_item owner |
| admin_handler.py:3322 | handler child delete | Explicit child owner after owner/key/relation validation |
| job_handler.py:205 | handler canonical recovery sync | Persisted job owner equal validated request and supplied expected owner, if present |
| job_handler.py:306 | handler new child sync | Validated request owner; required matching producer envelope |
| intake_handler.py:303 | _handle_admin_created_booking sync | Existing constructed/persisted item owner from trusted tenant resolution |

Common recursion, deletion wrapper and HTTP executor retain their S2A.3 behavior.
Repository search finds no other Calendar mutation consumers. Provider tags, secret
ownership, canonical ARN pinning and fail-closed binding are unchanged.

## S2D.2 and regression boundaries

The broad review/assignment {**persisted_item, **body} merges remain. Calendar owner
is pinned at the call boundary; generalized body field allowlists, ownership write
hardening, broader record/cascade integrity and event/schedule field authorization
are still S2D.2. This task does not claim end-to-end F02 completion.

OAuth expiry/replay/single-use (S2B), passive status refresh/write (S2C), generalized
S2D.2 and Platform target/provider behavior (S2E) are NOT STARTED / unchanged.
common/google_calendar.py, common/auth.py, google_auth_handler.py, platform handlers,
infra and modules are unchanged. No Terraform/state/lock/generated tracked files
changed. No provider policy/IAM/tag migration or tenant-resolution mode changes.

## Deployment interlock result

**YES — for the known source-level Calendar caller prerequisites.** All 11 legitimate
caller sites now carry explicit trusted tenant context, or deny genuinely missing/
foreign context. S2A.3 plus completed S2D.1 can later be considered together for
packaging/deployment after independent implementation review and explicit release
approval. The earlier admin/job caller-architecture interlock is resolved locally.

This is not deployment authorization or proof about live data/queues. Legacy new-
creation payloads without expected_company_id require reissue by a validated producer;
partial legacy recovery cannot create missing children. A later release must account
for this explicit contract and rollout the producer/consumer changes together.
No old-payload backfill, queue drain, live ownership inventory or production action
was attempted. Missing persisted ownership continues to fail closed by design.
S2A.3 remains NOT DEPLOYED; F02 UNRESOLVED; PTM-0 INCOMPLETE.

## Validation and failure classification

All tests ran with dummy credentials and socket/HTTP denial. Normal mode also blocks
unmocked AWS SDK operations. Moto mode permits in-process service mocks only.
The ignored runner imports no real provider data and performs no service requests.

- Final combined selection: **484 passed, 21 failed, 49 deprecation warnings**.
- All focused new prerequisites **94/94**, held propagation **47/47**, and S2A.3
  ownership **93/93** passed in that selection (234 focused tests).
- Separate S1 + R11E run: **122 passed, 2 failed, 2 warnings**; S1 **106/106 passed**.
- Baseline six handler modules executed in memory from starting SHA, selected terms/
  intake/job tests: **22 passed, same 21 failures, 3 warnings**.
- Baseline R11E: **16 passed, same 2 failures, 2 warnings**.
- Compilation passed for all 17 candidate Python files; tests imported all six changed
  handlers. git diff --check and candidate new-file whitespace checks passed.
- Final tested selections contain **zero new regressions**. The 23 remaining failures
  across combined/isolation runs are unchanged baseline failures, not waived new ones.

Expected security corrections in old fixtures: explicit canonical stored owners and
expected envelopes are now required; missing ownership no longer reaches mutations;
cancellation mocks/assertions must accept and verify company_id. Only the affected
workflow fixtures were adapted. Canonical job tests use test_company rather than
noncanonical test-company. Linked replay fixtures now return owned persisted children.
General scheduling/deduplication/404/notification assertions remain intact.

Initial workflow run before these fixture corrections was 95 passed / 39 failed;
initial additional canonical/terms run was 61 passed / 23 failed. The extra 32 and
9 failures respectively were expected ownership/envelope/signature corrections in
positive fixtures, subsequently fixed. During test authoring, three public-envelope
cases initially used the wrong domain-map fixture shape; that test setup was corrected
without runtime changes. Final results above supersede those intermediate runs.

The 21 baseline combined failures are listed below. Twenty are intake/terms tests
without the required trusted public domain mapping (500 vs expected 200/400), and
one is the existing missing visit_window assertion in noncanonical job expansion.
The unchanged R11E failures are test_review_handler_same_tenant_approved and
 test_pet_handler_get_same_tenant_succeeds (TenantDisabled 403 vs expected 200).
No unrelated fixture or runtime fix was used to hide these baseline failures.

- `test_r7e_multi_day_jobs.py::test_multi_day_jobs_inherit_visit_window`
- `test_intake_validation.py::test_valid_intake_succeeds`
- `test_intake_validation.py::test_missing_pet_names_rejected`
- `test_intake_validation.py::test_empty_pet_names_rejected`
- `test_intake_validation.py::test_status_injection_ignored`
- `test_intake_validation.py::test_missing_client_name_rejected`
- `test_intake_validation.py::test_whitespace_pet_names_validation`
- `test_r7s_terms_acceptance.py::test_valid_acceptance_succeeds`
- `test_r7s_terms_acceptance.py::test_missing_accepted_terms_rejected`
- `test_r7s_terms_acceptance.py::test_accepted_terms_false_rejected`
- `test_r7s_terms_acceptance.py::test_accepted_terms_string_truthy_rejected`
- `test_r7s_terms_acceptance.py::test_missing_accepted_privacy_rejected`
- `test_r7s_terms_acceptance.py::test_accepted_privacy_false_rejected`
- `test_r7s_terms_acceptance.py::test_missing_terms_version_rejected`
- `test_r7s_terms_acceptance.py::test_null_terms_version_rejected`
- `test_r7s_terms_acceptance.py::test_oversized_terms_version_rejected`
- `test_r7s_terms_acceptance.py::test_terms_version_at_max_length_accepted`
- `test_r7s_terms_acceptance.py::test_missing_privacy_version_rejected`
- `test_r7s_terms_acceptance.py::test_null_privacy_version_rejected`
- `test_r7s_terms_acceptance.py::test_oversized_privacy_version_rejected`
- `test_r7s_terms_acceptance.py::test_privacy_version_at_max_length_accepted`

| Suite | Passed | Baseline failures |
| --- | ---: | ---: |
| test_ptm0_s2d1b_prerequisites.py | 94 | 0 |
| test_ptm0_s2d1_calendar_context.py | 47 | 0 |
| test_ptm0_s2a3_provider_binding.py | 93 | 0 |
| test_r9a_admin_lifecycle.py | 6 | 0 |
| test_r7e_multi_day_jobs.py | 21 | 1 |
| test_ryan_slice_b_check_in_transactions.py | 31 | 0 |
| test_r7e_cancellation.py | 2 | 0 |
| test_r18p_cancellation_cascade_fix.py | 9 | 0 |
| test_r7g_assignment_multiday.py | 5 | 0 |
| test_r7d_calendar_hardening.py | 18 | 0 |
| test_public_intake_tenant_routing.py | 35 | 0 |
| test_intake_validation.py | 0 | 6 |
| test_ryan_release_readiness_hardening_r1.py | 3 | 0 |
| test_ryan_o1_overnight_fixed_scheduling.py | 22 | 0 |
| test_ryan_w1_walk_canonical_scheduling.py | 20 | 0 |
| test_r7s_terms_acceptance.py | 1 | 14 |
| test_ryan_slice_e3a_child_start_and_occurrences.py | 24 | 0 |
| test_r6g_calendar_all_day.py | 12 | 0 |
| test_r6g_calendar_health.py | 8 | 0 |
| test_r6g_calendar_retry.py | 14 | 0 |
| test_r6g_calendar_token.py | 6 | 0 |
| test_r9c_google_calendar_banner.py | 5 | 0 |
| test_r21g_google_token_isolation.py | 8 | 0 |

## Reproduction and evidence

Local ignored evidence files:
- scratch/ptm0_s2d1/completed-validation.txt and completed-validation.xml
- scratch/ptm0_s2d1/implementation-isolation.txt
- scratch/ptm0_s2d1/baseline-implementation.txt
- scratch/ptm0_s2d1/baseline-isolation-final.txt

The ignored offline runner's --baseline-handlers option now restores all six candidate
handlers from the starting SHA in memory; it never checks out/reset files. The
architecture/old partial records remain historical evidence.

```powershell
python scratch/ptm0_s2d1/offline_tests.py tests/backend/test_ptm0_s2d1b_prerequisites.py tests/backend/test_ptm0_s2d1_calendar_context.py tests/backend/test_ptm0_s2a3_provider_binding.py tests/backend/test_r9a_admin_lifecycle.py tests/backend/test_r7e_multi_day_jobs.py tests/backend/test_ryan_slice_b_check_in_transactions.py tests/backend/test_r7e_cancellation.py tests/backend/test_r18p_cancellation_cascade_fix.py tests/backend/test_r7g_assignment_multiday.py tests/backend/test_r7d_calendar_hardening.py tests/backend/test_public_intake_tenant_routing.py tests/backend/test_intake_validation.py tests/backend/test_ryan_release_readiness_hardening_r1.py tests/backend/test_ryan_o1_overnight_fixed_scheduling.py tests/backend/test_ryan_w1_walk_canonical_scheduling.py tests/backend/test_r7s_terms_acceptance.py tests/backend/test_ryan_slice_e3a_child_start_and_occurrences.py tests/backend/test_r6g_calendar_all_day.py tests/backend/test_r6g_calendar_health.py tests/backend/test_r6g_calendar_retry.py tests/backend/test_r6g_calendar_token.py tests/backend/test_r9c_google_calendar_banner.py tests/backend/test_r21g_google_token_isolation.py
python scratch/ptm0_s2d1/offline_tests.py --moto tests/backend/test_ptm0_s1_untagged_isolation.py tests/backend/test_r11e_tenant_enforcement.py
python scratch/ptm0_s2d1/offline_tests.py --baseline-handlers tests/backend/test_r7s_terms_acceptance.py tests/backend/test_intake_validation.py tests/backend/test_r7e_multi_day_jobs.py
python scratch/ptm0_s2d1/offline_tests.py --moto --baseline-handlers tests/backend/test_r11e_tenant_enforcement.py
git diff --check
```

## Exact final candidate / ending hygiene

Runtime (6 modified):
- src/backend/handlers/admin_handler.py
- src/backend/handlers/assignment_handler.py
- src/backend/handlers/cancellation_handler.py
- src/backend/handlers/intake_handler.py
- src/backend/handlers/job_handler.py
- src/backend/handlers/review_handler.py

Tests (9 modified, 2 new):
- tests/backend/test_r18p_cancellation_cascade_fix.py
- tests/backend/test_r7e_cancellation.py
- tests/backend/test_r7e_multi_day_jobs.py
- tests/backend/test_r7g_assignment_multiday.py
- tests/backend/test_r9a_admin_lifecycle.py
- tests/backend/test_ryan_o1_overnight_fixed_scheduling.py
- tests/backend/test_ryan_release_readiness_hardening_r1.py
- tests/backend/test_ryan_slice_b_check_in_transactions.py
- tests/backend/test_ryan_w1_walk_canonical_scheduling.py
- tests/backend/test_ptm0_s2d1_calendar_context.py (new held test)
- tests/backend/test_ptm0_s2d1b_prerequisites.py (new prerequisite test)

Docs (2 untracked candidate records, updated):
- docs/reviews/ptm0-s2d1-calendar-tenant-context-local.md
- docs/reviews/ptm0-s2d1b-admin-job-ownership-architecture.md

Total: 19 candidate files, all unstaged. Two pre-existing untracked S2A.2d evidence
records are excluded/preserved. Ending HEAD/local origin/main equal starting SHA.
Index and stash empty. Worktree intentionally dirty: 15 modified tracked files,
4 untracked candidate files and the 2 pre-existing untracked evidence documents.
Ignored runner/log/XML/bytecode are local test artifacts, not release packaging.

Staging, commits, pushes, remote Git operations, production/AWS/Google access,
Terraform operations, RC packaging and deployments: ZERO. Stop for independent
local implementation review. No later-slice implementation is authorized here.

---

# Historical held S2D.1 record (superseded by completed disposition above)

# PTM0-S2D.1 Calendar tenant context propagation â€” local record

Date: 2026-09-06

Disposition: **PTM0_S2D1_ARCHITECTURE_DEPENDENCY**

A bounded local candidate is implemented for callers with a validated tenant source.
It is UNSTAGED, NOT independently reviewed, NOT committed, NOT pushed, NOT packaged,
and NOT deployed. This is not a completed S2D.1 or deployment approval.

## Checkpoint and hygiene

Starting branch `main`; HEAD and local `origin/main` both:
`3272267c224505240be20656c4111fd02733a998`.
Tracked worktree clean; index empty; stash empty. No remote Git operation was needed
or performed in this task. Two existing untracked documents were preserved unchanged:

- `docs/reviews/ptm0-s2a2d-r1-targeted-convergence-verification.md`
- `docs/reviews/ptm0-s2a2d-terraform-convergence-plan-preflight.md`

S2A.1 and S2A.2 remain COMPLETE. S2A.3 remains IMPLEMENTED / INDEPENDENTLY REVIEWED /
COMMITTED / PUSHED / NOT DEPLOYED. F02 remains UNRESOLVED; PTM-0 INCOMPLETE.

## Source review and complete mutation inventory

Search covered all `src` files for `sync_calendar_event`, `delete_event`,
`delete_event_detailed`, `_execute_calendar_api`, and the Google Calendar API URL.
A separate Python search outside `src/backend`, tests and scratch found no other
mutation consumers. Imports without calls are not additional call sites.
OAuth/token exchange is not a Calendar event mutation and was not changed.

All source locations in this table refer to the starting SHA, so they remain
reproducible. `sync_calendar_event` accepts tenant identity inside `item['company_id']`;
it has no standalone `company_id` keyword. Pinning that field at the call boundary
preserves the existing interface. There are 11 external mutation call sites.

| File under src/backend; function; original line | Operation | Original tenant source and validation | Explicit company / permits None before | Body influence before | S2D.1 action | S2D.2 / remaining dependency |
| --- | --- | --- | --- | --- | --- | --- |
| handlers/review_handler.py; handler; 308 | Create/update | Persisted request validated by validate_tenant_ownership at 149, then merged with body | Item field only; merge permits None | YES: body overwrites company_id | Pin Calendar-only copy to validated request company; reject missing before call | YES: general merge remains unchanged; other body-controlled fields still require review |
| handlers/review_handler.py; handler; 345 | Delete parent event | Persisted request event ID and validated request owner | NO; omitted becomes None | Body selects requested record; owner check exists; body company not used | Explicit company_id=request_item['company_id']; no missing fallback | General body hardening deferred; this deletion uses persisted identity |
| handlers/review_handler.py; handler; 364 | Delete child job event | Parent validated; child fetched by persisted parent job_ids and request key, but child owner not checked | NO; omitted becomes None | No direct body owner; child relation previously unchecked | Require explicit child owner equal validated parent; pass child owner; retain reference on false/exception | Broader cascade/record-write ownership review deferred |
| handlers/cancellation_handler.py; handle_admin_decision; 248 | Deduplicated parent/child deletion | Parent validated at 155; child fetched from parent's job_ids; local company variable had primary fallback and was only logged | NO; omitted becomes None | Body company not read; child owner previously unchecked | Remove local primary fallback; require matching explicit child owner before collection; pass validated company for each accepted event; missing parent denied | General workflow/cascade authorization hardening remains separate |
| handlers/assignment_handler.py; handler; 206 | Create/update job event | Each persisted job validated at 161; request also validated if present; then body merge | Item field only; merge permits None | YES: body overwrites company_id | Pin Calendar-only copy to validated job company; reject missing before call | YES: general merge remains; other body fields not hardened |
| handlers/admin_handler.py; handler / admin requests lifecycle; 3272 | Create/update | current_item from _resolve_admin_record; direct/swapped lookups return without ownership check; only scan path filters | Item field; missing permitted | Body controls PK/SK/records; this sync dictionary adds only status, not body company | STOP for this site; unchanged | Prior object validation must be reviewed before safe propagation; classify as S2D.2/caller-validation dependency, without implementing it here |
| handlers/admin_handler.py; handler / admin requests lifecycle; 3283 | Delete request or single job event | Same unvalidated current_item; _action_company_id is resolved but not compared with direct result | NO; omitted becomes None | Body selects record keys; no direct body company merge at this site | STOP; unchanged | Same object-validation dependency; omission remains a deployment blocker |
| handlers/admin_handler.py; handler / admin requests lifecycle; 3294 | Delete child job event | Neither direct parent nor child is established as same-tenant at this boundary | NO; omitted becomes None | Body selects parent; child IDs from persisted parent | STOP; unchanged | Parent/child ownership and false-result handling must be reviewed; omission remains a deployment blocker |
| handlers/job_handler.py; handler; 164 | Recover canonical child event (create/update) | existing_job read by deterministic key; no tenant ownership validation against request; request itself has no tenant ownership check in handler | Item field; None permitted | Invocation IDs select request; no HTTP body merge in this handler | STOP; unchanged | Trusted asynchronous invocation/request/child relationship needs an explicit reviewed contract; do not invent it here |
| handlers/job_handler.py; handler; 268 | Create/update new child event | item company from request_item.get('company_id') OR get_current_company_id(event); no request ownership validation | Item field populated, but may be manufactured primary in single mode | Invocation IDs select request; no direct body company merge | STOP; unchanged | Remove fallback only as part of separately reviewed trusted-source design; not implemented |
| handlers/intake_handler.py; _handle_admin_created_booking; 302 | Create parent event | Authenticated tenant resolved at 146, existing client fetched in company partition and mismatch checked; newly constructed/persisted item has explicit company | YES, item field; resolver returns tenant or raises | body company not copied; booking-window expansion supplies schedule fields only | No change required: existing explicit resolved tenant field is already propagated | No company-merge fix at this call; tenant-resolution mode remains unchanged |

Internal equivalents in unchanged `common/google_calendar.py`:

| Function and original line | Operation and tenant handling | Disposition |
| --- | --- | --- |
| sync_calendar_event -> _execute_calendar_api at 627 | POST/PATCH uses token acquired from the item's S2A.3-validated company; private executor takes token, not a company argument | Unchanged; no external executor callers found |
| sync_calendar_event recursion at 658 | Remote 404 recovery reuses the same item (including company) for create | Unchanged; S2A.3 revalidates; missing context fails before API access |
| delete_event -> delete_event_detailed at 743 | Wrapper explicitly forwards its company argument; callers may still omit it | Unchanged; binding denial returns false |
| _execute_calendar_api at 559 / delete_event_detailed at 724 | Actual HTTP mutation transport uses previously obtained token | Unchanged; no new token selection or resolution |

## Implemented propagation and safety boundaries

Only three runtime files changed: review, cancellation and assignment handlers.
The common provider module is byte-for-byte unchanged relative to HEAD.

Review parent deletion changes from two arguments (implicit None) to explicit
persisted validated request company. Child deletion additionally requires the
child company to equal the nonmissing validated parent company. A false provider
result now retains the child's event reference, does not count as deleted, and
produces calendar_failed in the review result. This small response/reference
change is required to preserve S2A.3 denial semantics at the changed caller.

Cancellation removes its local primary fallback. It includes a child in the
existing event-ID deduplication only after exact owner equality with the validated
parent. The collected events all have that one validated owner, passed explicitly
to delete_event_detailed. Missing parent context raises within the existing
Calendar failure path. Mismatched/missing child context records a sync failure and
keeps the child reference. Parent/child same-owner event deduplication and 404
cleanup remain supported; a mismatched child is never included in reference cleanup.

Review and assignment sync receive a call-local copy that pins company_id to the
already validated persisted object. The existing sync_data merge and other fields
are unchanged. No body-supplied owner is newly trusted. This is the narrowly allowed
Calendar propagation adjustment, not generalized body-merge remediation.

No default tenant constant, query parameter or body company is used by a changed
Calendar call. Missing persisted company blocks the call even where the unchanged
legacy ownership validator would accept an untagged primary record. The common
resolver continues to validate canonical tenant syntax and provider ownership.
No metadata migration for untagged records was attempted.

## Architecture dependencies and deployment interlock

**NO â€” S2D.1 does not remove every legitimate Calendar caller dependency.**

1. Admin lifecycle direct/swapped record lookup lacks ownership validation. Merely
   passing `_action_company_id` would select a caller Calendar for an unvalidated
   event object; passing current_item's owner could target a foreign Calendar.
   Neither is safe propagation. All three admin mutation sites were left unchanged.
   The two deletions still omit company and therefore fail closed under S2A.3.
   The unchanged child branch also removes references without checking delete_event's
   false return; this must be included in the later caller review.
2. Job creation/recovery lacks an established validated request/child owner contract
   at these call sites. Its fallback can manufacture a primary company from a
   missing request owner. Internal invocation is mentioned in the handler docstring,
   but that alone is not evidence of per-object tenant validation. No claim is made
   here about public exposure or live IAM; neither was accessed. The trusted-source
   prerequisite must be reviewed before modifying these sites.
3. Legitimate records that truly lack an explicit persisted tenant remain denied
   in the changed paths. Any required legacy-data treatment needs separate review;
   this task does not infer ownership, backfill records or restore a fallback.

These are stop conditions for the affected sites under the user's trusted-source
rule. They are documented for S2D.2/caller-architecture review, not implemented or
silently broadened into this slice. S2A.3 plus this partial candidate must NOT be
considered ready for RC/deployment.

S2B (OAuth expiry/replay/single use), S2C (passive GET refresh/write), S2D.2 (general
body/record ownership hardening), and S2E (Platform target/provider behavior) remain
NOT STARTED / unchanged. No Platform handler or auth resolver was changed.
TENANT_RESOLUTION_MODE, provider policy, IAM/tags, Terraform and tenant configuration
are unchanged. S2A.3 ownership semantics and fail-closed resolver are preserved.

## Tests and exact results

New `tests/backend/test_ptm0_s2d1_calendar_context.py`: 47 passing parameter cases.
These call real review, cancellation and assignment handlers with real ownership
validation and mocked DB/Calendar/notification boundaries. They cover:

- Primary, Alpha and future tenant parent/child deletion propagation.
- Create/update sync with and without existing event IDs, despite foreign body company.
- Missing/empty persisted owner, including review sync, cannot become primary.
- Foreign caller cannot mutate a primary record at the changed handlers.
- Missing/foreign child owner is excluded from deletion and reference cleanup.
- False provider deletion preserves references; review reports calendar_failed.
- Failed provider sync does not persist a new Calendar event reference.

Updated existing fixtures/assertions in R7E cancellation, R18P cancellation and
R7G assignment supply explicit stored tenants and explicit claims. Cancellation
assertions require the company keyword. No production fallback is mocked into the
new tests. Existing deduplication, 404, failure, notification and assignment cases
remain passing (16/16 across those three suites).

The requested positive admin propagation test is NOT claimed satisfied: admin
implementation is blocked by the source-validation dependency above. Likewise no
claim is made that the unmodified job callers meet the full S2D.1 invariant.

Offline runner uses dummy credentials, EC2 metadata disabled, socket connect and
HTTP send denial; normal mode also blocks unmocked SDK calls. Moto mode permits
only in-process SDK dispatch and retains the network guards. All provider data is
fabricated. Local ignored runner: `scratch/ptm0_s2d1/offline_tests.py`, derived from
the existing S2A.3 runner. `--baseline-handlers` executes the three original handler
modules from the exact starting SHA in memory, without checkout/reset or edits.

| Validation | Result |
| --- | --- |
| Final new propagation tests + S2A.3 provider tests + workflow selection below | 267 passed, 7 failed, 28 deprecation warnings |
| New propagation tests within final selection | 47/47 pass |
| Unmodified S2A.3 provider binding tests within final selection | 93/93 pass |
| R7E cancellation + R18P cancellation + R7G assignment after fixture updates | 16 passed, 5 deprecation warnings |
| S1 untagged isolation + R11E tenant enforcement, Moto offline | 122 passed, 2 failed, 2 deprecation warnings (S1: all 106 pass) |
| Baseline handlers: R7E jobs + intake validation | 21 passed, same 7 failures |
| Baseline handlers: R11E tenant enforcement | 16 passed, same 2 failures |
| Compile changed runtime/test files | PASS |
| git diff --check and new-file trailing whitespace check | PASS |
| Protected common/admin/job/intake/OAuth/auth files vs HEAD | Unchanged |

The seven final workflow failures reproduce unchanged at the starting checkpoint:

- `test_r7e_multi_day_jobs.py::test_multi_day_jobs_inherit_visit_window`:
  KeyError for expected `visit_window` (job handler unchanged).
- `test_intake_validation.py`: `test_valid_intake_succeeds`,
  `test_missing_pet_names_rejected`, `test_empty_pet_names_rejected`,
  `test_status_injection_ignored`, `test_missing_client_name_rejected`,
  `test_whitespace_pet_names_validation`: absent trusted public domain mapping
  yields 500 instead of expected 200/400 (intake handler unchanged).

The two R11E failures also reproduce at baseline:
`test_review_handler_same_tenant_approved` and
`test_pet_handler_get_same_tenant_succeeds`: TenantDisabled 403 instead of 200.
No unrelated test defects or runtime behavior were repaired to make these pass.
The initial workflow run before adapting explicit-owner fixtures was 116 passed /
18 failed; after fixture corrections only the seven baseline failures remain.
The initial focused run was 136 passed (43 new + 93 provider); four additional
cases added afterward are included in the final selection above.

Reproduction from repository root:

```powershell
python scratch/ptm0_s2d1/offline_tests.py tests/backend/test_ptm0_s2d1_calendar_context.py tests/backend/test_ptm0_s2a3_provider_binding.py tests/backend/test_r7e_cancellation.py tests/backend/test_r18p_cancellation_cascade_fix.py tests/backend/test_r7g_assignment_multiday.py tests/backend/test_r9a_admin_lifecycle.py tests/backend/test_r7e_multi_day_jobs.py tests/backend/test_ryan_slice_b_check_in_transactions.py tests/backend/test_r7d_calendar_hardening.py tests/backend/test_public_intake_tenant_routing.py tests/backend/test_intake_validation.py
python scratch/ptm0_s2d1/offline_tests.py --moto tests/backend/test_ptm0_s1_untagged_isolation.py tests/backend/test_r11e_tenant_enforcement.py
python scratch/ptm0_s2d1/offline_tests.py --baseline-handlers tests/backend/test_r7e_multi_day_jobs.py tests/backend/test_intake_validation.py
python scratch/ptm0_s2d1/offline_tests.py --moto --baseline-handlers tests/backend/test_r11e_tenant_enforcement.py
```

The S1/R11E run used the equivalent original S2A.3 runner in Moto mode. The
baseline extension does not affect normal or Moto behavior. Final workflow output
is retained locally in ignored `scratch/ptm0_s2d1/final-workflows.txt`.

## Exact candidate and final boundaries

Modified tracked, all UNSTAGED:

1. `src/backend/handlers/assignment_handler.py`
2. `src/backend/handlers/cancellation_handler.py`
3. `src/backend/handlers/review_handler.py`
4. `tests/backend/test_r18p_cancellation_cascade_fix.py`
5. `tests/backend/test_r7e_cancellation.py`
6. `tests/backend/test_r7g_assignment_multiday.py`

New untracked candidate:

7. `tests/backend/test_ptm0_s2d1_calendar_context.py`
8. `docs/reviews/ptm0-s2d1-calendar-tenant-context-local.md` (this record)

The two pre-existing S2A.2d records remain untracked and excluded. Ignored runner,
log and Python bytecode are local validation artifacts, not release packaging.
No common/provider, admin, job, intake, OAuth, Platform, Terraform, state, lock or
generated tracked files changed. No tenant-resolution mode or secret policy changes.

Ending HEAD/local origin/main remain the starting SHA. Index and stash remain
empty. Tracked worktree intentionally contains the six unstaged modifications;
not claimed clean. No files staged, commits, pushes, RCs or deployments.
Production/AWS/Google access: ZERO. Terraform operations: ZERO.
Stop for independent review of this bounded candidate and the unresolved caller
architecture. No S2D.2 implementation or deployment is authorized by this record.
