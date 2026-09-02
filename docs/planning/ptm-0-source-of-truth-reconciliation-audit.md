# PTM-0 Source-of-Truth Reconciliation Audit

Date: 2026-09-02

Scope: repository-only static audit; documentation changes only

Disposition: **PTM0_ARCHITECTURE_CONFLICT_FOUND**

Overall completion classification: **C — requires narrow implementation changes**

Audit complete for independent review; PTM-0 implementation/acceptance is **not complete**.

## 1. Checkpoint, method, and evidence limits

Starting branch `main`; HEAD and local `origin/main` both
`3d584851407d5341a4121a17ca61d27d173dc4ab`. Worktree and index were clean;
stash was empty. A read-only remote-ref check before closeout also confirmed
that exact SHA on remote main. No material checkpoint mismatch was found.

Continuity documents were consulted in the requested order, followed by the
approved PTM specification, mobile presentation specification, DOMAIN-1 ADR,
operational alignment, and relevant release records. Analysis used repository
file reads, `rg` discovery/searches, and Git source/history comparisons. It did
not import or execute application modules, run application tests, use a browser,
access AWS, inspect application sessions, or read Terraform state/plan files.
Test results below are **recorded historical evidence, not new executions**.

Source references and line numbers below refer to the starting main commit.
The current repository is not identical to deployed source:

| Evidence class | Reference and interpretation |
|---|---|
| Current source | `3d584851407d5341a4121a17ca61d27d173dc4ab`; includes locally complete, undeployed Preview V1 and other unrelated work |
| Recorded deployed backend | P1 plan-generation RC `ec618b5734d4b271e7dd4b4aa9eecf318411323c`, runtime/test commit `97cb6ebffe8b727e7a6833988107a40e65ba2105`; see P1 deployment-plan note, source checkpoint and applied-status addendum |
| Recorded production acceptance | P1 acceptance note and B1A real Web/API validation note: all 13 Lambdas on `K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=`, strict multi, API `prod -> atxpw3`, state 516; these were **not rechecked live** |
| Recorded deployed Web | PTM-3D.1 RC `3025f2f1e3991f990d0d4adde79b910e955fd6d1`, `assets/index-CdPio7XK.js`; current-state PTM-3D.1 closeout records authenticated Alpha acceptance |
| Recorded Mobile distribution | Current-state records iOS 1.0.0 (6) / Android versionCode 4 from `bf9f80d95c1846f197bab24d96463906bc26bfce`; main Mobile source is not proof of the installed binaries |

`git diff --exit-code ec618b5734d4b271e7dd4b4aa9eecf318411323c HEAD --`
the following seven files returned no differences: `common/auth.py`,
`common/entitlement.py`, `common/tenant_route.py`, `common/calendar_metadata.py`,
`handlers/admin_handler.py`, `handlers/platform_handler.py`, and
`handlers/google_auth_handler.py` (all under `src/backend/`). Therefore the
specific findings in those files are also present in the recorded deployed
source, not merely newer main work. This is source correspondence, not evidence
of exploitation or current production data contents.

The billing diff is catalog extraction only: main imports tier/status constants
from `tenant_catalog.py`; the deployed RC keeps equivalent constants inline.
The entitlement class/build/load logic discussed below is unchanged. The auth
Terraform diff adds Custom Email Sender wiring, not app-client policy changes.
Do not deploy main wholesale to address any finding.

## 2. Canonical approved PTM-0 definition

The unchanged [approved specification](platform-tenant-management-control-plane.md)
at lines 348–350 labels PTM-0 **“Complete in Specification”** and states:

> Establish formal control-plane architecture, document 5-way tenant authorization model, Cognito identity vs. role group rules, define lifecycle states, and reconcile existing platform handlers.

Its explicit deliverable is that specification itself. It does **not** supply a
separate PTM-0 executable acceptance suite, a production rollout checklist, or a
requirement to implement every later PTM phase as PTM-0. “Specification approved”
is not “all runtime invariants implemented and production-validated.”

The inherited contracts are specification §§2–5 and 8: canonical company
identity and registry; route/claim/registry agreement; functional Cognito groups;
orthogonal lifecycle/subscription/entitlement models; shared app clients;
control-plane separation; fail-closed tenant access; governed creation and
disable/restore. Section 10 preserves the customer-tenant gates. PTM-1/2/4/5
visibility, PTM-8 creation, PTM-9 lifecycle mutations, DOMAIN-2/6 persisted
routing, and enterprise exceptions retain their own scope and approvals.

## 3. Requirement-by-requirement reconciliation

`IMPLEMENTED_AND_VALIDATED` means supported by specific recorded validation of
that bounded behavior, not a new or universal assurance. Where one requirement
mixes an implemented foundation and missing target behavior, its status remains
partial or conflicting rather than inheriting a blanket historical PASS.

