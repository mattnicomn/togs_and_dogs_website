# PTM-0 Source-of-Truth Reconciliation — Independent Architecture / Security Review

Date: 2026-09-02
Reviewer role: Independent architecture / security reviewer (Kiro)
Type: **REVIEW ONLY — no implementation, no production action, no tests run, no AWS/Terraform/Cognito/DynamoDB access**

Final disposition: **PTM0_INDEPENDENT_REVIEW_CHANGES_REQUIRED**

This review independently reproduces the source-only caller chains behind the audit
`docs/planning/ptm-0-source-of-truth-reconciliation-audit.md` and assesses each
material classification. It does not accept the audit's conclusions on trust; the
findings below reflect direct reads of the current `main` source.

---

## 1. Repository checkpoint

Verified at review start (read-only git):

- Branch: `main`
- HEAD: `afda4eb74f0f4f494ffbd27976943f0ca876a997`
- origin/main: `afda4eb74f0f4f494ffbd27976943f0ca876a997`
- Working tree: clean; index empty; stash empty

HEAD == origin/main. Hygiene matches the expected checkpoint. No material mismatch.

Note: the audit document itself was authored at the prior commit
`3d584851407d5341a4121a17ca61d27d173dc4ab`; the current authoritative checkpoint
`afda4eb...` is the commit that recorded the audit. Source line references below
were re-verified against current `main` and remain valid.

---

## 2. Agreement with overall "C" classification

**AGREE — C (narrow implementation changes required).**

The core architecture exists and is sound: canonical company identity, functional
Cognito groups, shared standard app clients, server-owned route/registry agreement,
and control-plane/tenant-plane separation. The defects are bounded correctness gaps
in specific helpers and list/read predicates, not a broken foundation. Therefore:

- Not A/B: the conflicts are live runtime behaviors (untagged-record predicates,
  provider fallback, availability bypass) that wording cannot fix.
- Not D: no replacement architecture is warranted; a new universal
  browser-selected tenant identity service would be a regression.

C is the correct disposition, and `PTM0_ARCHITECTURE_CONFLICT_FOUND` is accurate:
PTM-0 is **not** implementation-complete.

---

## 3. R04 assessment — Cognito functional groups as role authority

**AGREE: CONFLICTING_IMPLEMENTATION.** Independently confirmed:

- `src/backend/common/auth.py` `get_effective_role` returns `'owner'` from a
  hard-coded email allowlist when no functional group matches (email→owner fallback).
- `web/src/api/auth.js` contains the same email→owner fallback.
- `mobile/src/auth/cognito.ts` contains the same email→owner fallback **and** maps
  the `admin` group to `'owner'` (UI-level privilege elevation / alias).
- Staff profile `role` edits persist a DDB field and best-effort sync name/phone,
  but do not add/remove Cognito functional groups, so DDB role is not authorization.

Group-only authority is therefore false today. UI aliases do not change API
privileges (backend re-derives role from the token), but they do misrepresent
authority and must be reconciled. Protected-account values are deliberately not
reproduced in this document.

## 4. R06 assessment — platform role alone must grant no tenant operation

**AGREE: CONFLICTING_IMPLEMENTATION.** Confirmed:

- Normal staff/tenant operations do not include a platform-only role, and the
  DOMAIN-1 route bridge has no platform exception — good.
- However `common/entitlement.py` `require_active_tenant` bypasses the tenant-active
  check at the top for `is_platform_admin(event) or _is_bypass_active(event)`. A
  **mixed** owner+platform_admin identity therefore silently skips tenant lifecycle
  enforcement while acting in the tenant plane. The "platform role grants no tenant
  operation" invariant is not globally met. No unrestricted impersonation is claimed.

## 5. R08 assessment — missing/inactive/unresolvable tenant must fail closed

**AGREE: CONFLICTING_IMPLEMENTATION.** The strict claim resolver and route bridge
fail closed, but three independent paths disagree:

- `entitlement.py` `_get_entitlement_safely` fails **open** (returns an active
  starter tier) for both a missing tenant record and any load exception.
