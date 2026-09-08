# S2D.1B implementation reconciliation � 2026-09-08

User supplied independent architecture disposition:
`PTM0_S2D1B_INDEPENDENT_NARROW_PREREQUISITE_APPROVED`.

The subsequent authorized implementation is now incorporated into the completed
local S2D.1 candidate. See [current implementation record](ptm0-s2d1-calendar-tenant-context-local.md).
It is ready for independent implementation review, not committed/pushed/deployed.
The current source-level Calendar caller deployment interlock answer is YES, subject
to that later review/release decision and the documented legacy producer-reissue rule.

The user's implementation instructions superseded this architecture record's
blanket rejection of omitted expected_company_id: safe legacy recovery is permitted
only where existing persisted request/job relationships establish equal ownership.
New creation without the envelope fails closed. The implementation preflights all
occurrences before side effects, including for mixed legacy recovery/new-child input.
No general S2D.2, provider resolver, OAuth, Platform or Terraform changes were made.

The original architecture review below is retained as historical design evidence;
its hold/no-deployment conclusions described the then-partial candidate. Neither
architecture approval nor this reconciliation is independent implementation approval.

---

# PTM0-S2D.1B — Admin/job ownership prerequisite architecture review

Date: 2026-09-08

Disposition: **PTM0_S2D1B_NARROW_PREREQUISITE_CHANGE_REQUIRED**

Architecture review only. No prerequisite implementation is included. The current
S2D.1 candidate remains at PTM0_S2D1_ARCHITECTURE_DEPENDENCY, unstaged and uncommitted.
This review refines the earlier deferral: the examined blockers fit a narrow
ownership-validation and producer/consumer propagation contract (category A),
without implementing generalized S2D.2 body-override prevention.

## Checkpoint and evidence limits

Branch main; HEAD and local origin/main both
`3272267c224505240be20656c4111fd02733a998`. No remote fetch or verification performed.
Index and stash empty. Starting tracked modifications: assignment_handler.py,
cancellation_handler.py, review_handler.py, test_r18p_cancellation_cascade_fix.py,
test_r7e_cancellation.py, test_r7g_assignment_multiday.py. Existing untracked candidate:
test_ptm0_s2d1_calendar_context.py and ptm0-s2d1-calendar-tenant-context-local.md.
The two pre-existing S2A.2d documents remain untracked and untouched.

Source paths below are repository-relative; line numbers are current local source.
Admin, job, auth, DB and infrastructure source are unchanged from the checkpoint.
Review source contains the existing S2D.1 candidate. Read-only inspection of .tf
source is not a Terraform operation. No state, cloud resources, credentials, tenant
records, queues, secret values or provider endpoints were inspected.

## Complete unresolved admin inventory

All three calls occur in `src/backend/handlers/admin_handler.py::handler`, the
catch-all `elif http_method == 'POST'` branch at line 3018. The configured API route
is POST /admin/requests: `modules/api/main.tf:222-244` declares Cognito authorization
and AWS_PROXY integration. The function's branch itself is not restricted to that
exact path; earlier POST branches consume their own special routes.

| Call | Operation/trigger | Persisted object and loader | Current validation | Correct Calendar owner |
| --- | --- | --- | --- | --- |
| admin_handler.py:3272, sync_calendar_event | Non-multiday APPROVED/ASSIGNED/BOOKED/SCHEDULED; also UNARCHIVE and test-flag operations when effective status meets those values | current_item, a selected request or job, via _resolve_admin_record(body PK/SK or each records entry) | None on direct/swapped returns; scan-only owner filtering | Exact nonmissing current_item.company_id after comparing with authenticated tenant and validating returned record identity |
| admin_handler.py:3283, delete_event | Non-multiday CANCELLED/ARCHIVED/DELETED | Same current_item; google_event_id from that persisted object | Same gap; company argument omitted, therefore None | Validated current_item.company_id passed explicitly |
| admin_handler.py:3294, delete_event | Multiday request cleanup; completed children preserved | Parent current_item, then get_item('JOB#'+jid, actual_parent_pk), jid from persisted parent.job_ids | Neither parent nor child is verified at this boundary; company omitted; false delete return ignored | Explicit child.company_id after strict equality to validated parent owner and request relationship verification |

