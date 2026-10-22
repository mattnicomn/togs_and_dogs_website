# Workstream 1 — Existing Pet Selection (canonical request↔pet association)

**Disposition:** `W1_CANONICAL_PET_ASSOCIATION_HARDENED_READY_FOR_FINAL_REVIEW`

`W1_IMPLEMENTATION_STATUS=LOCAL_IMPLEMENTED_NOT_DEPLOYED`

> **Contract hardening (PR #26 follow-up commit):** invalid supplied existing-pet associations
> now **reject the whole client request generically** (HTTP 400, nothing persisted) instead of
> being silently dropped; the `pet_ids` field shape is validated at the API boundary; and new-pet
> identity is decided by the absence of a canonical `pet_id` (never by display-name equality),
> with request-scoped idempotency (`created_from_request_id`). See the hardened descriptions
> below.

**Checkpoint at authoring:** branch `fix/w1-canonical-request-pet-association` created from
`origin/main == 066a260af3b3c95af2e36a4dbf945f8234ac099f`. Not merged, not deployed.

> **Naming boundary:** this is *PetCare Hero Workflow & Payment Architecture — Workstream 1,
> Existing Pet Selection (canonical pet association)*. It is **NOT** the historical *Ryan
> Cross-Platform Alignment W1 — 20-Minute Walk Canonical Scheduling Windows*, which is
> untouched.

## What this implements

The canonical request↔pet association is now a **`pet_ids: string[]`** array for existing
profile pets. `pet_names` becomes a derived display / legacy-compatibility value and is never
the identity authority when `pet_ids` is present.

`CANONICAL_REQUEST_PET_ASSOCIATION=pet_ids: string[]`

### Mobile (`mobile/src/screens/IntakeScreen.tsx`)
- Existing-pet selection state is keyed by **`pet_id`** (`selectedPetIds`), not by name. The
  first pet is pre-selected by its id; pet chips toggle by id; duplicate pet names remain
  independently selectable; deselection/reselection operate on ids.
- Submission sends canonical `pet_ids` for the selected existing pets (present only when at
  least one existing pet is selected). The structured `pets[]` entries for existing selections
  carry their `pet_id`; the typed "add new pet" fallback is a new `pets[]` entry with no id.
- The derived `pet_names` display string is built from the ID-backed selected pets plus any
  typed new pet — never from a name→id lookup (the old `availablePets.find(p => p.name === name)`
  and comma-joined `pet_names`-as-identity producer are eliminated for existing pets).
- Review screen derives human-friendly names from the selected ID-backed pets.

### Web client (`web/src/components/IntakeForm.jsx`)
- `W1_WEB_CLIENT_PARITY_REQUIRED=YES`. The authenticated-client intake flow now has a
  first-class existing-pet picker (it previously only had a type-your-own `pets[]` entry). It
  loads the client's pets **once** via the client-safe `getClientPets()` (`GET /client/pets`),
  selects by `pet_id` (duplicate names independently selectable, removal/reselection supported),
  and submits canonical `pet_ids`. The structured new-pet entry path is preserved; empty new-pet
  rows are dropped before submit. No admin pet endpoint is used; no N+1 pet calls.
- The public (unauthenticated) intake path is unchanged and never produces `pet_ids`.

### Backend
- `src/backend/common/pet_profile.py`:
  - `resolve_owned_pet_ids(raw_pet_ids, client_id, company_id)` — the canonical ownership gate.
    **Existing-pet association is ALL-OR-NOTHING** (hardened): if the client supplied a `pet_ids`
    field at all, every entry must be a well-formed string id for an **active PET owned by this
    client under this tenant** (same filter as `GET /client/pets`, via `_owned_pet_map`). It
    returns a validity signal (`ok`/`supplied`/`reason`): a non-list shape, a non-string/blank
    entry, or ANY unowned id (covering foreign-client, foreign-tenant, inactive, unknown) makes
    `ok=False`. An absent field (or empty list) is valid new-pet-only intake. Order-preserving
    dedupe of valid ids; display names derived from the owned records. Fails closed without
    trusted identity. The offending id / reason are **never surfaced** (logging only).
  - `create_or_link_pets_from_request` treats a canonical `pet_ids` array as **authoritative**
    (existing selections never re-created/renamed) and decides what is new by **identity, not
    name**: a structured `pets[]` entry is an echo of a *client-selected* existing pet iff its
    `pet_id` is a canonical id that is NOT this request's own creation provenance; every other
    entry is new-pet intent and is created even if some owned pet shares its display name.
    **Real-retry idempotency is request-scoped** via `created_from_request_id == request_id`:
    all active pets this request created on any earlier run are kept available for reconciliation
    **even when they already appear in the request's persisted `pet_ids`** (the first run appends
    the new-pet IDs to `pet_ids`, so a true retry sees them there) — the id-less structured
    new-pet entries are reconciled deterministically (stable `created_at`/`pet_id` order) against
    that request-created provenance set, and only a genuine shortfall is created. A same-name pet
    from a different request or a pre-existing owned pet never suppresses creation and is never
    treated as this request's identity. A second and third invocation over the persisted
    post-first-run REQUEST create nothing and keep the same final `pet_ids`. The legacy name-match
    path remains only for requests without `pet_ids`.