- `google_auth_handler.py` `get_company_id_safe` returns `DEFAULT_COMPANY_ID` on
  authenticated resolution failure (see F02).
- The admin list/export predicates admit untagged records for any caller (see F01).

So "missing/unresolvable ⇒ fail closed" is not universally true.

## 6. R13 assessment — immutable, complete platform audit

**AGREE: CONFLICTING_IMPLEMENTATION.** Confirmed in `platform_handler.py` PATCH:
`update_item(...)` runs first, then a separate `put_item(audit_record)` whose result
is not checked, with no correlation_id and no transactional guarantee. A successful
mutation followed by a failed audit write is silently accepted. `common/db.py`
write helpers can return `False`. Historical successful-audit evidence does not
establish all-or-nothing or immutability.

---

## 7. F01 exact assessment — legacy / untagged record visibility

**CONFIRMED BLOCKER. AGREE.**

The defect is a predicate mismatch between the read paths and the ownership helper:

- `common/auth.py` `validate_tenant_ownership` treats an untagged record
  (`company_id` absent/empty) as belonging to `DEFAULT_COMPANY_ID` **only**.
- The admin list/export read paths instead admit untagged records for **any** caller
  company using `company_id = :cid OR attribute_not_exists(company_id)` and do not
  re-filter by ownership before returning the response.

"Untagged" = a record with no `company_id` attribute (or empty). These are legacy
records created before tenant tagging; by the ownership helper they implicitly
belong to the primary compatibility tenant (`tog_and_dogs`).

Behavior is present in current `main`; the audit's seven-file deployed-source
`git diff` (exit 0) indicates `admin_handler.py` is byte-identical to the recorded
deployed backend, so the behavior is deployed-equivalent, not new work. No live
records were read; actual data exposure is unknown, but the code path is active.

Only the primary compatibility tenant should ever observe untagged legacy records.
`test_tenant_alpha` and all future tenants must fail closed on untagged records.
Platform Admin control-plane reads use their own explicit target company and do not
use tenant-plane fallback (confirmed: platform list/detail take an explicit path
company id, not a caller fallback). No browser-selected tenant gains legacy
compatibility.

## 8. F01 affected paths (exact)

- `src/backend/handlers/admin_handler.py` — `GET /admin/export-data`: scan
  `_Attr('company_id').eq(_company_id) | _Attr('company_id').not_exists()`
  (~line 569), gated by role owner/admin + `export_enabled` feature.
- `src/backend/handlers/admin_handler.py` — `GET /admin/requests` ALL/no-status
  branch: `(company_id = :cid OR attribute_not_exists(company_id))` + `REQ#` filter
  (~line 2341).
- `src/backend/handlers/admin_handler.py` — `GET /admin/requests` status-specific
  StatusIndex query: same `OR attribute_not_exists(company_id)` predicate (~line 2397).
- `src/backend/handlers/admin_handler.py` — `GET /client/requests` client branch:
  scans on `client_id` + `entity_type == REQUEST` **only**, with no tenant/company
  predicate at all (~line 525-543). This is a distinct gap: it relies on client_id
  uniqueness rather than an explicit tenant boundary and should be closed alongside F01.
- Ownership contract that these paths contradict: `common/auth.py`
  `validate_tenant_ownership` and `get_current_company_id` untagged→DEFAULT mapping.

Existing test `tests/backend/test_r11e_tenant_enforcement.py` pre-filters its mock
and has no untagged fixture, so its PASS does not disprove F01.

## 9. Recommended untagged-record policy

**Adopt "primary-only legacy compatibility." AGREE with the candidate principle.**

- Explicitly tagged records: must match the resolved caller tenant exactly; otherwise
  excluded (and cross-tenant direct access continues to raise).
- Untagged legacy records: visible **only** when the resolved caller tenant is the
  explicit primary compatibility tenant (`DEFAULT_COMPANY_ID` / `tog_and_dogs`).
- `test_tenant_alpha` and all future tenants: must never inherit untagged records
  (fail closed).
- Platform Admin: control-plane reads use explicit target-company rules, never
  tenant-plane fallback.
- No browser/route/query-selected tenant ever gains legacy compatibility.