| ID | Approved requirement / location | Status | Exact source and evidence; remaining boundary |
|---|---|---|---|
| R01 | Canonical tenant record and company identity; §§2.3, 4 | IMPLEMENTED_AND_VALIDATED | `platform_handler.py:11–34,39–43`; `auth.py:247–260`; 19D created `TENANT#test_tenant_alpha / METADATA`; B1A final inventory restored that baseline. This proves the key model, not universal access enforcement. |
| R02 | Claim, server route registry, active metadata agreement; §§3.2,4.1,8.2 | PARTIALLY_IMPLEMENTED | `tenant_route.py:38–75`, `admin_handler.py:423–444`, `web/src/utils/tenantContext.js:26–67`; DOMAIN-1/B1A validate Alpha. General host routing and persisted slug registry absent; claim-only endpoints do not universally apply the same gate. |
| R03 | Slug is context, not identity or authority; §§2.3,4.1 | PARTIALLY_IMPLEMENTED | `tenant_route.py:17–35` has only `test-tenant-alpha -> test_tenant_alpha`; no slug derivation or provisioning uniqueness contract. Spec's extra `tog-and-dogs` mapping is not implemented. |
| R04 | Cognito functional groups are business-role authority; §§4.1–4.2 | CONFLICTING_IMPLEMENTATION | `auth.py:29–74`, `web/src/api/auth.js:83–102`, `mobile/src/auth/cognito.ts:170–188`: legacy email-to-owner fallback; Mobile admin-to-owner alias; profile `role` edits do not change authorization groups (`admin_handler.py:1625–1695`). F04/F05. |
| R05 | Platform Admin authority requires platform_admin group; §§3.1,8.2 | IMPLEMENTED_AND_VALIDATED | `auth.py:71–74`; `platform_handler.py:296–320`; `web/src/App.jsx:26–67`; 17L/17N tests and 17P/17R production records. Email fallback does not grant platform_admin. |
| R06 | Platform role alone grants no tenant operation/impersonation; §§4.1,8.3 | CONFLICTING_IMPLEMENTATION | Normal staff operations exclude platform-only role; route bridge has no exception. But `entitlement.py:506–508` exempts any platform group, including mixed-role callers, from tenant status checks. The global no-bypass invariant is not met. F03; no claim of unrestricted impersonation. |
| R07 | Separate lifecycle_state, subscription_status, entitlement_state; §5 | SPEC_ONLY | No persisted/runtime `lifecycle_state`, `entitlement_state`, or `onboarding_state` contract found in searched runtime/tooling. `billing.py:64–158,210–227` computes access from subscription/override instead. New state storage/mutations remain separately scoped. |
| R08 | Missing/inactive/unresolvable tenant fails closed; §§4.1,8.2 | CONFLICTING_IMPLEMENTATION | Strict claim resolver and route bridge fail closed, but `entitlement.py:126–154,492–528`, `auth.py:352–398`, `google_auth_handler.py:89–101` and untagged filters disagree. F01–F03. |
| R09 | Disable/restore blocks tenant work and preserves records; §5, PTM-9 | PARTIALLY_IMPLEMENTED | `platform_handler.py:175–187`; 20C/20F recorded active -> disabled -> active and ordinary-owner denial. Not orthogonal lifecycle, not tested for all override/mixed-group/missing-record cases. |
| R10 | Shared standard clients; enterprise exceptions only; §4.3 | IMPLEMENTED_NOT_FULLY_VALIDATED | One tracked pool/client resource in `modules/auth/main.tf:1,62–121`; Web and Mobile configs name same client. Platform uses Web session. No per-tenant client creation found; no fresh live inventory or full cross-platform callback validation performed. |
| R11 | Governed creation, uniqueness, safe defaults, rollback; §7, PTM-8 | PARTIALLY_IMPLEMENTED | `scripts/provision_tenant.py:269–319,326–399`; Preview domain/adapter; 17W/19D and Preview V1 note. Serial repeat guard exists, but not atomic uniqueness or whole-operation idempotency; CLI active vs preview disabled defaults. F06. |
| R12 | Preview must remain no-write and creation separately gated; §7, PTM-6/8 | IMPLEMENTED_AND_VALIDATED | `platform_onboarding_handler.py:235–408`, `infra/prod/platform_preview_iam.tf:52–76`; Preview V1 records 91 backend/5 focused Web passes, no Apply path. **Local validation only, not deployed**. |
| R13 | Immutable complete platform audit; §8.1 | CONFLICTING_IMPLEMENTATION | `platform_handler.py:223–248` updates then separately writes audit without checking result/correlation ID; `common/db.py:10–16` can return false. CLI also separate writes. Historical success does not establish atomic/immutable logging. F07. |
| R14 | Neutral platform identity; tenant-aware shared presentation; §3.3 | PARTIALLY_IMPLEMENTED | `web/src/utils/tenantPresentation.js:14–83`; recorded PTM-3D.1 acceptance. Mobile AuthContext has no tenant bootstrap model; broad branding/PTM-3B/3E are not all proved by the Web result. |
| R15 | Nested tenant/control host hierarchy in §§3.1/3.2/6.2 | SUPERSEDED | Same spec PTM-10 lines 408–414 and mobile architecture ownership invariant select flat `platform.usmissionhero.com` / `<slug>.usmissionhero.com`. Older nested examples remain stale, not an approved deployment target. |
| R16 | Reconcile existing handlers and document enforceable acceptance; PTM-0 | PARTIALLY_IMPLEMENTED | This audit completes the static reconciliation; conflict review and proposed acceptance criteria below remain unapproved/unimplemented. No explicit approved executable PTM-0 criteria found. |
| R17 | Mandatory Tier-1 customer creation gate; §10 | IMPLEMENTED_AND_VALIDATED | Current backlog and continuity preserve PTM-0/1/2/4/5; recorded Alpha-only approvals/cleanup are bounded internal validation, not a new customer admission. Governance evidence only, not a programmatic CLI gate. |
| R18 | Enterprise per-tenant clients/white-label builds as a PTM-0 implementation obligation | NOT_APPLICABLE | §4.3 and PTM-12/13 explicitly defer exceptions. No enterprise build, new client, tenant switch, or impersonation implementation is required by this audit. |

