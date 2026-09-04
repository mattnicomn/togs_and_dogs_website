# PTM0-S2A pre-implementation ownership-contract gate

Date: 2026-09-03

Disposition: **PTM0_S2A_ARCHITECTURE_CONFLICT**

Status: **STOPPED BEFORE RUNTIME/TEST EDITS / LOCAL UNCOMMITTED RECORD**

## Checkpoint and scope

Starting branch `main`; HEAD and local `origin/main` both
`1cca9dd1cca9be3a39257f4d3c11ed7de4c53ac3`. Tracked worktree clean,
index empty, stash empty. The existing untracked
[S2 architecture review](ptm0-s2-f02-architecture-source-of-truth-review.md)
was present and is unchanged by this task.

Matthew authorized S2A only and expressly required an architecture-conflict
stop if exact secret ownership cannot be proved without introducing a new
metadata/naming contract. This record documents that stop condition. It does
not revoke the approved overall S2 architecture direction or start S2B–S2E.

S1/F01 remains deployed, production-accepted and complete. F02 remains
unresolved. S2A implementation has not started; PTM-0 remains incomplete.

## Blocking finding

The repository establishes a tenant-to-secret **reference**, but does not
establish an enforceable ownership contract for every accepted reference.

1. `src/backend/common/google_calendar.py:42–67` looks up
   `TENANT#<company_id> / METADATA` and accepts any truthy
   `calendar_secret_ref`. It does not check the returned metadata owner,
   reference type, namespace, secret owner, uniqueness, or provider enablement
   before returning an explicit reference.
2. `tests/backend/test_r21g_google_token_isolation.py:75–83` deliberately accepts
   `custom/path/to/tokens` for a non-primary tenant. Thus requiring every
   legitimate explicit reference to follow the derived tenant-name path would
   change, not merely enforce, the current accepted contract.
3. [21F](../planning/release-21f-google-per-tenant-token-isolation-plan.md)
   calls `<prefix>/calendar/<company_id>/tokens` a **proposed** naming pattern;
   its compatibility algorithm still prioritizes arbitrary explicit metadata
   references. [21C](../planning/release-21c-tenant-calendar-provider-metadata-model.md)
   calls the pattern future and defines the field as a string/null secret path.
   Current `get_tenant_secret_path` derives such a path only when there is no
   explicit reference and provider metadata enables it.
4. `modules/secrets/main.tf` declares the legacy Google app/token secrets and
   generic tags. No enforced per-tenant owner binding or per-tenant secret
   resource is established there. Searching runtime, modules, and provisioning
   scripts found no provider-owner field, secret ownership lookup, or
   maintained unique tenant-to-secret registry to validate custom references.
5. Tenant provisioning deliberately excludes provider/secret fields. A matching
   tenant row's `company_id` proves whose row was loaded, not whose Google
   connection a potentially misbound opaque reference addresses.

Consequently, merely checking row owner equality would still accept a valid
Alpha row pointing at another tenant's opaque reference. Rejecting all
noncanonical references would reject the existing custom-reference contract.
Scanning other tenant rows is not proof of external ownership: an unregistered
or incorrectly registered reference can still pass. No new registry, secret
tag contract, naming mandate, or allowlist has been invented.

The missing decision is the authoritative ownership evidence for an existing
noncanonical reference, including alias normalization and conflicting or
missing evidence. Requirements to reject cross-tenant/unowned references while
accepting legitimate tenant-owned references cannot both be certified from
the currently established fields alone.

This is a source-contract limitation, not a claim that production has a
misbound reference. No production inspection is needed to establish this gate,
and none was performed.

## Before/after common behavior

**Unchanged: no unsafe fallback has been removed in this stopped task.**

| Location | Current behavior retained | S2A concern |
| --- | --- | --- |
| GC `resolve_google_token_secret_name`, lines 46–60 | None becomes DEFAULT_COMPANY_ID; explicit primary with no truthy reference gets environment/hardcoded legacy secret, including missing metadata | Implicit identity and primary compatibility must be separated after ownership policy approval |
| GC `_get_stored_tokens`, `_save_tokens`, `_get_valid_token` | Optional company forwarded to resolver; write re-resolves and merges existing token state | Requires one validated binding, not repeated independently defaulted lookups |
| GC `_mark_token_revoked`, lines 167–169 | Explicit local None-to-primary conversion before resolver | Removing only resolver conversion leaves this unsafe conversion intact |
| GC `_refresh_access_token` | Optional company; provider exchange precedes `_save_tokens`; invalid-grant branch may omit company when marking revoked | Resolver-only edits cannot guarantee no provider action for an invalid context |
| GC `sync_calendar_event`, lines 485–491 | Reads `item.get('company_id')`; absent/null becomes None | Untagged or null record can reach primary today |
| GC `delete_event_detailed` / `delete_event` | Omitted company flows to valid-token lookup; no token returns success/already-gone | A future denied binding must not be conflated with successful deletion and cause callers to remove event references |
| CM `get_tenant_calendar_config`, lines 10–18,55–87 | Empty record becomes dict; truthy metadata company overrides supplied company; missing provider defaults primary display to Google/connected | Does not validate row/target agreement or reference ownership; presentation is not ownership evidence |

GC = `src/backend/common/google_calendar.py`; CM =
`src/backend/common/calendar_metadata.py`. All primary/default occurrences in
these two files and the Google handler wrappers were traced. Path-prefix
defaults in `get_tenant_secret_path` are naming defaults, not independent
authorization. Existing S1 read-compatibility and other administrative defaults
are outside this provider change and were left untouched.