This aligns the read predicates with the existing `validate_tenant_ownership`
semantics, so no data migration or backfill is required to make it correct. Blanket
removal/backfill of untagged records is a separate, larger decision and must not be
bundled into the read-isolation fix. Encode the compatibility rule **centrally**
(one predicate/helper) rather than per-handler to prevent recurrence (see §24).

---

## 10. F02 exact assessment — Google / provider tenant fallback

**CONFIRMED BLOCKER. AGREE, with a slightly stronger concrete impact than the audit
stated.**

- `google_auth_handler.py` `get_company_id_safe` wraps `get_current_company_id` in
  `try/except Exception: return DEFAULT_COMPANY_ID`. On an **authenticated** request
  with a missing/invalid `custom:company_id` claim, resolution failure resolves to
  the primary tenant instead of failing closed.
- `get_status` (`GET /admin/auth/status`) calls `get_company_id_safe(event)` and, on
  a successful refresh, calls `save_tokens(token_data, company_id)`. So a
  missing/invalid-claim caller resolved to primary can trigger a **refresh-and-save
  write** against the primary tenant's Google token secret. This is a write
  side-effect on a nominally read ("status") path — this is more than a read leak.
- `require_active_tenant` runs first in the handler but returns `None` (proceed) on
  `PermissionError`, so it does not block the fallback path; and it is bypassed
  entirely for platform/mixed-role callers.

The scheduled/EventBridge health-check branch legitimately uses primary and is an
explicit compatibility use; that should be preserved. The problem is specifically
the **authenticated** fallback and the caller-context provider read/write.

## 11. F02 affected Google / provider paths

- `src/backend/handlers/google_auth_handler.py` `get_company_id_safe` (authenticated
  `except`→DEFAULT branch, ~line 90-101).
- `get_status` → `save_tokens(...)` refresh/persist side-effect (~line 380-396).
- `common/entitlement.py` `require_active_tenant` missing-claim `PermissionError`
  swallow (returns None) + platform bypass.
- `src/backend/handlers/platform_handler.py` tenant detail: for the primary company
  it calls `google_auth_handler.get_status(event)` with the **caller's** event
  (~line 70-83), a control-plane read that can trigger the same tenant-plane provider
  refresh/persist. Cross-plane side-effect + target/context mismatch.
- OAuth callback uses **saved state** company (`google_auth_handler.py:273-276`),
  which is the correct pattern and behaves differently (does not use the caller
  fallback) — this is not part of the defect.

## 12. Recommended provider fail-closed policy

**AGREE with fail-closed direction.**

- Authenticated provider paths: missing / invalid / conflicting tenant association
  ⇒ **no provider operation** (deny), never resolve to `tog_and_dogs`.
- Preserve the explicit scheduled-health-check compatibility branch (source
  `aws.scheduler`/`aws.events`/`health_check`) as the only sanctioned primary default.
- Platform-plane provider status reads must pass an **explicit target company** and
  must be **side-effect-free** (no refresh/persist); separate the read model from the
  tenant-plane `get_status` that can write.
- Validate against existing per-tenant token-storage/resolution (21H) so tenant
  isolation of secret names is preserved.

---

## 13. Availability / platform_admin exception assessment (HIGH — F03)

**Current behavior violates the intended principle. AGREE it is a HIGH finding.**

Principle to hold: Platform Admin authority may permit **control-plane**
administration of an inactive tenant, but must not silently convert a normal
**tenant-plane** request into an allowed active-tenant request.

Today `require_active_tenant` grants a blanket tenant-plane bypass to any caller in
the platform group (including mixed owner+platform_admin) and to `_is_bypass_active`.
Combined with the fail-open `_get_entitlement_safely` and the `is_active`-ignoring
entitlement builder, a disabled/missing-metadata tenant can be treated as active in
tenant-plane operations. Recommendation: platform_admin should not bypass tenant
availability while performing a tenant-plane operation; control-plane administration
of inactive tenants belongs to explicit `/platform/*` routes. This needs a reviewed
truth table before changing semantics (grace/override/public-intake/scheduler
exceptions must be decided explicitly), so it is **not** an S1-blocking change.