- `src/backend/handlers/intake_handler.py` (authenticated client-portal path only):
  - Calls `resolve_owned_pet_ids` against the **server-resolved** `client_id` / `company_id`
    (never body-supplied identity). If `ok` is False the whole request is **rejected with a
    single generic, non-disclosing HTTP 400** ("One or more selected pets are invalid. Refresh
    your pets and try again.") and **nothing is persisted** — no silent partial drop, no
    new-pet-only fallback. On success it persists the validated canonical `pet_ids` and derives
    the display `pet_names` from the validated owned pets + structured NEW-pet entries (new
    entries distinguished by lacking a canonical `pet_id`, so a new pet sharing a selected pet's
    name is still listed). Spoofed caller names never override canonical identity/name.

## Canonical contract guarantees
- `W1_PET_OWNERSHIP_ENFORCEMENT=PASS` — every accepted existing `pet_id` is proven to belong to
  the authenticated client, within the client's tenant, and active. No trust in caller-supplied
  `client_id`/`company_id`/PK/SK/arbitrary ids. No cross-client or cross-tenant association.
- `W1_INVALID_PET_ID_REQUEST_REJECTION=PASS` — a supplied existing-pet selection is **all-or-
  nothing**: any malformed, inactive, unknown, foreign-client, or foreign-tenant id rejects the
  entire client request (generic HTTP 400, nothing persisted). Invalid ids are NOT silently
  dropped and do NOT fall back to new-pet-only.
- `W1_PET_IDS_INPUT_VALIDATION=PASS` — if the `pet_ids` field is present it must be a list of
  non-empty strings; a non-list shape or any non-string/blank entry is rejected generically.
  Absence of the field remains valid for new-pet-only intake.
- `W1_NAME_IS_NOT_IDENTITY=PASS` — new-pet intent is identified by the absence of a canonical
  `pet_id`, never by display-name equality. A genuinely-new pet sharing a selected/owned pet's
  name is still created; two distinct owned pets with the same name stay independently associated
  by id.
- `W1_MIXED_NEW_PET_IDEMPOTENCY=PASS` / `W1_REAL_PERSISTED_RETRY_IDEMPOTENCY=PASS` — mixed
  existing+new retries are idempotent via request-scoped provenance (`created_from_request_id`),
  not global same-name ownership, and are proven against the **persisted post-first-run REQUEST
  state** (`pet_ids` already containing the created new-pet IDs) across second and third
  invocations (zero re-creation).
- The response is **non-disclosing**: it never reveals which id failed, nor whether an id exists,
  belongs to another client/tenant, or is inactive.
- `W1_NEW_REQUESTS_CANONICAL_PET_IDS=PASS` — new authenticated-client requests persist canonical
  `pet_ids` for existing selections; names are derived.
- `W1_LEGACY_READ_COMPATIBILITY=PASS` — legacy `pet_id`, `pet_ids`, `pets`, and `pet_names`
  (string/array) read shapes remain readable; no historical REQUEST records were migrated or
  rewritten. (Legacy-read compatibility does not authorize new name-only canonical writes.)
- `W1_CLIENT_REQUEST_PRIVACY_BOUNDARY=PASS` — the PR #22 `/client/requests` allowlist projection
  (in `admin_handler.py`) is untouched; `pet_ids` are persisted on the REQUEST write but were not
  added to the client list projection, and no raw PK/SK or internal/admin pet metadata is exposed.
- `W1_N_PLUS_ONE_PET_FETCHES_ADDED=NO` — mobile and web load the client's pets once; list/card
  surfaces add no per-row pet fetches.

## Add-new-pet behavior
Existing + newly-added pets are representable with the current intake semantics: `pet_ids` for
existing selections and the structured `pets[]` array for new pets. A selected existing pet is
not duplicated into a new `pets[]` entry. **No new client pet-creation endpoint was invented**
(`W1_NEW_PET_CREATION_ARCHITECTURE_CONFLICT_FOUND` was NOT triggered); the established approval-
time `create_or_link_pets_from_request` path handles new-pet creation.

## Admin / scheduling compatibility
Admin-created bookings, `APPROVED` / `VISIT_BOOKING` semantics, scheduling payloads, assignment,
service windows, Ryan historical W1 Walk behavior, and Overnight O1 behavior are **unchanged**
(this is pet-association normalization, not a scheduling redesign). The admin new-visit flow and
Admin Client Management were not redesigned.

## Tests
- Backend: `tests/backend/test_w1_canonical_pet_association.py` — **39 tests** covering ownership
  / tenant / dedupe / order / duplicate-name-distinct-id; hardened all-or-nothing validity
  (absent-ok, empty-ok, non-list shape rejected, non-string/blank entry rejected, any unowned id
  rejects whole selection, fail-closed); handler-level generic non-disclosing 400 with no
  `put_item` on invalid input; valid existing + new pet persists; new pet sharing a selected
  pet's name is still listed/created; identity-not-name mixed linking (echo-by-id skipped,
  new-by-absence-of-id created, same-name unselected/other-request pet does not suppress);
  **real persisted-post-first-run retry idempotency** (first run creates once and appends the
  new-pet ID to `pet_ids`; second and third runs over the persisted association create nothing),
  multi-new-pet deterministic retry reconciliation; spoofed names not overriding identity; public
  path unaffected; legacy name path preserved. **PASS**.