## 4. Identity authority and entry-path map

| Layer/path | Authority today | Important constraint |
|---|---|---|
| Cognito/API Gateway | User Pool authorizer provides verified identity/group/custom-attribute claims to proxy Lambdas (`modules/api/main.tf:6–13` and protected methods) | Backend helpers consume authorizer context; they do not independently verify arbitrary direct-invocation claims. IAM/direct invocation is a separate trust boundary. |
| Authenticated tenant backend | `custom:company_id` from authorizer claims via `auth.py:247–285` | A nonempty claim selects company, not proof that metadata exists/is active. No runtime staff-record lookup in this resolver despite stale comments. |
| Canonical registry | `TENANT#<company_id> / METADATA`, with matching `company_id` | Route bridge checks record/claim/registry equality. `tenant_id` in public-domain config and prose denotes this same company identity, not a second identity database. |
| Operational records | `COMPANY#<company_id>` partitions for staff/clients; request/job/pet records carry company association; helper `validate_tenant_ownership` | Helpers enforce comparisons only where called. Untagged legacy ownership is default-company compatibility; broad queries currently disagree (F01). |
| Web route bootstrap | `/t/:tenantSlug/admin` -> `expectedTenantSlug` query on `/admin/tenant-info` -> server registry check -> session claim equality | `App.jsx:70–72`, `api/client.js:174–179`, `tenantContext.js:26–67`, `AdminDashboard.jsx:1181–1225`. Query is an expected-context assertion, never tenant override. No universal per-request route slug enforcement is claimed. |
| Compatibility Web | `/admin`, `/client` use shared login and claim-based APIs | No generalized hostname-to-tenant lookup; route bootstrap is special to DOMAIN-1. Primary branding is not platform identity. |
| Public intake | Server-owned `PUBLIC_INTAKE_DOMAIN_MAP` keyed by API requestContext domain; optional claim must agree (`auth.py:300–450`; `infra/prod/main.tf:98`) | Does not trust browser Origin/Host/body/query as a tenant grant; current server mapping is not wildcard host onboarding. Active logic differs from route gate (F03). |
| Mobile | Shared Cognito login and API client; tenant claim travels in authenticated request | No explicit tenant context/branding bootstrap in `mobile/src/auth/AuthContext.tsx:5–109`; no route/host parser or tenant switch. Role cached locally is UI state, not server authority. |
| Platform catalog | `/platform/tenants` scans canonical TENANT metadata; detail target is explicit path company ID | Control-plane read model, not independent identity master; no caller-company fallback in core list/detail lookup. `common/tenant_catalog.py` is a **tier/status catalog**, not tenant directory. |
| Provisioning | Human supplies company ID; domain validates format; CLI or future gated handler would persist metadata | Neither company ID nor slug is derived from display name. No actual slug generation/storage today. |
| Internal workflow / providers | Jobs load request company (`job_handler.py:18–59`); signed Stripe events resolve metadata/company and check booking ownership (`stripe_webhook_handler.py:83–95,147–155,392`); OAuth callback uses saved state company (`google_auth_handler.py:273–276`) | Not browser tenant-selection mechanisms; internal IAM, provider verification, record ownership and legacy defaults require separate treatment. No provider calls performed. |

No new universal tenant identity service is needed. DDB metadata, Cognito
association, and route registry have different responsibilities; merging them
into a single mutable browser-selected authority would be a regression.

## 5. Role/group model and association drift

- Cognito pool groups are global **functional roles**, paired with one company
  claim per identity. They are not memberships in every tenant. `client` is the
  implemented customer role; a separate `customer` group is not recognized.
- The authoritative role input is the `cognito:groups` **token claim**, which is
  a snapshot of group membership. A generic `role` or `custom:role` claim is not
  a recognized backend authority. Effective role is computed, not persisted.
- Backend priority is owner > admin > staff > client > platform_admin > unknown.
  `is_platform_admin` tests group membership independently. Thus mixed
  platform+owner identities legitimately have two authorities, but tenant
  lifecycle enforcement must still apply in the tenant plane.
- Web's standard role helper lacks platform_admin; `PlatformAdminGuard` checks
  that group separately. Web/Mobile string-group parsing differs from backend
  comma splitting. Mobile maps admin to owner for navigation. These UI mappings
  do not themselves change API privileges.
- All three role helpers contain a legacy hard-coded email owner fallback.
  Values are deliberately not copied here. No recognized functional group plus
  an allowlisted email can still become owner; group-only authority is false.
- DDB staff `role`, `is_active`, `cognito_sub`, and profile membership are
  operational/link/display state. Staff profile edits persist `role` but the
  subsequent best-effort attribute sync handles name/phone, not group removal or
  demotion (`admin_handler.py:1625–1695`). Local profile inactivity is not a
  universal request-time login/role check.
- Onboarding/link paths use `ensure_cognito_tenant_attribute`
  (`auth.py:472–519`, `admin_handler.py:1269–1287`) to reject conflicting existing
  company before group/profile mutation. This is valuable but not a transaction
  across Cognito and DDB. Group-add failures may be warnings, leaving drift.
- Directory reads merge Cognito and DDB (`admin_handler.py:1874–1943`); substring
  `client` group enumeration is legacy compatibility, not evidence that tenant
  groups are required or currently exist. No live group enumeration was done.