## 14. Legacy email role elevation assessment (HIGH — F04)

**Recommendation: MIGRATE (do not blind-REMOVE, do not KEEP).**

- Historical purpose: bootstrap owner access before functional groups were fully
  provisioned, and preserve a protected operator's access.
- Security impact: establishes an authority channel outside Cognito group membership,
  contradicting group-only authorization; duplicated across backend + Web + Mobile.
- It still has a narrow legitimate purpose (protected operator lockout avoidance), so
  a blind removal risks locking out a legitimate operator.
- Correct target: represent the protected operator explicitly via a Cognito
  functional group (`owner`) and/or `platform_admin`, then remove the email
  allowlist from all three layers in a single reviewed slice.
- Required compatibility steps before removal: confirm (privately, no values in docs)
  that each allowlisted identity has the correct Cognito group membership; stage the
  group assignment; then remove the fallback with a session-freshness plan for stale
  tokens. No automatic user/group migration in this review.

Protected email values are intentionally not reproduced here.

## 15. Cognito / DDB membership drift assessment (HIGH — F05)

**AGREE it is a HIGH finding.** `custom:company_id`, Cognito group claim, DDB staff
`role`, DDB `is_active`, `cognito_sub`, and profile membership can diverge. Onboarding
uses `ensure_cognito_tenant_attribute` to reject conflicting company before mutation
(good) but group-add failures can be warnings, leaving drift; profile role edits do
not demote group membership; a stale token retains old privileges. This cannot be
assumed self-consistent.

## 16. Canonical role authority model (recommended)

- **Authentication identity:** Cognito user (`sub`) — canonical.
- **Authorization role:** Cognito functional **group token claim**
  (`cognito:groups`) — canonical and computed, never persisted DDB `role`.
- **Platform privilege:** membership in `platform_admin` group — canonical, tested
  independently.
- **DDB staff/client `role`:** operational/display/link state only — **not** authority.
- **Profile `is_active`:** operational state; must not be silently treated as an
  access gate without an explicit request-time check policy.

Drift disposition:
- Company-claim vs persisted-association mismatch → **fail closed** for tenant-plane
  operations; **surface to Platform Admin** (PTM-4), never silently "repair" or pick
  highest privilege.
- Group-add failure during onboarding → **fail closed** / surfaced, not warn-only.
- Name/phone attribute lag → **warn / async repair** acceptable.
- Stale-token role after demotion → requires a **session-freshness policy** decision.

## 17. Canonical tenant association model (recommended)

- **Tenant identity:** `TENANT#<company_id> / METADATA` in DynamoDB — canonical
  registry record.
- **Per-identity association:** `custom:company_id` claim — the runtime selector,
  which must **agree** with an existing active metadata record; a nonempty claim is
  not proof of existence/active status.
- **Route/slug:** context assertion only (`expectedTenantSlug` validated against the
  server registry) — never identity or authority.
- **Operational record ownership:** explicit `company_id` on records; untagged ⇒
  primary-only compatibility (§9).

Do not merge these into a single mutable browser-selected authority.

---

## 18. Provisioning atomicity assessment (F06 — HIGH)

**CONFIRMED.** `scripts/provision_tenant.py` does `get_item` then an unconditional
`put_item` guarded only by a prior read (not a conditional write / transaction);
concurrent callers can both pass the read guard. Replay **always** appends a fresh
`PROVISION_TENANT` audit built from proposed values even when the metadata write is
skipped, so audit can describe a creation that did not occur. CLI default `active`
vs Preview default `disabled` is an inconsistent initial-availability policy. Slug is
not generated/persisted/reserved.

**Scoping:** This belongs to the existing PTM-8/9 governed-create workstream
(proposed **S6**), **not** PTM0-S1. It should not expand S1; the one controlled Alpha
seed remains accepted. Atomic uniqueness/idempotency must precede any generalized
customer-create path, but that path is separately gated regardless.

## 19. Audit atomicity assessment (F07 — MEDIUM)