`_resolve_admin_record` at 266 loads direct PK/SK (275), then swapped PK/SK (280),
then scans for partial raw IDs (300). Direct and swapped results return immediately.
Only scan results at 306-311 compare company, and they treat missing owners as
DEFAULT_COMPANY_ID. `common.db.get_item` (18) is just a base-table get; it does not
validate ownership or request strong consistency. A comment describing a scoped
lookup is not proof that all lookup paths enforce scope.

Authenticated context exists: `_action_company_id = get_current_company_id(event)`
at 3152. It is passed to the loader but is not compared to the direct/swapped object.
The earlier require_active_tenant call (504) checks caller entitlement, not object
ownership. The role gate allows owner/admin/staff; six lifecycle actions additionally
require owner/admin. Preserve those gates in the prerequisite.

This is the tenant data-plane route, not a Platform explicit-target operation.
A platform_admin-only effective role is rejected. A principal also carrying owner,
admin or staff may enter under that role because of get_effective_role precedence
(`common/auth.py:41-69`); that does not grant cross-tenant Calendar access. No
is_platform_admin bypass is called in these branches. Other Platform helpers in
the same file do not establish permission for these Calendar calls. Do not add a
Platform override; S2E remains separate.

Body/query/default analysis:

- No body or query company_id is read for these calls. The sync dictionary is
  `{**current_item, 'status': effective_new_status}`, not a broad body merge.
- Body does control PK/SK and the records array. An attacker can select a foreign
  object without changing its stored company. This is an object-authorization gap.
- A bulk list can mix arbitrary tenant records; there is no uniform-tenant preflight
  or mandatory per-result owner check. Current direct lookups can return all of them.
- get_current_company_id can default in single mode (`common/auth.py:247-285`), and
  the scan filter maps missing owner to DEFAULT_COMPANY_ID. Neither is acceptable
  as proof of an explicit stored Calendar owner.
- The generic validate_tenant_ownership helper also maps missing stored ownership
  to primary and returns for non-dictionaries (287-299). Calling it alone is
  insufficient for this strict prerequisite.

## Minimum admin validation/propagation contract (proposed only)

1. Resolve the existing authenticated tenant once. For this Calendar-bearing path,
   require explicit authenticated tenant evidence; if the claim is missing, do not
   let a default resolver result establish Calendar authorization. This is a local
   prerequisite, not a change to TENANT_RESOLUTION_MODE or global auth helpers.
2. Treat record lookup as candidate selection. After every direct, swapped or healed
   lookup, require an actual dictionary with an explicit canonical company_id,
   exact returned PK/SK matching the resolved keys, and owner equality to the
   authenticated tenant. A targeted consistent re-read of the resolved key can
   supply the validation snapshot; do not change the global DB helper.
3. Apply that check before the selected lifecycle record's status update, audit,
   notifications or Calendar use. A Calendar-only check after mutating a foreign
   record would leave the same operation internally inconsistent. Keep denial
   generic, record it per item, and continue only with authorized bulk entries.
   No tenant-switching within a batch. If healing cannot identify one intended
   authorized record unambiguously, deny rather than select an arbitrary match.
4. For child Calendar deletions, load the exact child key, require child owner equal
   validated parent owner, child PK equal requested JOB key, and SK/request relation
   equal parent REQ key. Never fill a child's missing owner from its parent.
5. Supply the validated persisted owner explicitly: item field for sync, company_id
   keyword for deletion. Keep completed-child preservation and event IDs from the
   persisted object. Only remove references/count success after successful deletion;
   retain references on false/exception. Report partial cleanup failures accurately.
6. Keep PURGE, other unrelated admin routes, global record healing, and general
   cascade integrity outside this prerequisite. Put the strict check in the affected
   lifecycle path or an opt-in helper; changing _resolve_admin_record globally would
   also alter its PURGE callers. Broader child-record cascade hardening stays S2D.2.