- **custom:company_id cannot be proven always equal to persisted association.**
  Existing guard coverage is operation-specific; old tokens, manual privileged
  changes, partial multi-service writes, profile edits, and email fallback need
  explicit reconciliation policy. PTM-4 should expose disagreement, not silently
  “repair” it or choose the highest privilege.

## 6. Lifecycle and entitlement truth table

There is no canonical operational `lifecycle_state` field today. The de facto
disable/restore control is `subscription_status`, supplemented inconsistently by
`is_active` and overrides. This conflates administrative availability and billing
instead of implementing the approved three-dimensional model.

| Mechanism | Actual behavior | Consequence |
|---|---|---|
| DOMAIN-1 route gate | Requires metadata `is_active is True` AND status active/trialing; lookup/mismatch denies | Strong bounded Alpha gate; past_due/override eligibility elsewhere does not imply route admission |
| Public intake active helper | Denies missing/error and explicit blocked statuses; rejects false is_active only when status is not active (`auth.py:384–396`) | `is_active=False, subscription_status=active` is accepted here, unlike route gate |
| Shared tenant gate | `_get_entitlement_safely` returns active starter on absent metadata/load exception; bypass for platform group or protected identity | Not global fail-closed tenant existence/lifecycle enforcement |
| Entitlement builder | Uses subscription/limits/flags/override/status-change date; ignores metadata is_active (`billing.py:210–227`) | `is_active=False` alone does not block normal claim-only tenant routes |
| Billing access | active/trialing allowed; past_due grace 7 days, read-only window to 14; missing/malformed status-change date assumes grace; active override takes precedence (`billing.py:80–145`) | Administrative hold and billing override precedence are not independent; normal shared gate denies read-only-window access rather than distinguishing every method |
| Other billing loader | `get_tenant_entitlement` fails closed on missing/load error, with five-minute warm-process cache (`billing.py:169–207`) | Two incompatible loaders; platform invalidation only clears that process's cache, not all Lambda execution environments |
| Platform PATCH | Six statuses active/trialing/past_due/canceled/paused/disabled; records billing_status_changed_at; allowed fields exclude is_active/lifecycle/slug (`platform_handler.py:132,175–187`) | 20F proves ordinary disable/restore, not SUSPENDED/ARCHIVED transition semantics |
| Provisioned metadata | is_active True; starter limits. Preview default status disabled; CLI default active | Inconsistent initial-availability policy; neither writes ONBOARDING |

Approved future states remain PROSPECT (no record), ONBOARDING, ACTIVE,
SUSPENDED, ARCHIVED; entitlement allowed/blocked/overridden remains a proposed
separate model. Do not synthesize/migrate lifecycle values or change billing
policy during this audit. PTM-1/2 can report “not modeled” until a reviewed
mapping exists; they must not mislabel subscription `active` as proved lifecycle
ACTIVE. Cognito sign-in itself is not disabled by a DDB subscription PATCH.

## 7. App-client policy

One tracked Cognito User Pool and one tracked app client serve Web, its Platform
Admin UI, and Mobile; Web and Mobile source defaults use the same pool/client
IDs (`web/src/api/config.js:4–5`, `mobile/src/api/config.ts:4–5`). Web can override
these through build configuration, so source alone is not a live account-wide
client inventory. No per-tenant client resource or provisioning operation was
found. Functional groups other than platform_admin are not all declared in the
auth module; Terraform alone is not a full membership inventory.

`modules/auth/main.tf:47–56` declares mutable optional company_id, while
lines 85–120 allow the application to **read but not write** custom:company_id.
Privileged server assignment remains separate. Password/SRP and refresh flows
are shared; OAuth code/implicit and email/openid/profile are configured.
Callback URLs are localhost `/admin` and the compatibility host `/admin`; logout
URLs are their roots (lines 72–83). DOMAIN-1 preserves the in-page SDK login and
route; no per-tenant callback is necessary for that bounded path. No standard
Mobile Hosted-UI deep-link callback is declared; Mobile uses the SDK, not a
separate Hosted-UI tenant client. Flat-host callback/logout design is future
DOMAIN-4/PTM-10 work, not authorization to add clients now.

This matches the shared-client policy in principle. An enterprise exception
requires its own RFC/approval; there is no evidence requiring such an exception
for PTM-0.

## 8. Control-plane / tenant-plane boundaries

| Plane | Actual routes and handler | Boundary/qualification |
|---|---|---|
| Control | Web `/platform-admin`, `/platform-admin/tenants/:companyId`, `/platform-admin/audit`; API GET `/platform/tenants`, GET/PATCH `/platform/tenants/{company_id}`, GET `/platform/audit` | `platform_handler.py:296–320` checks platform group first; explicit target, no tenant fallback. `/platform-admin/metrics` is not an implemented route found in `App.jsx`. |
| Control, local only | `/platform-admin/onboarding`; POST `/platform/onboarding/validate` and `/preview` | Preview V1 has no creation path and dedicated read-only IAM; not deployed |
| Tenant | `/admin/*`, `/client/*`, requests/pets/devices/review/assignment/cancellation and internal job processing | Cognito role + company claim + operation ownership; individual caller chains matter. Broad shared IAM does not enforce tenant row isolation (`modules/iam/main.tf:20–46`). |
| Context bootstrap | `/admin/tenant-info?expectedTenantSlug=...` | Validates route registry before operational Web bootstrap. Without expected slug, compatibility behavior differs; metadata/status endpoint permits platform group but does not grant operational role. |
| Public/provider boundary | Public intake, saved OAuth callback state, verified provider webhooks, scheduled Calendar health | Not ordinary tenant or control UI operations; must not inherit caller fallback or be treated as safely read-only by method name |