**CONFIRMED (MEDIUM).** Platform mutation and audit write are separate, unchecked,
without correlation id. PTM-0 does **not** require full atomic audit guarantees now
to unblock S1; a failed audit-after-mutation is currently possible and should be
corrected before **new** mutation surfaces are added, not as a precondition to the
read-isolation slice. DynamoDB `TransactWriteItems` is the right eventual tool.
**Does not block PTM0-S1.** Also clarify spec "every operation writes audit" to mean
mutating operations (Preview is deliberately zero-write).

## 20. Lifecycle model recommendation

**Option C (amend specification to distinguish target from implemented), combined
with B for now.**

There is no persisted `lifecycle_state` / `entitlement_state` / `onboarding_state`
today; de facto lifecycle is `subscription_status` + `is_active` + overrides. Do
**not** synthesize or migrate lifecycle values during PTM-0. Amend the spec with a
reviewed status addendum labeling §§5/6 fields SPEC_ONLY/absent, record the existing
subscription/availability semantics honestly, and defer persisted lifecycle +
transitions to PTM-9 under separate migration approval. The existing model is
sufficient for current tenants; PTM-1/2 must report "not modeled" rather than
mislabeling subscription `active` as lifecycle `ACTIVE`.

## 21. Control-plane vs tenant-plane assessment

Boundary intent validated: USMissionHero LLC = platform/operator; `tog_and_dogs` =
tenant; `test_tenant_alpha` = internal validation tenant; Platform Admin =
control-plane authority; tenant owner/admin/staff/client = tenant-plane authority.

The platform list/detail read model uses explicit target company ids and does not
apply caller-company fallback — good. The **leaks in the other direction** are the
concern: (a) `require_active_tenant` lets platform/mixed-role callers bypass
tenant-plane availability (control-plane privilege leaking into tenant-plane
enforcement), and (b) the platform detail handler invokes the tenant-plane
`get_status(event)` with caller context, coupling a control-plane read to a
tenant-plane provider side-effect. Both must be corrected so control-plane privilege
does not silently alter tenant-plane authorization or state.

---

## 22. Is PTM0-S1 the correct first slice?

**APPROVED_AS_FIRST_SLICE** (with the precise policy in §24 and the central-encoding
requirement). F01 is the highest-severity, most self-contained, migration-free
correctness fix; it touches one handler and existing tests, introduces no new
registry/tenant/lifecycle/app-client/provider surface, and has the smallest blast
radius. It is the right first slice.

## 23. Should F01 and F02 be combined or separated?

**SEPARATE.** F01 = tenant-plane list/read isolation in `admin_handler.py`; F02 =
provider resolver + control-plane provider read in `google_auth_handler.py` /
`platform_handler.py` / `entitlement.py`. Different files, different blast radius,
different integration/approval considerations (F02 touches provider behavior and a
write side-effect). Keep S1 = F01 and S2 = F02.

They do share a common root cause — "resolution/absence defaults to primary." A
single **canonical tenant-resolution + untagged-compatibility helper** should be the
long-term home for both rules, but the two fixes should still land as separate
reviewed slices to preserve minimal blast radius. Encode the untagged-compatibility
predicate centrally in S1 so S2 and later paths can reuse it.

## 24. Exact proposed S1 policy

1. **Tagged records:** included only if `company_id` == resolved caller company;
   all other tagged records excluded. Cross-tenant direct access continues to raise
   `PermissionError` via `validate_tenant_ownership`.
2. **Untagged records (`company_id` absent/empty):**
   - `tog_and_dogs` (primary/DEFAULT): visible (legacy compatibility retained).
   - `test_tenant_alpha`: **not** visible (fail closed).
   - future customer tenants: **not** visible (fail closed).
   - Platform Admin: not applicable on these tenant-plane routes; control-plane reads
     use explicit target-company rules.
3. **Record types / routes covered:** `GET /admin/export-data`; `GET /admin/requests`
   ALL/no-status branch; `GET /admin/requests` status-specific StatusIndex query;
   `GET /client/requests` (add an explicit tenant predicate — currently client_id
   only). Include any additional list/scan path in `admin_handler.py` that admits
   `attribute_not_exists(company_id)`.