Missing or malformed ownership fails closed, including untagged primary objects.
The canonical ID shape must agree with S2A.3; do not normalize or invent identity.
Provider tags/ARN validation remains entirely in the unchanged S2A.3 resolver.
Validation is not an atomic ownership lock; no cross-service atomicity claim is made.
A concurrent ownership-transfer protocol would be separate scope, not a reason to
silently broaden this prerequisite into a record-integrity rewrite.

## Complete unresolved job inventory and invocation chain

Both calls are in `src/backend/handlers/job_handler.py::handler`, an asynchronous
Lambda entry point, not an API route. Local wiring: `infra/prod/main.tf:198-202`
defines handlers.job_handler.handler; workflow module receives its ARN at 550.

| Call | Object and current tenant source | Validation/replay facts | Required source |
| --- | --- | --- | --- |
| job_handler.py:164, sync_calendar_event(existing_job) | Existing canonical occurrence job read at 156 by deterministic JOB key and originating REQ key | Runs if calendar_event_id exists but google_event_id does not; no request/child tenant comparison before Calendar call or subsequent relinking | Explicit stored child owner equal validated originating request owner and trusted invocation expected tenant |
| job_handler.py:268, sync_calendar_event(item) | New child item at 194; company copied from local company_id | company_id at 59 is request owner OR get_current_company_id(event); no request ownership validation; canonical children persisted before Calendar, other multiday children afterward | Copy only validated originating request owner into constructed child; no fallback |

Job reads the request using invocation request_id/client_id at 35. It validates
schedule fields, not tenant ownership. Existing parent job links cause an early
return at 47-56. Deterministic occurrence names use request/date/window plus a static
`togs-and-dogs:` namespace string; that string is not tenant authorization and must
not be repurposed as such. Existing deterministic IDs need not be changed.

The existing fallback at 59 manufactures DEFAULT_COMPANY_ID (normally tog_and_dogs)
for a missing request owner in single mode; multi mode raises when claims are absent.
Ordinary job invocations have no HTTP authorizer claims. A truthy request owner is
copied without comparison to an independent expected tenant. A job's persisted
SK/request relationship is useful evidence but alone cannot prove equal ownership.

There is no dictionary body merge into the new job. Top-level input company_id is
currently ignored. Input IDs select the source request. Separately, line 140 prefers
input google_event_id over persisted request google_event_id for single-day linkage;
that can affect future Calendar targets even though it does not override company_id.
The narrow design should take inherited event identity from the validated persisted
request; if the old event hint is retained, require equality and reject disagreement.
This is an explicit event-reference input rule, not generalized body-merge hardening.

Three producer sites are present in repository source:

| Producer | Existing validation/source | Current payload |
| --- | --- | --- |
| review_handler.py:393-402 | Request read and validate_tenant_ownership at 140-147; approved transition invokes job Lambda | request_id, client_id, google_event_id; no tenant |
| intake_handler.py::_handle_admin_created_booking, 270-278 | Resolved authenticated tenant, company-scoped client lookup and newly persisted request with company | request_id, client_id; no tenant |
| intake_handler.py::handler, 559-566 -> modules/workflow/main.tf:30-33 | New persisted request company from authenticated portal tenant or validated public domain mapping | request_id, client_id, status; no tenant; CreateJob passes state input without a Parameters projection |

The Step Functions choice reads payload status rather than reloading the database;
its wait/status progression is separate workflow behavior, not repaired here.
Repository IAM grants Lambda/Step Functions broad InvokeFunction permissions
(`modules/iam/main.tf:142,166`, Resource '*'). This supports a service invocation
model, not per-tenant authorization. It does not prove live configuration or that
an arbitrary tenant value in a payload is trustworthy. No job API integration was
found in the examined modules. This review does not claim exclusive live invokers.

## Minimum job contract (proposed only)

For an authenticated producer:

`persisted job.company_id == validated request.company_id == expected_company_id`