## Caller compatibility inventory

| Caller | Current missing/default path | Impact of a future common fail-closed change / slice boundary |
| --- | --- | --- |
| Google handler `get_stored_tokens` / `save_tokens`, lines 26–55 | Convert None to primary themselves | Common resolver cannot distinguish this laundered primary argument from a legitimate explicit tenant; requires a separately reviewed narrow interface decision, not silent S2B/C work |
| Google `get_company_id_safe`, lines 89–101 | Malformed event or caught resolution failure defaults primary; scheduled branch also explicitly selects primary | Authenticated fallback is unsafe; trusted scheduled primary has legitimate compatibility intent. Do not treat both as equivalent |
| OAuth callback, lines 267–280 | `state_record.get('company_id')` may yield None | Common rejection would block invalid-state ownership. No callback expiry, replay, consume, or save behavior was changed (S2B deferred) |
| Status/health, lines 340–342,418–420 | Safe helper supplies primary after missing claims or a scheduled event | No GET/refresh separation performed (S2C). Common hardening alone cannot recover provenance once a wrapper supplies primary |
| Review and admin Calendar deletions | `review_handler.py:345,364`; `admin_handler.py:3283,3294` pass only event/request IDs | Company defaults to None. Later S2D must propagate context; do not silently keep primary to make these calls succeed |
| Cancellation deletion | `cancellation_handler.py:248` omits company despite locally deriving it at line 213 | Same S2D dependency; no call-site propagation implemented |
| Sync callers | Intake item, job item, admin current item; review/assignment merged item | Missing/null company yields None. Body override and record propagation remain S2D; no merge changes |
| Token refresh/revocation helpers | `_get_valid_token` forwards optional company; refresh may invoke mark without it | Must validate before any provider operation, not just before persistence |
| Tenant-info and Platform detail | Call CM with record/target and may invoke Google status | Strict metadata agreement could alter outputs for mismatched/missing data. No Platform behavior changes (S2E), no passive-status changes (S2C) |

There are no normal direct calls spelling `resolve_google_token_secret_name(None)`
needed to trigger the issue: omitted optional arguments, `.get` on absent/null
fields, and wrapper conversions are the relevant runtime sources of None.
Adding a falsey return only at the resolver is not a sufficient security fix.

## Existing expectation classifications

No tests were edited to preserve or bless unsafe behavior.

| Tests / expectation | Classification |
| --- | --- |
| 21G `test_default_tenant_legacy_fallback` passes explicit primary | Legitimate primary compatibility intent, but currently no distinct explicit compatibility opt-in. Future policy must name it explicitly, not make it a generic fallback |
| 21G `test_tenant_explicit_secret_ref` accepts opaque custom path | Existing accepted reference behavior; ownership proof is absent. Blocking architecture decision, not permission to assume it is owned or ban it silently |
| 21G explicit Alpha provider-none returns None | Legitimate unconfigured outcome; must stay distinct from invalid/unowned-context rejection |
| 6G token tests call `_refresh_access_token`, `_get_valid_token`, `_mark_token_revoked` without company | Historical unsafe caller convention for tenant-sensitive helpers. Preserve token algorithm test intent with explicit validated context only after policy approval; mocks are not ownership evidence |
| 6G scheduled health fixtures | Legitimate explicitly recognized scheduled-primary intent; not authority for arbitrary None callers |
| 9C status fixtures omit tenant claims | Historical unsafe authenticated fallback fixture. Status refresh semantics themselves remain S2C, not a reason to keep missing-claim primary access |
| 21D metadata tests omit the optional company argument but supply metadata owner | Not simply None-to-primary: identity is supplied inside the record. Future explicit-context API expectations need review; preserve valid record-owned intent, reject unknown/conflicting owner |
| 7E/18P assert deletion calls without company | Historical unsafe provider-context omission; S2D call sites remain deferred |

Tests added: **0**. Tests changed: **0**. Tests executed: **0**.
Requested implementation and regression runs were not reached because the
mandatory ownership-contract gate stopped work before code/test changes.
No PASS count or local implementation readiness is claimed.

## Required architecture input before resuming

Approve or supply the existing enforceable source of truth for exact ownership
of noncanonical `calendar_secret_ref` values, including conflicts, missing
ownership, and equivalent name/ARN references. If it does not exist, explicitly
approve a bounded ownership contract and compatibility policy before S2A code.

That decision may select an explicit validated binding registry/mapping,
an authoritative owner attribute with controlled assignment, or a required
naming contract with reviewed legacy exceptions. These are alternatives for
independent review, **not implemented proposals or production authorization**.
Providing secret values is neither needed nor requested.

## Final scope and hygiene

- Created only this local review record, unstaged/uncommitted.
- Existing architecture review preserved unchanged.
- Runtime, tests, OAuth callback, status GET refresh, Platform Admin behavior,
  workflow body merges and Calendar handler propagation all unchanged.
- No S2B/S2C/S2D/S2E implementation. F02 remains unresolved.
- Production/AWS/Google/provider access: ZERO. Terraform operations: ZERO.
- Credentials, Secrets Manager, tenants and production data: untouched.
- Commits/pushes/staging: NONE. HEAD and origin/main unchanged.
- Expected ending worktree: tracked files clean plus the two untracked review
  records; empty index and stash.