4. **Central vs per-handler:** encode the tenant/untagged predicate in **one shared
   helper** (e.g. a `build_tenant_scope_filter(company_id)` used by all list/scan
   paths) rather than repeating the raw expression per handler.
5. **Must fail closed:** any non-primary tenant reading untagged records; any list
   path that would otherwise return records outside the resolved tenant.
6. **Legacy compatibility retained:** untagged records remain visible to the primary
   compatibility tenant only; no data migration/backfill/deletion is performed.
7. **Explicitly NOT changed by S1:** F02 provider fallback; F03 availability bypass;
   F04 email elevation; provisioning; audit atomicity; lifecycle fields; app clients;
   Decimal-safe entitlement logging; DOMAIN-1 route behavior; any deployment.

## 25. Exact S1 test matrix

All offline, external clients mocked; no route invocation; assert both the predicate
semantics and the returned record set.

| # | Scenario | Expected |
|---|---|---|
| 1 | Correctly tagged record, current tenant caller | included |
| 2 | Correctly tagged record, different tenant caller | excluded |
| 3 | Missing `company_id` attribute, primary (`tog_and_dogs`) caller | included (legacy compat) |
| 4 | Missing `company_id` attribute, `test_tenant_alpha` caller | excluded (fail closed) |
| 5 | Missing `company_id` attribute, hypothetical future tenant caller | excluded (fail closed) |
| 6 | Null/empty-string `company_id`, non-primary caller | excluded |
| 7 | Malformed `company_id` (wrong type/whitespace), non-primary caller | excluded / safe |
| 8 | Export path (`/admin/export-data`), non-primary caller, untagged present | excluded; export audit side-effect must not be exercised for live testing |
| 9 | ALL-status list branch, mixed tagged+untagged, non-primary caller | only own tagged returned |
| 10 | Status-specific StatusIndex query, mixed records, non-primary caller | only own tagged returned |
| 11 | `GET /client/requests`, client with records under a different tenant | excluded (new tenant predicate) |
| 12 | Pagination across multiple scan pages preserves the filter | filter applied on every page |
| 13 | Platform Admin control-plane read (where relevant) | uses explicit target, unaffected by S1 |
| 14 | Zero-side-effect rejection: denied/excluded path performs zero writes/provider calls | asserted |
| 15 | No primary data leakage: non-primary caller never receives `tog_and_dogs` tagged or untagged rows | asserted |
| 16 | Regression: existing valid primary-tenant reads unchanged | pass |

Existing tests to **extend** (add untagged fixtures, remove mock pre-filtering that
hides the defect): `tests/backend/test_r11e_tenant_enforcement.py`,
`tests/backend/test_r19k_tenant_isolation.py`. Add a **new** dedicated boundary-test
file for the untagged-compatibility matrix if the existing suites cannot host it
cleanly.

## 26. Files likely affected (S1 only)

- `src/backend/handlers/admin_handler.py` (list/export predicates; `/client/requests`)
- (recommended) a small shared helper in `src/backend/common/` for the tenant scope
  filter, reused by the above
- `tests/backend/test_r11e_tenant_enforcement.py` (extend)
- `tests/backend/test_r19k_tenant_isolation.py` (extend)
- optional new `tests/backend/test_ptm0_s1_untagged_isolation.py`

No Web/Mobile/infra/shared changes in S1.

## 27. Migration / compatibility concerns

- No data migration/backfill required for the primary-only-compatibility option;
  untagged records simply stop being returned to non-primary tenants.
- The export path has an audit side-effect (`EXPORT_BACKUP`) — do **not** use it for
  live read-only testing.
- Do not generalize the notifications/cancellation/Stripe/Calendar "absent company ⇒
  primary" compatibility branches to new tenants; they are live callable branches and
  belong to the S2/S3 boundary review, not S1.
- F04 email-fallback removal (S4) must be preceded by a private membership check and
  session-freshness plan to avoid protected-operator lockout.

## 28. Deployment isolation recommendation