with expected_company_id captured by that producer from the authenticated tenant
and matched to the request before dispatch. For public intake, the last equality
is to its validated domain-mapped tenant, not an invented authenticated user.
For asynchronous execution, the envelope carries the original validated scope;
the consumer must not call an HTTP tenant resolver on a service event.

1. Add an explicit expected_company_id to all three producer payloads, sourced only
   from their validated/persisted request context. Require explicit nonmissing owner
   before dispatch; never take this field from request body/query/default. The
   existing Step Functions input pass-through can carry it without a Terraform edit.
2. At job entry, require that expected tenant and a canonical persisted request owner
   match exactly; validate exact REQ/CLIENT keys and supplied IDs. Read the request
   from the authoritative table (a targeted consistent read is preferable). Do this
   before the idempotent return, pet/profile work, job writes, or Calendar actions.
   Stored request data is the owner source; the expected tenant is a scope constraint,
   not an ownership override. Missing either value is a denial.
3. Copy that owner into new children. For recovery, require the exact persisted job
   key and relationship, explicit company equality, and expected occurrence identity
   before provider use or relinking. A missing owner cannot be reconstructed from
   an event name, default or UUID. Failed checks must not relink foreign children.
4. Do not synthesize authenticated claims at the consumer. Invocation transport is
   trusted only for authorized producer services; adding an envelope does not turn
   arbitrary JSON into authenticated evidence. Confirm the allowed producer contract
   in the later implementation/release review. If an additional producer is found,
   it must satisfy the same rule before release. No IAM change is proposed here.
5. Preserve deterministic IDs, replay behavior, scheduling and provider binding.
   Resolve inherited Calendar event identity from the validated request as above.
   Validate already-linked replay owner scope before returning; no need to add
   Calendar writes to the existing no-op replay branch.
6. Old queued/replayed payloads have no expected_company_id. They must fail closed;
   a later explicit release procedure must reissue them through a validated producer
   or otherwise establish a separately reviewed compatibility path. Do not implement
   a silent legacy-envelope fallback. No queue/backlog count was inspected here.

This updates both ends of a small invocation contract. It is category A across a
few files, not evidence that a broad multi-component architecture refactor is needed.
A parent-only scheme would be smaller syntactically but would not bind the requested
record to the tenant whose operation initiated the asynchronous work.

## Relation to S2D.2 and proposed slices

A — recommended: strict local object validation plus explicit propagation, including
producer/consumer expected scope and event-reference equality. A small pure helper
can centralize canonical owner/equality checks if useful; it must not alter provider
policy or the legacy global auth helper. It is optional, not a new registry/service.

B — not a prerequisite for these five calls: no broad body merge sets their owner.
Body-selected record IDs need authorization, which is covered above. Review and
assignment's broader merge semantics remain a separate S2D.2 concern.

C — not justified by the source evidence: no schema migration, ownership backfill,
new job ID scheme, workflow redesign or general cascade rewrite is required to
express the narrow Calendar ownership contract. Discovered corrupt/untagged data
must be denied and separately handled, not silently repaired.

D — not currently required. Reassess if additional untrusted invocation producers
or incompatible data contracts appear during the bounded implementation review.

Recommended decomposition (future authorization required):

- Admin prerequisite: strict validation in the lifecycle branch, child relationship
  checks, explicit Calendar owner, and deletion false-result handling; tests/docs.
- Job prerequisite: request/child validation in job_handler plus expected tenant at
  the review and two intake dispatch sites; tests/docs and legacy-envelope handling
  specification. This needs small edits in review_handler/intake_handler, but no
  common/google_calendar.py, global auth, OAuth, Platform or Terraform changes.
- Independent review of the combined S2D.1 candidate and these prerequisites, followed
  by a separate commit/push authorization and later explicit release decision.
- Keep generalized S2D.2, S2B, S2C and S2E deferred. Do not label F02 complete.

## Commit and deployment options