The platform detail read aggregates staff/client/request data internally but
returns metadata and counts, not operational records. It has cross-plane
coupling: for primary-company details it calls `google_auth_handler.get_status`
with the **caller's** event (`platform_handler.py:70–83`), not explicit target
context. That helper may refresh/persist provider credentials. Historical 21H
reports platform IAM blocked token reading; this mitigates that historical
execution, not the architectural side-effect/target mismatch. No such GET was
invoked here. Aggregate staff/client queries also lack pagination, unlike the
tenant directory scan (`platform_handler.py:45–65`). PTM-1/2/5 counts cannot be
declared authoritative at all sizes without addressing that limitation.

## 9. Provisioning source of truth

`scripts/provision_tenant.py` is the existing human-operated write tool, not a
deployed customer creation API. CLI company ID is validated as lowercase
letters/digits/underscores, length 3–64; `tog_and_dogs` is reserved. Preview uses
the shared pure builder and checks company existence plus normalized display
name conflict through `tenant_read_adapter.py:31–85`. Those reads are not atomic
reservations. Slug is neither generated nor persisted nor reserved.

Metadata is the canonical DDB record; builder fields are at
`tenant_provisioning.py:265–280`. Starter defaults are 20 clients, one staff,
50 monthly bookings, 100 monthly notifications, with feature flags off in the
tier catalog. No provider credentials or explicit Calendar fields are created;
non-primary absence derives none/not_configured/capabilities false in
`calendar_metadata.py:89–103`. This is not configuration of a new provider.

The CLI prints Cognito command templates but does not execute them. Owner setup
and claim/group assignment are separate approved operations. `--apply` plus
`--confirm-apply` is a mechanical gate, not proof of a current Matthew approval;
the historical “APPROVED (Release 19D)” print is not reusable authorization.

Actual idempotency is limited: `get_item` then unconditional `put_item`
(`provision_tenant.py:297–313`), not a conditional write/transaction. Sequential
repeat skips existing metadata but **always** appends a fresh PROVISION_TENANT
audit built from proposed values; concurrent calls can overwrite despite the
guard, and audit/data failure can split. `--force-overwrite` exists and remains
separately gated. No transactional rollback occurs. Printed rollback guidance
uses subscription disable, preserves records, and gives separately authorized
Cognito-disable suggestions (`provision_tenant.py:182–220`).

Therefore 19D's one successful Alpha seed and Preview V1's local tests do not
prove production-grade atomic uniqueness, slug reservation, activation, or
idempotent governed customer creation. Those belong to the existing creation
workstream, not an automatic PTM-0 implementation expansion.

## 10. Security findings

Severity describes the architecture/customer-readiness consequence, not a
confirmed incident. **BLOCKER means block broad tenant-isolation/customer-ready
signoff**, not an instruction to roll back, disable a tenant, or alter production.

| ID / severity | Concrete finding and evidence | Exposure limits / review needed |
|---|---|---|
| F01 — BLOCKER | Untagged records are shared by list/export predicates: `admin_handler.py:569,2341,2397` allows matching company OR missing company, without subsequent ownership filtering before response (`595–600,2374–2381,2406–2408`). This conflicts with `auth.py:291–297`, which assigns legacy untagged ownership only to default company. | Any eligible non-primary owner/admin can match legacy untagged records if present; no live records were read and actual exposure is unknown. Export also requires export feature. `test_r11e_tenant_enforcement.py:287–313` prefilters its mock and has no untagged fixture, so PASS does not disprove this. Client request scan at `admin_handler.py:525–543` also relies on client_id alone; confirm tenant predicate independently. |
| F02 — BLOCKER | `google_auth_handler.py:89–101` catches failed strict tenant resolution and returns DEFAULT_COMPANY_ID. Shared gate swallows missing-claim PermissionError (`entitlement.py:511–516`); `/admin/auth/status` then calls this helper and can read primary metadata/provider state. `get_status:380–395` may refresh and save credentials; platform detail also calls it with caller context. | Not proof of leaked credential values. Scheduled-primary health is an explicit compatibility use, but authenticated missing-claim fallback is not. Existing disconnect legacy-secret guard and platform IAM restrictions narrow effects; neither makes the resolver fail closed. No provider/production request was made. |
| F03 — HIGH | Fail-open metadata loader, ignored is_active, privileged tenant-gate bypass, and inconsistent override/grace precedence (`entitlement.py:126–154,506–526`; `billing.py:80–145,210–227`; `auth.py:384–396`). | Route bridge is stronger; ordinary disabled-owner behavior is validated. Mixed owner+platform or protected identities bypass status, not every endpoint role check. Missing metadata/load-error paths and inactive+active combination need negative tests. |
| F04 — HIGH | Backend/Web/Mobile legacy email owner elevation conflicts with group-only authorization (`auth.py:65–67`; `auth.js:97–99`; `cognito.ts:183–185`). | Source proves an alternate authority, not current group/user inventory or exploitation. Preserve protected-account safety; do not change users or remove guards as part of this audit. |
| F05 — HIGH | DDB role/inactivity and Cognito group/claim state can diverge; best-effort onboarding/link sync and profile role edits are not membership reconciliation (`admin_handler.py:972–983,1269–1287,1625–1695`). | A DDB role demotion cannot be assumed to revoke group-token privileges. One company claim per user is the current model; multi-company identity switching is not implemented or authorized. No current mismatch asserted. |
| F06 — HIGH | CLI existence check is non-atomic; repeat audit may describe a creation that was skipped; defaults conflict (active CLI vs disabled preview). `provision_tenant.py:297–313,340`; `tenant_provisioning.py:174–194,265–280`. | Existing one-time controlled seed remains accepted. Concurrent provisioning/default activation correctness must precede any generalized customer create path; no provisioning performed. |
| F07 — MEDIUM | Metadata mutation and audit are separate; audit-write failure ignored, correlation_id missing, no immutable storage enforcement shown (`platform_handler.py:223–248`; `db.py:10–16`; IAM shared table writes). | 17R/20F prove successful audit instances, not all-or-nothing or immutability. Specification “every operation” also conflicts with deliberate zero-write preview; clarify whether it means mutating operations. |
| F08 — MEDIUM | General slug uniqueness/lifecycle/readiness/owner counts absent; detail counts unpaginated; platform detail provider status uses caller context. `tenant_route.py:21–23`; `platform_handler.py:45–83`; Preview adapter. | No slug collision currently demonstrated: single explicit Alpha mapping is safe but not scalable provisioning. Directory visibility and provider-read-model work remain distinct scopes. |
| F09 — LOW | Stale hierarchy/status/route claims, role parser differences, Mobile admin alias and cached UI role, and primary export filename fallback (`AdminDashboard.jsx:2339`) can mislead operators. | Presentation naming is not tenant authorization. Correct documentation and review UI parity separately; no Mobile build change here. |