Do **not** deploy `main` wholesale — it contains intentionally undeployed work
(Preview V1, other unrelated changes). When an S1 fix is eventually approved, build
an **isolated backend RC** from the recorded deployed baseline plus the reviewed S1
delta only (the seven-file deployed-source comparison confirms the affected handler
matches deployed source, so a narrow delta is clean). Preserve the current P1
production package state and API `prod -> atxpw3` until a separately approved release.
No deployment, RC, or Terraform action is authorized by this review.

---

## 29. BLOCKER findings

- **F01** — untagged/legacy record visibility in `admin_handler.py` list/export
  predicates (+ `/client/requests` tenant-predicate gap). Confirmed; primary-only
  compatibility policy recommended. → PTM0-S1.
- **F02** — Google/provider authenticated resolution fallback to primary tenant, plus
  a refresh/persist write side-effect on `get_status` and a cross-plane platform
  detail call with caller context. Confirmed; fail-closed policy recommended. → S2.

## 30. HIGH findings

- **F03** — fail-open entitlement loader, ignored `is_active`, platform/mixed-role and
  protected-identity tenant-availability bypass, inconsistent override/grace precedence. → S3.
- **F04** — legacy email→owner elevation in backend + Web + Mobile; Mobile admin→owner
  alias. MIGRATE recommended. → S4.
- **F05** — Cognito/DDB membership + role + active-status drift; best-effort sync is
  not reconciliation. Surface to Platform Admin; fail closed on claim/association
  mismatch. → S3/S5.
- **F06** — non-atomic provisioning existence-check/write; replay always appends audit;
  inconsistent CLI vs Preview default state. → S6 (PTM-8/9), not S1.

## 31. MEDIUM findings

- **F07** — platform mutation and audit write are separate, unchecked, no correlation
  id, no immutability guarantee. Correct before adding new mutation surfaces; does not
  block S1.
- **F08** — no general slug uniqueness/lifecycle/readiness/owner-count model;
  unpaginated platform detail counts; platform detail provider status uses caller
  context. → S5/S6.
- **F09 (LOW)** — stale hierarchy/route/status prose, role-parser differences, Mobile
  alias/cached UI role, primary export filename fallback. Documentation/UI-parity fix.

## 32. Documentation created / changed

- Created (this review): `docs/reviews/ptm-0-source-of-truth-independent-review.md`.
- No changes to the approved PTM-0 specification.
- No changes to `src/`, `web/`, `mobile/`, `infra/`, `shared/`, or any test.

## 33. Commit SHA (if any)

To be recorded on commit of this review document only (targeted `git add` of this
single file). No source/test/infra commit.

## 34. Push status

No push performed by this review step. Push of the review document only if/when
directed, to a non-`main` branch or as an approved docs commit per project git safety.

## 35. Production mutations = ZERO

## 36. Terraform operations = ZERO

(Also: production reads = ZERO; Cognito/DynamoDB writes = ZERO; browser/session =
none; application routes invoked = none; tests run = none.)

## 37. Final disposition

**PTM0_INDEPENDENT_REVIEW_CHANGES_REQUIRED**

The audit is accurate and well-reasoned; overall **C** is correct and PTM-0 is not
implementation-complete. Two BLOCKERs (F01, F02) and four HIGH findings are
independently confirmed in current `main`, which is why the disposition is
"changes required" rather than "approved." The recommended remediation sequence
(S1→S6) is sound; PTM0-S1 (F01 legacy-record read isolation) is approved as the
correct, minimal-blast-radius first slice.

## 38. Exact recommended next implementation step

Present PTM0-S1 to Matthew for an explicit implementation decision:
**confirm the primary-only untagged-compatibility policy (§9/§24)**, then — only on
approval — implement S1 as an offline, test-first change to
`src/backend/handlers/admin_handler.py` using a single shared tenant-scope filter,
extend `test_r11e_tenant_enforcement.py` and `test_r19k_tenant_isolation.py` with
untagged fixtures, run the backend suite locally, and prepare an isolated backend RC
from the deployed baseline + S1 delta. No RC build, deployment, Terraform, Cognito,
or production action until separately approved. F01 (S1) and F02 (S2) remain separate
slices sharing one canonical resolution/compatibility helper.

**Do NOT begin implementation automatically.**