- Mobile: `mobile/__tests__/IntakeScreen.test.tsx` — 7 new W1 tests (ID-keyed selection,
  duplicate-name independence, multi-select, deselect/reselect, new-pet-only, existing+new, no
  name→id reconstruction). Full IntakeScreen suite **35/35 PASS**; `tsc --noEmit` clean.
- Web: `web/tests/IntakeFormExistingPetSelection.test.jsx` — 6 new W1 tests (load-once via
  client-safe endpoint, select by id, multi + removal/reselection, duplicate-name independence,
  add-new preserved, existing-only submit). Full vitest suite **29 files / 444 tests PASS**.
- `W1_NEW_REGRESSIONS=0` — full backend suite shows an identical pre-existing failure set on this
  branch and on the clean baseline `066a260` (90 failed on both; this branch has +19 passing =
  the new W1 backend tests). The pre-existing failures are environmental (Google Calendar provider
  metadata, tenant resolution, Stripe/Postmark, entitlement DB) and unrelated to pet association.

## Not done / boundaries
- Not deployed: no web deploy, no mobile build/distribution, no Terraform, no AWS mutation, no
  API Gateway deployment, no backend deployment. `W1_DEPLOYED=NO`.
- `NEXT_RECOMMENDED_WORKSTREAM` after W1 per the approved sequence (W2 → W4 → W1 → W3) is W3,
  which remains **not authorized**.

## Gates preserved (unchanged by W1)
`SCHEDULING_WORKSTREAM_STATUS=DRAFT_PR_DELIVERY_CHECKPOINT`;
`SCHEDULING_PR_MERGE_AUTHORIZED=NO`; Stripe sandbox-only; `RYAN_TESTING_AUTHORIZED=NO`;
no second tenant; no production test data; no production quote mutation (Send/Accept/Decline);
no EAS/TestFlight/App Store/Google Play/public mobile distribution; no web deployment. W3 not
authorized. Latest completed production backend release remains
`PR22_PRIVACY_PRODUCTION_DEPLOYED_VERIFIED`.