Additional compatibility inventory: notifications default absent record company
to primary (`common/notifications/service.py:35,50,86–91,324`); cancellation uses
record company or primary (`cancellation_handler.py:213`); Stripe booking
ownership fallback is constrained by subsequent company comparison
(`stripe_webhook_handler.py:147–155`); Calendar metadata/secret helpers preserve
primary-specific defaults. These are live callable compatibility branches, not
dead code. Missing company on trusted async inputs must be covered by the
follow-up boundary review; do not silently generalize them to new tenants.

Test-only Alpha fixtures and single-mode fallback tests are not production
configuration. Core auth single-mode fallback remains callable compatibility,
but recorded production sets multi. Unknown/misspelled modes take the non-multi
fallback in core auth, unlike the route gate's deny; validate allowed modes in a
future hardening slice. No dead-code determination is asserted merely because a
branch was not exercised by historical validation.

## 11. Spec drift and chronological reconciliation

Preserve the approved document and append a **reviewed implementation-status /
supersession addendum**, rather than rewriting historical approval or silently
implementing a new architecture. This audit is the proposed evidence for that
addendum; it does not amend approved requirements itself.

| Material drift | Reconciliation recommendation |
|---|---|
| §§3 diagram,3.1/3.2,6.2 nested `*.toganddogs.usmissionhero.com`; older DOMAIN-1 ADR and workflow-alignment host rationale | Mark superseded by PTM-10 lines 408–414 and mobile spec flat-host ownership invariant. Compatibility path still deployed; no new DNS approved. |
| §2 “existing deployed foundation” includes Preview V1 | Split deployed platform foundation from locally complete **NOT DEPLOYED** onboarding preview, per Preview V1 note and P1 package exclusions. |
| §2.3 claims two slug mappings | Record exact one-entry Alpha registry; do not invent primary route mapping or treat company ID as slug. |
| §§5/6 present lifecycle/entitlement/onboarding fields as target model | Label SPEC_ONLY/absent today; record existing subscription disable semantics separately. |
| §7 preview diagram claims slug uniqueness | Actual checks are company ID and display name; slug reservation is future DOMAIN-6/PTM-8 contract. |
| §8.1 “every operation” must write immutable audit | Clarify reads/preview vs mutations and atomic/correlation requirements; do not introduce writes to read-only paths. |
| §11 state 513 and old Web artifact, PTM-3D local-only, B1A not started | Preserve dated milestones; point latest status to P1/state516, PTM-3D.1 deployment, separate B1A backend/read-only/cleanup and representative-write PASS; **full E2E not claimed**. |
| §3.3/PTM-3D broad branding coverage, PTM-3B/3C/3E target matrix | Later Web presentation acceptance proves bounded title/neutrality/Alpha isolation, not all dynamic logos/themes/email branding or Mobile cache/suspension scenarios. |
| §9 title says 13 phases through PTM-12; detail heading says 7 sections but lists 8 | Editorial addendum should acknowledge PTM-13 and Section H without changing scope. |
| Current-state claimed header/query/subdomain/path tenant engine and `/platform-admin/metrics` | Narrow to actual claim resolver, expected-slug bridge, server public-domain map and implemented platform routes. Neither arbitrary headers nor metrics route is implemented authority. |
| Historical claims “all endpoints secured”, “disable prevents login”, “idempotent provisioning” | Retain releases as evidence of their executed cases; qualify global wording with F01–F08. DDB disable is not Cognito account disable; tests are not universal proofs. |

Still accurate: canonical company identity, functional roles/shared standard
clients, no route-only authority, no platform identity equal to Togs & Dogs,
approval-gated creation, no implicit impersonation, and Tier-1/2/3 sequencing.
Later DOMAIN-1, PTM-3D.1, P1 and B1A work implement parts without completing the
generalized control-plane model.

## 12. Proposed acceptance criteria and smallest next slices

These criteria are proposals for Matthew/AG/Kiro review, **not new authority**:

