# PTM0-S2 / F02 architecture and source-of-truth review

Date: 2026-09-03

Disposition: **PTM0_S2_ARCHITECTURE_REVIEW_MULTI_COMPONENT_CHANGE_REQUIRED**

Status: **LOCAL REVIEW RECORD / UNCOMMITTED / IMPLEMENTATION NOT STARTED**

## 1. Authority, checkpoint, and evidence limits

Starting branch: `main`. Starting HEAD and local `origin/main`:
`1cca9dd1cca9be3a39257f4d3c11ed7de4c53ac3`. Worktree clean, index empty,
stash empty. No fetch or production inspection was performed.

Reviewed the continuity README, current-state, guardrails, master handoff,
document map, maintenance checklist, SaaS readiness backlog, release index,
PTM-0 audit, independent review, and final S1 production closeout before
tracing the provider source. This task's explicit no-production-access rule
takes precedence over older generic continuity statements permitting reads.

F01 / PTM0-S1 remains **DEPLOYED / PRODUCTION ACCEPTANCE PASS / COMPLETE**.
F02 is **UNREMEDIATED / UNRESOLVED**. S2 architecture review has now occurred;
S2 implementation has not started. PTM-0 remains **INCOMPLETE**.

Evidence is static repository source, test definitions, Git object comparisons,
and dated release records. No application module was imported or invoked, no
tests were executed, and no current production configuration, customer record,
credential, secret payload, session, or provider account was read. Source-proven
reachable behavior is not a claim of observed exploitation or current live use.

### Main versus recorded deployed source

The recorded deployed S1 RC is `c31be0ab6f95ba77707f33980cadc0c998dda6e3`,
with accepted package hash `kmf9B9gD4pZ1wy1plBDVwSVtAIbNl7ybOdqxjVMemiI=`
and recorded state serial `519`. These facts were not rechecked in AWS.

Local Git comparison establishes that the following files are identical between
that RC and current main: `handlers/google_auth_handler.py`,
`handlers/platform_handler.py`, `handlers/admin_handler.py`,
`handlers/assignment_handler.py`, `handlers/cancellation_handler.py`,
`common/auth.py`, `common/entitlement.py`, `common/calendar_metadata.py`, and
`modules/iam/main.tf` (backend paths are relative to `src/backend/`).

`common/google_calendar.py`, `handlers/review_handler.py`,
`handlers/intake_handler.py`, and `handlers/job_handler.py` differ on main due to
other service/scheduling work. The recorded RC still contains the same relevant
secret resolver, optional-company token helpers, body-overwrite sync pattern in
review, and tenant-omitting delete calls. Main-only scheduling details are not
assumed deployed. Any eventual S2 RC must use the recorded deployed baseline
plus an independently reviewed overlay, not current main wholesale.

## 2. Exact original F02 and reconciliation

The [audit](../planning/ptm-0-source-of-truth-reconciliation-audit.md) F02 and
[independent review](ptm-0-source-of-truth-independent-review.md) sections 10–12
identify three linked conflicts:

1. `get_company_id_safe` catches authenticated tenant-resolution exceptions and
   returns `DEFAULT_COMPANY_ID`, undoing strict-multi fail-closed behavior.
2. `GET /admin/auth/status` can exchange a refresh token and persist replacement
   token state. It is not inherently read-only despite its name and HTTP method.
3. Platform tenant detail calls the tenant-plane status helper with the caller's
   event rather than an explicit target tenant, coupling a control-plane read
   to the wrong identity context and a write-capable provider operation.

The shared active-tenant gate returns `None` on missing-claim `PermissionError`,
expecting the handler to deny; the Google fallback instead continues. Platform
and protected-identity bypasses in that gate are additional entry conditions,
not proof of unrestricted cross-tenant permission.

Important refinement: the independent review correctly describes callback
binding to stored OAuth state rather than caller claims. That does **not** prove
all callback states safe: missing/null `company_id` in state becomes `None`,
which the shared secret resolver converts to primary. Expiration is stored but
not checked by the callback, and read-then-delete is not an atomic one-use claim.

## 3. Identity and provider ownership today

### Tenant identity