1. Independent commit/push of the current safe subset, kept undeployed: technically
   reasonable after independent review and explicit authorization. A commit does not
   clear deployment interlocks. **Recommendation now: HOLD**, since the current
   candidate has not completed independent review and remains dependency-marked.
   It need not be merged into one inseparable commit with the prerequisites.
2. Deploy S2A.3 plus the current partial S2D.1 while admin/job remain blocked: **NO**.
   Admin single-record cancellation/archive/delete passes None and receives false,
   so legitimate events remain on Calendar. The child branch ignores false and
   removes google_event_id anyway, orphaning the live event/reference relationship.
   DB lifecycle changes can still report success; fail-closed provider access does
   not make this a safe functional release.
3. Hold production shipment until admin/job prerequisites are resolved and reviewed:
   **YES**. Tagged job paths may continue working, but missing request context can
   still be defaulted, untagged recovery is denied, and mismatched persisted child
   owners are not checked against the initiating scope. Do not describe every job
   flow as broken; the exact live prevalence is unknown because no production read
   was performed. The known admin breakage alone is enough to block partial release.

Even after implementation, account for old service envelopes, required explicit
record ownership and all known caller dependencies before considering deployment.
No RC or deployment is authorized or performed by this review. S2A.3 remains NOT
DEPLOYED; F02 UNRESOLVED; PTM-0 INCOMPLETE.

## Required future tests

All offline; dummy credentials and blocked real network/provider boundaries:

- Admin direct, swapped and healed lookups: primary/Alpha/future same-owner success;
  foreign, missing, malformed owner and absent authenticated tenant deny before
  status/audit/provider side effects. Ambiguous healing denied; body/query tenant
  fields cannot influence the target.
- Mixed-tenant bulk lists: only validated same-tenant entries proceed; no per-record
  target-tenant switching. Existing action/role gates preserved, including staff and
  platform_admin-only and mixed-role principals without a cross-tenant bypass.
- All three admin Calendar call sites: sync owner pinned; parent/child deletion owner
  explicit; foreign/missing child or wrong request relation skipped; completed jobs
  preserved; false/exception retains references and does not count success; 404/410
  cleanup stays compatible.
- Producer contracts: review approval, admin-created booking and public/portal
  lifecycle dispatch carry validated expected_company_id despite hostile body data.
  Static workflow input pass-through verified without Terraform execution.
- Job request validation: primary/Alpha/future equality, missing/malformed envelope
  and request owner, wrong keys/IDs, mismatches and input tenant override; no pet/job/
  Calendar side effects on denial. Missing owner never resolves to primary.
- New job creation, canonical recovery, linked no-op replay and partial retries:
  correct owner and relationship preserved; foreign/missing child cannot be used or
  relinked; deterministic IDs unchanged; failed provider operation retains references.
- Event hint mismatch cannot override validated persisted Calendar reference.
  Old-envelope rejection/reissue contract covered explicitly; do not assert legacy
  payloads remain compatible without a reviewed design.
- Re-run S2D.1 propagation, S2A.3 provider ownership, S1 isolation, admin lifecycle,
  review/assignment/cancellation, job/canonical occurrence and intake suites.
  Keep previously established baseline failures separately reported.

No test suite was run in this architecture-only task; prior S2D.1 results remain
historical evidence, not new validation of proposed code. Verification here consists
of source inventory, Git hygiene and preservation checks.

## Review output and ending hygiene

Only new file in this task:
`docs/reviews/ptm0-s2d1b-admin-job-ownership-architecture.md` (this record).

Existing S2D.1 runtime/tests/docs and the two S2A.2d records are preserved byte-for-byte
by SHA-256 comparison. Six tracked modifications remain unstaged; the four initial
untracked documents/tests remain, plus this new review document (five total).
HEAD/local origin/main unchanged at the starting SHA; index and stash empty.
No files staged; commits/pushes ZERO; remote Git operations ZERO.
Production/AWS/Google access ZERO; Terraform commands/operations ZERO; RCs ZERO;
deployments ZERO. Local infrastructure source was read only.
Stop after architecture review; prerequisite implementation is not authorized here.