1. Accept the source-of-truth/status matrix and historical deployment boundaries;
   approve an implementation-status addendum and authoritative flat-host wording.
2. Prove each tenant operation either enforces the identity/role/metadata/record
   contract or has a documented separately trusted public/provider/internal
   contract. Missing/unknown company must not select primary tenant.
3. Deny non-primary access to untagged legacy records; explicitly approve whether
   primary-only legacy compatibility remains. Do not backfill/delete data here.
4. Deny missing/error/inactive metadata and disabled lifecycle independently of
   platform membership or protected identity. Explicitly decide billing grace,
   overrides, public intake, scheduler exceptions, and legacy is_active absence
   before changing their semantics; retain Decimal-safe logging.
5. Set group authority/demotion/session-freshness policy; distinguish profile
   state from access authority, with no email privilege elevation or implicit
   cross-tenant membership. Preserve protected-account mutation safeguards.
6. Document existing vs future lifecycle fields honestly, and require separate
   migration/transition approval for persisted lifecycle/PTM-9. Complete PTM-1/2/
   4/5 visibility under their own reviews before customer creation.
7. Demonstrate no cross-plane provider side effects in a read-only control-plane
   model, and define complete mutation audit behavior before new mutations.
8. Use isolated offline tests with all external clients mocked; include denied
   paths with assertions of **zero downstream writes/provider calls**, and
   targeted regressions for current valid tenants. Separately approve any RC,
   deployment, read-only production checks, or production write validation.

**Recommended smallest implementation slice: PTM0-S1 — legacy-record read
isolation.** It directly addresses F01 in the existing admin handler; it does not
introduce a new registry, tenant, lifecycle field, app client, or provider action.
No implementation begins before independent review and explicit approval.

| Slice | Exact problem / likely files | Production impact / migration | Tests / deployment / gates |
|---|---|---|---|
| S1 — legacy-record read isolation (first) | Constrain untagged records in export, ALL/status request lists; add company filter to client request list. Likely `src/backend/handlers/admin_handler.py`, `tests/backend/test_r11e_tenant_enforcement.py`, `tests/backend/test_r19k_tenant_isolation.py`; if useful, a dedicated new boundary-test file | Narrows read visibility; proposed compatibility permits untagged legacy records only for primary company, matching existing ownership helper. No data migration needed for that option. Blanket removal/backfill is a separate decision. Export's existing audit side effect must not be used for live read-only testing. | Assert actual predicate semantics plus returned records for primary, Alpha, third tenant, missing/empty/mismatched company, mixed client IDs, both list branches, pagination. Existing mocks must not prefilter away the defect. Backend RC/deploy required later; approve compatibility decision, local implementation, review, release separately. |
| S2 — Google resolver/control-read boundary | Reject authenticated missing-claim fallback; separate scheduled primary compatibility and explicit platform target/status read. Likely `google_auth_handler.py`, `platform_handler.py`, relevant common Calendar helper, `test_google_auth_rbac.py`, `test_r21g_google_token_isolation.py`, `test_r6g_calendar_health.py` | May stop previously accepted malformed sessions; no credential migration intended. Do not alter scheduled primary behavior or authorize provider writes implicitly. | Mock all provider/secret calls; assert absent/wrong claim makes zero reads/writes; explicit target != caller; control GET no refresh/persist. Backend RC/deploy later; integration policy/approval distinct from S1. |
| S3 — tenant availability gate reconciliation | Fail-open loader, is_active disagreement and mixed-role/protected bypass. Likely `common/entitlement.py`, `common/billing.py`, `common/auth.py`, `common/tenant_route.py`, `test_r20e_disabled_tenant_enforcement.py`, `test_r17b_entitlement_enforcement.py`, `test_tenant_route_context.py`, `test_public_intake_tenant_routing.py` | May deny access previously allowed during metadata failure/override. Needs reviewed truth table and legacy-field policy; not automatic persisted lifecycle migration. | Missing/error/inactive/disabled/unknown statuses, override/grace timing, platform-only and mixed roles, protected identity, no downstream work, Decimal limits. Backend release later; explicit business/security approval before semantics change. |
| S4 — role authority reconciliation | Remove or explicitly resolve legacy email authority; distinguish UI admin alias; define DDB role editing vs Cognito demotion. Likely `common/auth.py`, `admin_handler.py`, Web auth helper/tests; Mobile helper/tests only in separately approved Mobile sub-slice | Existing allowlisted identities may depend on fallback. **No automatic user/group migration**; require a separately approved safe inventory/membership/session-transition plan. | Group/no-group/unknown/string/list/mixed-role cases, stale tokens/profile demotion, protected-user safeguards; backend/Web deployment and any Mobile build separately approved, never bundled into S1. |
| S5 — specification status and read models (PTM-1/2/4/5 coordination) | Add reviewed status addendum; define absent lifecycle/slug fields, accurate paginated counts, membership/claim mismatch visibility. Likely PTM/mobile/DOMAIN docs, `platform_handler.py`, `PlatformAdmin.jsx`, `PlatformTenantDetail.jsx`, `test_r17l_platform_admin.py` | Docs-only first; read-model enhancements need backend/Web deploy, possibly separately reviewed read-only Cognito IAM. No silent data repair or lifecycle storage migration. | Missing metadata/fields, multi-page counts, sanitized membership conflict view, no operational records/secrets, zero provider/write calls. Approve field schema and display semantics before code. |
| S6 — governed create/audit correctness (existing PTM-8/9 work, not automatic PTM-0) | Atomic company/slug uniqueness, coherent initial state, replay semantics, audit durability/correlation. Likely `scripts/provision_tenant.py`, `common/tenant_provisioning.py`, `common/tenant_read_adapter.py`, `platform_handler.py`, provisioning/platform tests; IAM only if approved transaction design requires it | Future write paths; persisted slug/lifecycle additions may need explicit migration. No existing tenant change authorized; preview must stay no-write. | Concurrency, partial failure, duplicate/replay, audit failure, approval binding, default state, rollback. Tool update and eventual backend/IAM release separately gated; **per-tenant production creation always needs new approval plus Tier-1**. |