- `common/auth.py:247–285`: reads API Gateway authorizer claims and trims string
  `custom:company_id`. In `multi`, absent/empty values raise `PermissionError`.
  A truthy non-string is not rejected by this helper; no tenant-metadata identity
  validation happens here. Single-mode fallback exists but is not authorized
  to be enabled. No browser host/body/query is legitimate tenant authority.
- `common/entitlement.py:492–528`: checks availability but delegates a missing
  claim back to the handler; platform/root exceptions remain separate F03 work.
- `google_auth_handler.py:89–101`: malformed event, recognized scheduler event,
  or any caught resolution exception can select the primary company.
- Public OAuth callback obtains identity from `OAUTHSTATE` rather than an API
  claim. Scheduled health deliberately has no end-user tenant claim.
- Calendar sync obtains `company_id` from its input record, not a verified
  request context. Delete/token helpers accept omitted company arguments.

### Provider identity, reference resolution, and compatibility

`common/google_calendar.py:24–67` selects a token secret as follows:

1. `company_id is None` becomes `DEFAULT_COMPANY_ID`.
2. Read `TENANT#<company_id> / METADATA`.
3. Any truthy `calendar_secret_ref` wins, without checking its type, allowed
   namespace, tenant ownership, metadata `company_id`, provider, or enablement.
4. Otherwise primary receives `GOOGLE_USER_TOKENS_NAME`, or a hardcoded legacy
   primary secret name when that environment variable is absent/falsey.
5. Otherwise `calendar_provider == google` **OR** `calendar_enabled is True`
   yields `<environment-derived-prefix>/calendar/<company_id>/tokens`.
6. Otherwise return no connection. There is no final default-secret fallback
   for an explicit valid non-primary company with no configured integration.

`common/db.py:18–24` converts a DynamoDB `ClientError` into missing data. Thus
primary metadata absence **or read failure** can reach the legacy fallback.
Non-primary absence ordinarily yields no connection. Empty/falsey explicit
secret references are treated as absent; truthy malformed references reach the
Secrets Manager boundary. They are not established safe by SDK rejection.

Tokens are JSON in Secrets Manager, not DynamoDB provider rows. The reader and
writer do not verify an ownership field in token JSON or a Secrets Manager tag.
Ownership is effectively inferred from the selected secret reference. A
tenant-scoped metadata key alone cannot prove that its reference belongs to it.
Repeated resolution during read/refresh/save also does not freeze a single
validated binding for the whole operation.

`GOOGLE_CLIENT_CREDS_NAME` points to the shared Google OAuth application
configuration. Sharing that app registration is intentional; it does not grant
ownership of another tenant's user tokens or Calendar connection.