**C, not A/B:** runtime conflicts survive the later releases and cannot be fixed
by wording alone. **Not D:** company identity, shared clients, server route
agreement, and platform-role foundations already exist; bounded corrections and
explicit future read-model/lifecycle contracts are preferable to a replacement
architecture. This recommendation does not collapse PTM-1 through PTM-13 into
PTM-0 or declare the whole roadmap a prerequisite to fixing S1.

Tier 1 remains PTM-0, PTM-1, PTM-2, PTM-4, PTM-5 before any second real/customer
tenant creation/provisioning/staging record. Alpha remains the existing internal
validation tenant and is not retroactively blocked; this task grants **no new
Alpha workflow/write authorization**. P1 and narrow B1A PASS remain accepted;
no rollback, repeat probe, B1A workflow, Ryan testing change, or deployment follows
from this audit.

## 13. Evidence register and independent review handoff

Release-note references below are under `docs/release-notes/`:

- Strict multi: `release-18t-strict-mode-enablement-apply-and-smoke-validation.md`
  §§2–4 and `release-18u-strict-mode-post-enable-monitoring-checkpoint.md` §§2–3.
  Zero fallback telemetry in that window does not cover helpers that catch
  resolution errors and return their own fallback.
- Platform: `release-17l-platform-admin-backend-apis-closeout.md` §§1–2;
  `release-17n-platform-admin-access-bootstrap-and-authorized-api-smoke.md`
  §§3–8 (authorized live smoke deferred there); `release-17p-platform-management-ui-mvp-closeout.md`
  §§2–4,8; `release-17r-safe-tenant-metadata-edit-smoke-and-audit-validation.md` §2.
- Provisioning: `release-17w-tenant-provisioning-script-implementation.md` §§3–6;
  `release-19d-controlled-second-tenant-metadata-creation.md` §§2–4;
  `release-platform-admin-tenant-onboarding-preview-v1.md`, no-write/not-deployed
  status and test matrix.
- Isolation/lifecycle/providers: `release-19m-production-deployment-and-tenant-isolation-revalidation.md`,
  `release-20c-controlled-tenant-disable-restore-validation.md`,
  `release-20f-disabled-tenant-backend-access-enforcement-production-validation.md`,
  `release-21h-google-per-tenant-token-isolation-production-validation.md`.
- DOMAIN-1: `domain-1-b1a-route-local-implementation.md`,
  `domain-1-b1a-route-backend-v2-rc.md`,
  `domain-1-b1a-route-test-harness-triage.md`,
  `domain-1-b1a-route-backend-v3-rc.md`,
  `domain-1-b1a-route-backend-v3-deployment.md`,
  `domain-1-b1a-route-web-v2-rc.md`,
  `domain-1-b1a-route-web-v2-deployment.md`. Recorded 14 route tests and 51
  tenant-isolation selection passes do not cover all F01–F05 counterexamples.
- Presentation: `docs/project-continuity/current-state.md`, PTM-3D/PTM-3D.1
  closeouts; `web/tests/TenantPresentation.test.jsx`,
  `web/tests/TenantScopedRouting.test.jsx`; mobile presentation architecture
  §11 is a **target** matrix, not executed cross-platform PTM-3E evidence.
- P1: `p1-decimal-entitlement-serialization-local-fix.md`,
  `p1-decimal-entitlement-serialization-backend-rc.md`,
  `p1-decimal-entitlement-serialization-backend-deployment-plan.md`,
  `p1-decimal-entitlement-serialization-production-acceptance.md`.
- B1A: `b1a-api-gateway-read-only-validation.md`,
  `b1a-gate-c-synthetic-cleanup.md`,
  `b1a-real-web-api-write-path-validation.md`. Representative persisted write and
  exact cleanup accepted; full real-route E2E and generalized tenant admission
  are not proved.

AG/Kiro should first reproduce source-only F01/F02 caller chains, verify the
seven-file deployed-source comparison, and assess F03/F04 mixed-role and
privilege exceptions. Then confirm matrix classifications, C vs D, the proposed
primary-only legacy policy, and the scope of S1. Do not invoke application routes
to review these findings. A future approved offline test slice should make the
negative cases executable before remediation; no tests were changed or run here.

Documentation integrity checks: targeted diff review, source-path existence,
and Markdown local-link existence passed (zero missing local links). The seven
deployed-source file comparison returned exit 0. Application tests were not run;
no new test pass count is claimed. Only this audit and current-state, handoff,
document-map, and SaaS-backlog Markdown files are in the change allowlist.
Final staged `git diff --check`, Git commit/push,
and hygiene evidence are returned with the task closeout; no generated package,
plan, compiled artifact, or application file belongs in this change.

Production mutations = **ZERO**. Production reads = **ZERO**. Terraform
operations = **ZERO**. Runtime/test/infra/Mobile changes = **ZERO**.