`common/calendar_metadata.py:5–104` is a separate presentation derivation:
it favors a truthy metadata `company_id` over the supplied target; explicit
provider fields are copied through; otherwise primary is shown as Google,
enabled, and connected by default, while other tenants get none/not_configured.
It includes `calendar_secret_ref` in the returned config. This is a reference,
not raw token data, but it is not appropriate proof of ownership or connectivity.
Provider labels/capabilities for Microsoft, CalDAV, and ICS are metadata only;
the mutation adapter inspected here still calls Google and hardcodes
`calendars/primary` (the connected Google account's primary calendar, not the
platform's primary business tenant).

### Can another tenant inherit a connection?

| Case | Current source behavior | Evidence limit |
| --- | --- | --- |
| Primary with absent provider fields/reference | Deliberate legacy token-secret and display fallback | Supported by 21G/21H history; current exact binding not freshly read |
| Alpha or future tenant, valid explicit identity, no provider config | No token secret; none/not_configured presentation | Does not silently inherit legacy primary through this normal path |
| Caller without a valid tenant claim | Status/health fallback can select primary; owner/admin disconnect can do so too, subject to its legacy guard | A valid Cognito identity without tenant claim is distinct from an unauthenticated API request |
| Metadata whose reference points to another tenant or legacy secret | Reference accepted; read/write can follow it if IAM permits | No arbitrary-reference write route or current misconfiguration is claimed |
| Metadata `company_id` missing/null/empty/mismatched | Secret resolver ignores it; display helper may infer target or honor a conflicting truthy field | No exact-match ownership validation |
| OAuth state owner absent/null | Secret resolver receives None and selects primary | Public callback uses stored state; not caller tenant headers |
| Untagged/null-company sync input or omitted delete company | Optional-company helper selects primary | Missing and null collapse; explicit empty string follows a different, still unvalidated path |
| Valid non-primary request body overriding `company_id` for sync | Review/assignment merge body over validated record before provider use | Source-proven data-flow defect, not a live test or observed Google write |

The question of “untagged provider records” must therefore distinguish legacy
token JSON, tenant metadata, OAuth state, and operational records. There is no
single provider-record table whose missing tag is universally safe to inherit.

## 4. Source-of-truth matrix

Backend paths below are relative to `src/backend/`. Abbreviations: GA =
`handlers/google_auth_handler.py`; GC = `common/google_calendar.py`; CM =
`common/calendar_metadata.py`. Tests are under `tests/backend/`; named suites
were inspected, not run. “Change” means proposed scope, not implementation.

| Route / function | Handler/module | Tenant source | Provider ownership source | Legacy fallback | Platform-admin behavior | Read/write capability | Risk if fallback is wrong | Likely implementation | Current test coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GET `/admin/auth/google` / `initiate_auth` | GA:178–251 | Strict caller claim after owner/admin role check | GC metadata/reference resolver | Primary secret compatibility; no broad catch-to-primary here | Platform-only denied; mixed owner/admin role allowed under existing role rules | Reads metadata/client secret; **writes OAUTHSTATE** | Misbound reference/state prepares wrong-tenant token write | Validate context and owned binding before state write | `test_google_auth_rbac`; 21G configured/unconfigured cases |
| GET `/admin/auth/callback` / `handle_callback` | GA:253–332 | Stored state `company_id` | Re-resolved GC binding | Missing/null state owner becomes primary | Public route; no platform privilege is needed or granted | Reads/deletes state, exchanges code, **writes token secret** | Wrong-tenant token replacement, replay/expired state acceptance | Strict stored owner/binding, expiration and atomic one-use consume | 21G happy callback and absent-state case; adversarial owner/expiry gaps |
| GET `/admin/auth/status` / `get_status` | GA:335–404 | `get_company_id_safe` caller | GC selected secret, shared app config | Catch-to-primary; None-to-primary | No local role gate; platform-only can reach status; mixed/protected active-gate bypass | Metadata/secret reads; **Google refresh + secret save** when cache stale | Primary status disclosure/provider write after failed resolution | Strict context; separate cached status read from refresh writer | RBAC staff cached status; 9C explicitly expects refresh-on-expiry |
| Handler `/admin/auth/health`; scheduled `calendar_health_check` | GA:407–492 | Caller fallback or explicit scheduled primary | GC selected binding | Scheduled primary is intended; authenticated catch is not | No local role gate | **Refresh/save or revoke marker**, not read-only | Wrong-tenant provider/secret mutation | Separate trusted scheduled context from authenticated paths | 6G health success/revoked/error tests, mocks; no source/claim adversaries |
| DELETE `/admin/auth/google` / `disconnect_auth` | GA:143–175 | Owner/admin plus safe fallback | GC secret reference | Exact equality to env legacy reference returns success without clearing | Platform-only denied; mixed role retains tenant management authority | **Secret clear then revocation-marker write**; no Google revoke API | Clears wrong secret; aliases/env absence evade exact-string guard | Strict binding; canonical legacy guard; no false disconnected claim | 21G/RBAC legacy preservation and custom-tenant paths |
| `_get_stored_tokens`, `_save_tokens`, refresh/revoke/valid-token helpers | GC:69–221; GA:26–86 | Optional company parameter | GC resolver each time | Omitted company selects primary | No role logic; depends on caller context | Reads or **writes secrets/refreshes Google** | Cross-tenant read/merge/save or changed binding mid-operation | Resolve/validate once and pass an immutable owned binding | 6G token tests; 21G mocks; little invalid-binding coverage |
| GET `/admin/tenant-info` | `handlers/admin_handler.py:425–500`, CM | Claim or DOMAIN-1 expected-slug agreement | Tenant metadata plus GA status for primary | Primary metadata/display defaults | Platform role is admitted by this endpoint's role list; not universal impersonation | Nominal read can **refresh/save** via GA primary check | Tenant bootstrap gains provider side effects; reference disclosure | Use side-effect-free status/read model, preserve route agreement | 21D mocks out GA status, so does not prove no writes |
| GET `/platform/tenants/{company_id}` | `handlers/platform_handler.py:39–119,296–320`, CM | Explicit target for tenant record, but **caller** for GA | Target config mixed with caller-derived provider status | Primary target invokes GA fallback | Platform group required; target read must remain distinct from tenant authority | DDB reads; GA call is code-level write-capable, configuration-limited | Target/caller mismatch and cross-plane side effects | Explicit-target metadata-only provider summary; no GA tenant handler call | 17L group/detail tests; no caller-target/write isolation assertions |
| POST `/client/requests` / admin-created booking (`source=admin_created`) | `handlers/intake_handler.py::_handle_admin_created_booking`, GC | Caller-resolved tenant stamped into item | GC selected binding | Untagged generic GC input defaults primary | Ordinary tenant-role enforcement, not platform target mode | Booking writes and **Calendar create**, possible refresh | Missing/invalid binding can select wrong account | Preserve trusted stamp; validate before provider operation | Workflow mocks; add provider-binding assertions |
| POST `/admin/review` and POST `/admin/assign` | `handlers/review_handler.py:286–308`; `assignment_handler.py:155–206` | Stored-record ownership checked, then body merged over record | GC consumes merged `company_id` | Body null/omission patterns and primary default; body may name another tenant | No control-plane override is intended | Workflow writes/notifications and **Calendar create/update/delete** | Caller-controlled provider tenant despite valid original record | Trusted explicit company, never body override; validate linked records and deletes | Tenant record isolation suites; no body-overwrite provider-boundary test found |
| Async `job_handler.handler` | `handlers/job_handler.py:18–73,197–281`, GC | Persisted parent company or caller resolver fallback | GC with child item company | Legacy parent absence falls back to resolver; claimless strict event can fail | System workflow, not Platform Admin context | Job/Calendar writes; main also has newer scheduling behavior | Lost parent/child tenant binding or wrong event inheritance | Characterize deployed path; preserve immutable parent/child binding | Workflow suites mock GC; require tenant propagation tests |
| PUT `/admin/cancel/decision`; admin action POST `/admin/requests`; review cancellation/archive/delete | `cancellation_handler.py:205–248`; `admin_handler.py:3257–3297`; `review_handler.py:340–367` | Authorized record; **company omitted at delete call** | GC optional-company deletion resolves primary | All these two-argument delete calls default primary even for tagged tenants | Tenant role checks do not repair omitted provider context | **Calendar delete**, secret refresh, workflow/notification/ledger writes | Wrong-account deletion attempt; false cleanup success and removal of event references | Pass trusted tenant for every parent/child event; no cross-company inheritance | 7E/18P tests explicitly assert two-argument deletion; need policy-correct replacement expectations |
| `notify_event` and notification service | `common/notifications/service.py`, config/resolver | Workflow record, separate legacy notification defaults | Postmark/SES environment config, not Google connection | Notification tenant defaults are separate | No provider-status control-plane path | Email/SNS/ledger/quota side effects | Reusing workflow as a “provider read” can send notifications | No notification redesign in S2; mock and assert boundaries | Existing notification suites; no Google resolver import found |

Route evidence: `modules/api/main.tf:350–446` declares Cognito authorization for
Google initiation/disconnect/status; callback authorization is `NONE` and relies
on state. No `/admin/auth/health` API resource/method was found; it exists in
handler dispatch and is not claimed externally routable. The daily EventBridge
rule/target and invocation permission are in `infra/prod/main.tf:445–465`.
Admin-created booking uses the authenticated client-request intake route
(`modules/api/main.tf:627–642`, `web/src/api/client.js:40`), not the admin
archive/action POST route. Public `POST /requests` also targets intake; provider
write authority cannot be inferred from that public route's existence.
No Terraform command was run to inspect these source files.

## 5. Platform and infrastructure constraints

- Platform detail properly starts with an explicit platform group and target
  company. It should preserve that control-plane read, not synthesize tenant
  claims or impersonate an owner for provider operations.
- The current/recorded platform Lambda environment lists data table, default
  company, and strict mode, but **not** `GOOGLE_CLIENT_CREDS_NAME`
  (`infra/prod/main.tf:407–423`). On that configuration GA `get_google_config`
  cannot load the client config and returns `CREDENTIALS_MISSING` before token
  refresh. This narrows actual runtime impact but is not an architectural guard.
- 21H described platform status `error` as an IAM restriction. Source instead
  shows platform using the shared Lambda execution role, whose Google policy
  permits Get/Put on the configured app/legacy token secrets
  (`modules/iam/main.tf:70–103`). The old observation does not establish that
  causal IAM explanation. No live IAM confirmation or expansion is requested.
- That policy does not grant arbitrary per-tenant secret namespace access. An
  accepted arbitrary reference is a missing software ownership check, not proof
  that all referenced secrets are accessible. Primary/global references remain
  especially important because they are already in the configured allowlist.
- No IAM expansion, new connection, per-tenant secret provisioning, new provider
  registration, or Google/OAuth configuration migration belongs in this review.

## 6. Persisted keys and indirect consumers

| Store / key | Meaning | Ownership caveat |
| --- | --- | --- |
| DynamoDB `TENANT#<company_id> / METADATA` | `company_id`, provider/enabled/status, account label, last-check time, reference and capabilities | Secret resolver does not compare row owner with requested company; metadata display is not a credential validator |
| DynamoDB `OAUTHSTATE#<random_state> / META` | Initiating company, admin ID, creation time, `expires_at` | Callback gets state then deletes it; does not test expiration, owner type, or atomically claim it |
| Secrets Manager configured legacy secret or `<prefix>/calendar/<company_id>/tokens` | Actual connection/token state | No runtime owner/tag validation; only reference selection; raw material was not read |
| Secrets Manager configured OAuth app secret | Shared OAuth client configuration | App registration is not per-tenant Calendar ownership |
| DynamoDB `REQ#<request_id> / CLIENT#<client_id>` and `JOB#<job_id> / REQ#<request_id>` | Tenant and event references used by workflow sync/deletion | Event ID is not ownership proof; parent/child link and resolved tenant must agree |

There is no provider ownership GSI found in the declared schema. `StatusIndex`,
`WorkerIndex`, and `ClientPetIndex` are operational indexes, not provider
authority; table TTL is `expires_at` (`modules/data/main.tf`). OAuth callback
must evaluate its own expiry rather than relying solely on whether a state
record remains present.

Notification service imports no Google resolver/Calendar adapter. It uses
Postmark/SES/log-only configuration. Intake/review/assignment/cancellation
workflows invoke notifications and Calendar as separate side effects; none is
safe to invoke merely to inspect provider state. Notification fallback changes
remain outside S2 unless separately scoped; no Stripe work is proposed.

## 7. Tests: evidence and gaps

Inspected test definitions only; **no new test pass count is claimed**.

- `test_r21g_google_token_isolation.py`: eight test functions cover legacy
  primary, explicit arbitrary reference acceptance, unconfigured Alpha, connect
  denial, callback happy path, legacy disconnect preservation, connect/delete
  disabled gate, and absent-state response sanitization. The callback fixture
  has no expiry and supplies caller claims even though the real route is public.
  Its broad metadata mocks do not prove requested key/returned owner agreement.
- `test_google_auth_rbac.py`: owner/admin mutation roles and staff cached
  status. Its “read-only status” fixture avoids refresh, so it is not proof
  that the endpoint cannot write.
- `test_r9c_google_calendar_banner.py:96–127` explicitly asserts refresh and
  save on expired status. This expectation must be reviewed when separating
  passive status from active refresh; simply patching mocks would conceal policy.
- `test_r21d_calendar_metadata_defaults.py`: primary/other/explicit metadata
  defaults and tenant-info shapes; GA status is mocked at the integration seam.
- `test_r6g_calendar_health.py`, `test_r6g_calendar_token.py`, and
  `test_r6g_calendar_retry.py`: refresh/revocation, error handling, retry and
  nonblocking behavior; not a complete company/binding authorization matrix.
- `test_r17l_platform_admin.py`: platform group and detail/read shape, not
  explicit target versus caller identity or provider-write absence.
- `test_r7e_cancellation.py` and `test_r18p_cancellation_cascade_fix.py` encode
  delete calls without company. Record-level isolation tests and S1's `118/118`
  do not establish provider-account isolation after this context is discarded.

Required new offline cases before implementation acceptance:

1. Missing/null/empty/whitespace/non-string/conflicting caller, metadata owner,
   provider fields, reference, callback owner, and operation-record company.
   Denied context must cause zero provider/secret operations and zero workflow
   writes; a valid configured-none tenant should remain neutral/unconfigured.
2. Explicit Alpha/future-tenant reference to primary or another tenant; name/ARN
   aliases, malformed references and path components; provider none/disabled
   with a stale truthy reference; metadata read failure must not grant fallback.
3. Callback without authorizer claims, mismatched/missing owner, expired state,
   already-consumed state, two consumers, binding changes, and failure ordering.
4. Status and both tenant-info/control-plane GETs with expired cache must not
   exchange tokens, save/revoke, notify, mutate Calendar or application data.
5. Platform target different from caller, platform-only and mixed roles;
   explicit-target summary must work without tenant impersonation or secret read.
6. Scheduled primary compatibility versus API-shaped event/action confusion.
7. Review/assignment body `company_id` override; parent/child mismatch; all delete
   callers pass validated company; primary legacy case remains explicitly bound.
8. Return/log sanitization including provider exception bodies and secret
   references. Cached status and failures must never emit token/code material.
9. Deployed-baseline overlay tests plus S1, P1 Decimal and DOMAIN-1 regressions;
   preserve Calendar timing/event idempotency without importing main-only work.

## 8. Proposed minimum S2 policy — not approved or implemented

The smallest defensible boundary is a **single explicit provider context** used
consistently across authenticated reads, callback, scheduler and workflow
writers. Fixing only the status fallback leaves known alternative wrong-tenant
paths intact. It can be implemented in bounded steps under one reviewed scope;
this document authorizes none of them.

1. **Exact tenant match.** Authenticated provider operations require a nonempty,
   well-formed canonical tenant ID from verified claims, matching existing
   tenant metadata. Provider references must belong to that exact ID, not just
   be nonempty strings. No query/body/host override. Reject malformed truthy
   types locally without redesigning the global auth/F03/F04 policies.
2. **Explicit contexts, not optional defaults.** Use separate entry adapters
   for authenticated tenant, state-bound callback, trusted scheduled primary,
   and validated workflow record. Resolve once and carry the owned binding
   through read/refresh/save/delete; never independently default mid-operation.
3. **Restricted legacy exception.** Preserve the already-recorded primary
   Google connection only for explicitly established `tog_and_dogs` context and
   its approved legacy binding. No Alpha/future tenant may inherit it. A missing
   claim, missing tenant, read failure, malformed field, NULL, or empty value
   must not activate compatibility. Any absent-only legacy provider-field
   exception must be explicitly encoded and tested; a present invalid owner
   cannot be treated as absent. Do not apply S1's missing-record-tag rule
   wholesale to provider credentials or public OAuth state.
4. **Reference policy.** Prefer tenant-canonical names; accept an existing
   noncanonical reference only through an explicitly reviewed tenant-to-binding
   mapping, not a self-asserted metadata string. Compare normalized permitted
   names/ARNs without retrieving token payloads for this review. Do not invent
   a current mapping, migrate secrets or expand IAM. Existing custom bindings,
   if required for release, need separately authorized private metadata review.
5. **Same ownership, distinct capability.** All reads and writes use the same
   ownership decision. Passive status, tenant-info and Platform detail must not
   refresh, save, revoke, exchange codes, or call Calendar. Platform summary
   should read explicit-target metadata only, omit internal references, and
   label unknown/stale evidence honestly rather than defaulting to connected.
   Tenant cached-status semantics and any unknown-state response need contract
   review: existing Web banners recognize specific legacy values. Do not
   silently turn unknown into disconnected or broaden to Mobile changes.
6. **OAuth state binding.** Initiation records only validated initiating tenant
   and owned provider binding. Callback requires that exact stored binding,
   well-formed owner, unexpired state, and an atomic one-time claim before
   exchange/save. No fallback on missing state fields; no need for a logged-in
   callback claim. Bind redirect choice to approved initiation context. Reject
   a changed provider binding instead of saving into a newly selected account.
7. **Refresh and disconnect.** Only a validated tenant write context or the
   established trusted scheduled primary context may refresh. Preserve the
   current no-clear rule for the legacy primary secret until a separate
   disconnect policy is approved; normalize identity so aliases cannot evade
   it, and do not report a protected no-op as actual disconnection. Do not
   broaden into Google token revocation or configuration migration.
8. **Calendar writers.** Resolve authenticated tenant and record ownership
   before workflow effects; freeze company outside body merges. Every parent
   and child event operation passes this company explicitly. Missing/invalid
   ownership denies provider mutation; ordinary configured-none skips stay
   distinct from authorization/configuration failure. Existing primary legacy
   operational records may be normalized only after explicit primary caller
   ownership verification; never through a generic omitted argument. Verify
   parent/child/event context and preserve unrelated scheduling semantics.
9. **Platform separation.** Platform Admin may read safe target metadata under
   platform authorization; that role confers no tenant-plane token/Calendar
   capability. Mixed roles use only their explicit ordinary tenant authority
   for tenant operations, not a target from the control-plane URL. Do not fix
   the platform path by adding credentials/IAM to make the old call work.
10. **No automatic expansion.** No new tenants, provider accounts, credentials,
    lifecycle storage, notification policy, Stripe behavior, Ryan testing,
    Mobile builds, F03/F04 global auth changes, or infrastructure changes.

### Likely implementation file boundary

Core changes likely span `handlers/google_auth_handler.py`,
`common/google_calendar.py`, `common/calendar_metadata.py`,
`handlers/platform_handler.py`, `handlers/admin_handler.py`,
`handlers/assignment_handler.py`, `handlers/review_handler.py`, and
`handlers/cancellation_handler.py`, plus focused tests. Intake/job propagation
must be characterized and changed only if required by the explicit-context
contract. `common/auth.py`, `common/entitlement.py`, `common/db.py`, Web status
consumers and infrastructure definitions are dependencies to review, not a
blanket authorization to modify them.

Functional Lambda consumers are the existing:

- `togs-and-dogs-prod-google-auth`
- `togs-and-dogs-prod-platform`
- `togs-and-dogs-prod-admin`
- `togs-and-dogs-prod-assign`
- `togs-and-dogs-prod-review`
- `togs-and-dogs-prod-cancellation`
- `togs-and-dogs-prod-intake`
- `togs-and-dogs-prod-job`

These are eight functional consumers, distinct from the 13-function
shared-package deployment architecture. No release, package, plan or deployment
is being requested here.

Classification is **MULTI_COMPONENT_CHANGE_REQUIRED** because provider ownership
and write-context loss span multiple callers and shared helpers. This is not a
replacement-platform architecture recommendation, and not a finding that S1
regressed. A narrower status-only patch could be a separately approved first
sub-slice, but must not be labeled complete F02 provider isolation.

## 9. Production dependency and stopping boundary

21G explicitly preserved primary legacy storage to avoid migration/downtime.
21H records primary connected, Alpha unconfigured, and platform error status.
Current source still schedules primary health daily; dashboard status refresh
is an intentional historical behavior demonstrated by 9C test assertions.
Thus removing all primary compatibility or treating current GETs as harmless
reads would be unsafe. The authenticated missing-claim fallback itself has no
documented legitimate business requirement.

The presence of users currently relying on missing claims, current custom
secret mappings, secret ownership tags, actual refresh frequency, or historical
wrong-account Calendar operations cannot be established from the repository.
No production read is necessary for this architecture disposition. If a later
release needs compatibility verification, request a separately approved,
sanitized check of tenant/provider binding metadata and effective IAM/environment
reference presence (not secret values), plus aggregate missing-claim telemetry.
Do not perform those reads under this review authorization.

## 10. Task closeout

- Changed file: this local review record only; intentionally uncommitted.
- No runtime, application, test, Terraform, continuity, or release-status edits.
- No code imports, test execution, package build, Terraform init/plan/apply,
  AWS/production read, Google/API/OAuth invocation, credential inspection,
  application data write, commit, push, deployment, tenant or Mobile action.
- S1 stays complete; F02 stays unresolved; S2 implementation remains not started.
- Next step: independent review of this policy and its expanded caller boundary,
  then an explicit Matthew implementation decision. Stop here.
