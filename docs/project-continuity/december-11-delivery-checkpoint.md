# December 11 Delivery Checkpoint (ACTIVE)

**Status:** ACTIVE delivery checkpoint for the single-business pilot (Togs & Dogs on PetCare Hero).
**Target:** usable Android + web application by **2026-12-11**.
**As of:** 2026-11-13 (B6-C1 production baseline documentation reconciliation after the owner-approved read-only B6-B1 AWS metadata verification; see §16). *(Prior as-of text for the same date, preserved: B5-C1 post-merge documentation reconciliation after the owner-authorized B5-B squash merge of PR #78 into `main` at `cac3cd6a82220353c1d48599b484368f78251033`.)* **Assessment:** **AT RISK — RECOVERING (Full-Stack Source Integration MERGED to `main`, NOT DEPLOYED; Calendar Option 3A Selected; Full Convergence for Planning Only; Gated on Pre-Deploy Verification, W1 Release Scope, and Deploy/Build/Distribution Approvals)** (see §5).
*(Previous as-of line, preserved: 2026-11-13 (B4.1 final documentation accuracy & owner planning decision reconciliation on top of full-stack Draft PR #78). Assessment: AT RISK — RECOVERING (Full-Stack Source Candidate Verified & CI Green; Consolidated Strategy & Calendar Option 3A Selected; Gated on Explicit Merge Authorization, W1 Release Scope, and Deploy/Build Approvals).)*

This file is the shared checkpoint for ChatGPT, Kiro Desktop/Web and authorized implementation
agents. It does not replace [`guardrails.md`](guardrails.md) (canonical policy) or
[`current-state.md`](current-state.md) (production record). It references existing release notes
rather than repeating them.

> **B4 Reconciliation Note (Draft PR #74 Integration):** This file adopts and reconciles Draft PR #74 (`afa75c4a3b9ac52198b7ff193686df3968957ebd`, `docs/december-11-delivery-checkpoint`) on top of the source-accepted full-stack integration candidate **Draft PR #78** (`2ef5a1f43b256189860a9c5f97d87e274c338211`). Every standing rule, historical note, Kiro shell procedure, and initial 2026-11-12 snapshot/resume block from PR #74 is preserved without silent deletion; §14 explicitly maps what from PR #74 is adopted verbatim versus superseded by batches B1-A (#75), B1-B (#76), B2-A (#77), B2-B (Android source audit), B2-C (#78), B3 (read-only RC assessment), and B4 (documentation & release-gate reconciliation).

> **B5 Integration Note (2026-11-13):** Matthew issued an explicit structured Gate C3c `MERGE AUTHORIZATION` for PR #78 only (head `77e8ec8fbefe92134b829ebc9533c516af0f6262`, target `main`, squash, integration only). After B5-A non-force fast-forwarded the PR #78 branch from `2ef5a1f` to `77e8ec8` (adding the 12 B4/B4.1 docs files) and the full pre-merge checklist passed, B5-B converted PR #78 to Ready and squash-merged it: `main` `8fe7fa78ad707ac67a05d29059d2771a9aa256c8` → **`cac3cd6a82220353c1d48599b484368f78251033`** (89 files; tree identical to the approved head). **Merged ≠ deployed:** nothing was deployed, built, distributed or acceptance-tested. Historical 2026-11-12 / B4.1 text below is preserved and marked where superseded (see §4.2, §13).

---

## 1. Standing rules for this checkpoint

1. **Update this file** at every material task completion or change in release readiness. Keep it
   short. Link to release notes; do not copy them. Preserve historical evidence; replace only the
   snapshot, board and resume block.
2. **Approvals are scoped.** A previous owner approval covers only the exact action, PR, SHA and
   scope it named. A new session never infers approval for merge, Ready, deploy, build,
   distribution, production data, Ryan testing, Stripe or tenant changes.
3. **Re-verify live state.** Every session re-checks `origin/main` and every PR head with `git`
   and `gh` before acting. The SHAs below are a dated snapshot, never a current fact.
4. **Distinguish the stages.** Code complete ≠ source accepted ≠ merged ≠ deployed ≠ built ≠
   distributed ≠ acceptance-tested. Source acceptance (independent review of a Draft PR head) is
   not integration or release. Passing tests or an open Draft PR is not released functionality.

---

## 2. Verified snapshot (2026-11-13 — Post-B5-B Merge / B5-C1)

Verified with `git fetch` / `git rev-parse` / `gh pr view` / `gh api` on 2026-11-13 (dated
snapshot; re-verify live state before acting).

| Item | Value |
|---|---|
| `origin/main` | **`cac3cd6a82220353c1d48599b484368f78251033`** — squash merge of PR #78 (2026-11-13T17:50:52Z), single parent `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`, tree `f875c2c1583eba400a20ba3733f2e1c922077e90` (identical to the approved PR #78 head `77e8ec8fbefe92134b829ebc9533c516af0f6262` tree) |
| Merged scope | 89 files (+11,872 / −727) vs `8fe7fa7`: 12 docs, 18 mobile, 5 backend source, 23 backend tests, 31 web; zero infra/Terraform/CI/EAS/app-config files |
| Approved CI evidence | Run `43463005295` (`pull_request`) on `77e8ec8`: `backend`, `web`, `mobile`, `shared` `SUCCESS` + `GitGuardian` pass (5/5) |
| CI on `main` | None — `.github/workflows/ci.yml` triggers on `pull_request` to `main` only; no push-to-`main` run exists or is expected |
| Ruleset `protect-main-mvp` | Unchanged: PR required, 0 approvals, no required status checks, deletion + non-fast-forward blocked. Merge attributed to the owner identity; no independent human GitHub review (ChatGPT independent source review only) |
| Source branches | `integration/b2c-full-stack-verification` and `docs/b4-release-gate-reconciliation` retained at `77e8ec8` (not deleted) |
| Main checkout | on `fix/web-eslint-baseline-20261011` with one untracked `infra/prod/_gatea_plan_out.txt` — preserve; local `main` ref fast-forwarded to `cac3cd6` |
| `origin/main` (B6-C1 update) | `61e84d9649d016f462a4f436f8ec266b83e2d2de` — PR #80 B5-C1 docs squash merge on top of `cac3cd6` (4 docs files) |
| Production baseline (B6-B1) | Live-verified read-only on 2026-11-13 — see §16 |

PR status after B5-B:

| PR | State | Head | Disposition |
|---|---|---|---|
| **#78** B2-C full-stack integration | **MERGED** (squash `cac3cd6`) | `77e8ec8fbefe92134b829ebc9533c516af0f6262` | Integrated into `main`; NOT deployed |
| **#79** B4/B4.1 docs reconciliation | MERGED (GitHub auto-marked when its head `77e8ec8` landed in its base branch during B5-A; no merge action taken) | `77e8ec8fbefe92134b829ebc9533c516af0f6262` | Content in `main` via #78 |
| #75, #76, #77, #71, #72, #73, #74, #46, #67, #68, #69, #62, #43 | OPEN, Draft (unchanged) | as in §2.1 | **Closure candidates** per §15 read-only audit — closure NOT authorized |
| #45 inactive advisory-baseline policy | OPEN, Draft (unchanged) | `3c5679d72dd3cb239ec6785ce31d96e5d95799cb` | Content NOT in `main`; requires a separate Matthew policy decision |

### 2.1 Historical verified snapshot (2026-11-12 — Post-B2-C / B3 / B4) — preserved; superseded by §2 above

Verified with `git fetch` / `git rev-parse` / `gh pr view` / `gh pr checks` on 2026-11-12.

| Item | Value |
|---|---|
| `origin/main` | `8fe7fa78ad707ac67a05d29059d2771a9aa256c8` (2026-10-28, PR #14 test isolation; previous #5 CI workflow, #42 W3-C2 acceptance docs) |
| Stash (main checkout) | none |
| Main checkout | on `fix/web-eslint-baseline-20261011` (PR #6 branch) with one untracked `infra/prod/_gatea_plan_out.txt` — preserve |
| Ruleset `protect-main-mvp` | PR required, 0 approvals, no required status checks enforced by ruleset (Gate C3c 10-point checklist + Matthew `MERGE AUTHORIZATION` mandatory per [`guardrails.md`](guardrails.md)) |

Release-relevant Draft PRs (all OPEN, Draft, unchanged by B4):

| PR | Branch → base | Head SHA | Mergeable | CI status |
|---|---|---|---|---|
| **#78 B2-C full-stack integration verification** (#77 + #46/#67/#68/#69, 86 files) | `integration/b2c-full-stack-verification` → `main` | `2ef5a1f43b256189860a9c5f97d87e274c338211` | MERGEABLE | **5/5 `SUCCESS`** (run `43359979814`: `backend`, `web`, `mobile`, `shared`, `GitGuardian`) |
| **#77 B2-A combined backend/web verification** (#76 + #71 + #72 + #73, 61 files) | `integration/b2a-backend-web-verification` → `main` | `16471f858062f20ec3814e22a5cae76524d0a94b` | MERGEABLE | **5/5 `SUCCESS`** (run `43355736742`) |
| **#76 B1-B web green CI + tenant-detail stale-response guard** (40 cumulative files on #75) | `web/b1b-web-green-ci` → `main` | `2d69045d9bd50e3a6f3f4cee0c4b8fd80ffcdd79` | MERGEABLE | **5/5 `SUCCESS`** (run `43349187490`) |
| **#75 B1-A backend green CI + R7E legacy multi-day window fix** (17 files) | `test/b1a-backend-green-ci` → `main` | `b91e8ccf73ba2c1223957069c626c4c0029c3f7d` | MERGEABLE | `backend`/`mobile`/`shared`/`GitGuardian` pass; `web` red = pre-#76 baseline |
| **#74 December 11 delivery checkpoint** (initial docs-only checkpoint) | `docs/december-11-delivery-checkpoint` → `main` | `afa75c4a3b9ac52198b7ff193686df3968957ebd` | MERGEABLE | `mobile`/`shared`/`GitGuardian` pass; `backend`+`web` red = `main` baseline (adopted & reconciled by B4) |
| **#46 Android booking workflow remediation** | `mobile/android-workflow-remediation` → `main` | `06ee9d628ac57d1a988e264ec74c26fe41174125` | MERGEABLE | `mobile`/`shared`/`GitGuardian` pass; `backend`+`web` red = `main` baseline (included in #78) |
| **#67 S1 owner/admin quote editor + S1-R1 hydration** | `mobile/s1-admin-quote-editor` → #46 | `d60b1b203782c7b99382e2cfd525b96757dd720c` | MERGEABLE | stacked on #46; verified 5/5 green in #78 |
| **#68 A-1 owner/admin/staff visit Start/Complete** | `mobile/s1-visit-rbac-a1` → #67 | `257e045fe15095c981a08b6345efd076ee80ba3f` | MERGEABLE | stacked on #67; verified 5/5 green in #78 |
| **#69 S2 cancellation decisions + D-4 BE-CANCEL-1 compatibility** | `mobile/s2-cancellation-decisions` → #68 | `e4040ef040cd49fb05bd3ba09b7999475f765ea5` | MERGEABLE | stacked on #68; verified 5/5 green in #78 |
| **#71 BE-CANCEL-1 decision safety, cycle id & review guard** | `fix/be-cancel-1-decision-safety` → `main` | `ccf2d8460bde909e1bb63d812f360de1f62ecf8e` | MERGEABLE | `mobile`/`shared`/`GitGuardian` pass; verified 5/5 green in #77/#78 |
| **#72 WEB-CANCEL-1 decisions + cycle id** | `web/web-cancel-1-cycle-compatibility` → `main` | `56174ce7a947a83e41cf44ea0ac68e1e3bf0eb3c` | MERGEABLE | `mobile`/`shared`/`GitGuardian` pass; verified 5/5 green in #77/#78 |
| **#73 D-1 client denial marker** | `feat/d1-client-denial-marker` → `main` | `6f1c60ad2e32cb1ad06622d277cd0bf4cb50b287` | MERGEABLE | `mobile`/`shared`/`GitGuardian` pass; verified 5/5 green in #77/#78 |
| **#62 C3.1 combined backend test isolation** | `test/c3-1-combined-backend-test-isolation` → `main` | `057de19c01fbe24883192da3c68fbfda3bfadf1f` | MERGEABLE | superseded by #75 (`b91e8cc`) |
| **#43 web Class A lint cleanup** | `pra-lint-only` → `main` | `9a5dc1dd313116e6cec70d9bf52bdb82c4b67c7e` | MERGEABLE | superseded by #76 (`2d69045`, 0 lint errors) |
| **#45 inactive advisory-baseline policy** | `governance/c3b-advisory-baseline-acceptance` → `main` | `3c5679d72dd3cb239ec6785ce31d96e5d95799cb` | MERGEABLE | adoption BLOCKED (no longer needed because #75/#76/#78 pass CI cleanly) |

Mobile stack: **#69 → #68 → #67 → #46 → `main`**, combined with **#77 (#76 + #75 + #71 + #72 + #73)** in **Draft PR #78 (`2ef5a1f43b256189860a9c5f97d87e274c338211`)**. Also open: #6 and #18 (CONFLICTING), #7–#17 (source PRs consolidated by #62/#75), #37, #44, #47–#60 and #63–#66 (inactive contracts and orchestrator work, not on the December 11 path).

---

## 3. Production versus source-only

**Latest completed production milestone:** W3-C2 `MANUAL_EXTERNAL` bounded functional acceptance,
**2026-10-27** (`W3C2_FUNCTIONAL_ACCEPTANCE=COMPLETE` for the approved single full-settlement scenario on internal `test_tenant_alpha`; following the 2026-10-27 admin-only serialization fix deployment `263b3e7` → `GlA3mUtq…` and the 2026-10-24 Phase A/B/C route deployment `ef39b178` → stage `n40vai`). See
[W3-C2 release note](../release-notes/w3c2-manual-external-payment-route.md) and
[`current-state.md`](current-state.md).

Recorded production state (from `current-state.md`, not re-verified against AWS here):
*(B6-B1 update 2026-11-13: the Lambda, API Gateway, IAM and Web items below were subsequently
live-verified read-only and all match — see §16.)*

- **Admin Lambda (`togs-and-dogs-prod-admin`):** `CodeSha256 GlA3mUtq3O0RJcdc3i2MQjwcbuo8aiv52ACvacQH99o=` (deployed 2026-10-27 from `main == 263b3e7`).
- **Other 12 Lambdas (`intake`, `review`, `assign`, `job`, `google-auth`, `pet`, `cancellation`, `device`, `ses-feedback`, `postmark-webhook`, `stripe-webhook`, `platform`):** `CodeSha256 W6cqyudlRQF3Zw7uN2V42JzziwYITg8r5mCnsGdDAq4=` (deployed 2026-10-22 from curated PR #22 privacy RC `b94455a`).
- **API Gateway (`a022yxuiue` / stage `prod`):** deployment `n40vai` (2026-10-24).
- **Web (`toganddogs.usmissionhero.com`; bucket `togs-and-dogs-prod-toganddogs-hosting`; CloudFront `E35L00QPA2IRCY`):** deployed 2026-10-08 (W2C Gate D2, as recorded) from `main == 7c1a8f1f898233e37ee5c77e38bb92058deee3c7` (`index-DrAWpyW_.js`, `index-DEfFpwho.css`). *(B6-B1 2026-11-13: live-verified — public `index.html` SHA-256 `cc453a6e…` matches the W2C record and references `index-DrAWpyW_.js` / `index-DEfFpwho.css`; 11 bucket objects; CloudFront `Deployed`. Live object timestamps read 2026-10-10 UTC; see §16. Hostname corrected from the previously recorded `app.togsanddogs.com`.)*
- **Mobile internal builds:** iOS `1.0.0 (6)` / Android `1.0.0` versionCode `4`, both from
  `bf9f80d95c1846f197bab24d96463906bc26bfce`. **None** of the D1/D2, E3B/E3B.1, OPS-3A.3 client quote UX, W4 Option A, W1 `pet_ids`, or #46–#69 mobile work is in a distributed build.
- **W1 & untargeted apply guard:** `W1_PRODUCTION_RELEASE_AUTHORIZED=NO`; `W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES` — an untargeted `terraform apply` would sweep all 12 non-admin Lambdas and ship every merged-not-deployed backend change at once. Prohibited without explicit Matthew approval.
  *(B5-B update 2026-11-13: since `main` is now `cac3cd6`, an untargeted apply would additionally ship the entire merged PR #78 backend scope — BE-CANCEL-1, D-1, R7E — alongside W1. Still prohibited.)*
- Stripe sandbox-only (EIN). `TENANT_RESOLUTION_MODE=multi` unchanged.

### Two distinct `W1` concepts in repository source (deployment status corrected in B6-B1; original 2026-11-12 heading read "both NOT deployed on `intake`/`job` Lambdas")

1. **Workstream 1 (`W1`) — Canonical Existing-Pet Association (`pet_ids`)** (PR #26 `429f3b9`,
   [release note](../release-notes/w1-canonical-request-pet-association.md)): authenticated client
   portal intake (`POST /client/requests`) validates `pet_ids` all-or-nothing against active pets
   owned by the caller in `intake_handler.py`/`common/pet_profile.py`, and links canonical `PET#`
   records on approval in `job_handler.py`.
2. **Ryan Slice `W1` — Canonical 20-Minute Walk (`WALK_20MIN`) Scheduling Windows** (`c51828e`,
   [release note](../release-notes/ryan-w1-walk-canonical-scheduling-windows.md)): enforces
   `MORNING`/`MIDDAY`/`EVENING` single-window selection, deterministic UUIDv5 child `JOB` IDs, and
   deterministic `td<uuid_hex>` Google Calendar event IDs in `intake_handler.py`, `job_handler.py`,
   and `common/check_in.py`.
   *(B6-B1 2026-11-13: **`BACKEND_CODE_DEPLOYED`** — this Ryan Slice W1 Walk backend code (`c51828e`)
   is in the live 12 non-admin Lambda artifact `W6cqyudl…` (see §16). Runtime acceptance, customer
   use and Ryan testing are NOT verified or claimed. Item 1, Workstream 1 `pet_ids`
   validation/linking (#26 `429f3b9`), remains **NOT DEPLOYED**.)*
- **Gate:** **`W1_PRODUCTION_RELEASE_AUTHORIZED=NO`**. Neither W1 workstream is authorized for
  production deployment.
  *(B6-B1: gate unchanged — `W1_PRODUCTION_RELEASE_AUTHORIZED=NO`,
  `W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES`. The gate wording predates the finding that Ryan Slice W1
  Walk backend code is already deployed; reconciling its scope is an open owner decision. No
  historical approval is reinterpreted and no new approval is inferred.)*

**Merged to `main` (`8fe7fa7`) but NOT deployed on the 12 non-admin Lambdas, Web (`7c1a8f1`), or Mobile (`bf9f80d`):**
Ryan Slices A–C, C1, D1–D2, R1, W1 Walk (`WALK_20MIN`), O1 Overnight (`21:00–07:00`), E1, E2, E3A
(present in `admin` Lambda `GlA3mUtq…` and Web `7c1a8f1`, absent from `intake`/`review`/`assign`/`job`
Lambdas and Android `vc4`); Workstream 1 `pet_ids` association (PR #26/#27); W3-B/W3-C1 payment
domain/adapter (PR #29/#31, present inside `admin` Lambda via W3-C2, dormant on the other 12); W4
Option A client status presentation (PR #24, web/mobile); AC-9 Google OAuth diagnostics (`google-auth`
Lambda). See [`document-map.md`](document-map.md) for each release note.
*(B6-B1 2026-11-13 correction, list above preserved as recorded: the 12 non-admin Lambdas are
live-verified on `W6cqyudl…`, byte-identical to the retained rollback ZIP whose 49 files match RC
`b94455a` exactly. That artifact contains the backend code of Ryan O1 Overnight (`46bb6b8`), E3A
child start (`e10a98e`), Ryan W1 Walk (`c51828e`) and R1 (`66d6cc3`) → **`BACKEND_CODE_DEPLOYED`**
on `intake`, `job` and the other non-admin functions. Runtime acceptance, customer use and Ryan
testing are NOT verified or claimed. Slices A–C, C1, E1 and E2 backend presence was not
individually re-verified; D1–D2 and E3B/E3B.1 are mobile and are not in distributed builds. Still
**NOT DEPLOYED**: Workstream 1 `pet_ids` (#26/#27), W3-B/W3-C1 on the 12, W4 Option A, AC-9, and all
PR #78 scope.)*

**Source-only (Draft PRs):** everything in the §2 table (combined in **Draft PR #78** at
`2ef5a1f43b256189860a9c5f97d87e274c338211`).
*(B5-B update 2026-11-13: the line above is the 2026-11-12 state. All PR #78 content — #75, #76,
#71, #72, #73, #77, #46, #67, #68, #69 plus the B4/B4.1 docs — is now **merged to `main` at
`cac3cd6a82220353c1d48599b484368f78251033` but NOT deployed** on any Lambda, Web, or Mobile build,
joining the merged-not-deployed list above.)*

### Verified API route contract (`modules/api/main.tf`)

PR #78 adds **zero** new API Gateway routes or Terraform changes; all operational routes below are
already defined in `modules/api/main.tf` on REST API `a022yxuiue` (stage `prod` → `n40vai`):

- **`PUT /admin/cancel/decision`** → `cancellation` Lambda (`handlers.cancellation_handler.handler`):
  **canonical owner/admin cancellation decision path** (`APPROVE` / `DENY` with
  `cancellation_request_id`). Under `BE-CANCEL-1C` (PR #71), `POST /admin/review` rejects all
  cancellation-state transitions (`CANCELLATION_REQUESTED` / `CANCELLATION_DENIED`) with HTTP `409
  CANCELLATION_TRANSITION_NOT_ALLOWED`.
- `POST /client/cancel` → `cancellation` Lambda (client cancellation request; body `request_id`,
  `client_id`, `reason`). *(Corrected in B6-C1, 2026-11-13: previously listed as
  `POST /client/requests/{requestId}/cancel`; see `modules/api/main.tf` resource `client_cancel`.)*
- `POST /requests` (public intake) & `POST /client/requests` (authenticated client intake) →
  `intake` Lambda (`handlers.intake_handler.handler`).
- `GET /client/requests` → `admin` Lambda (`handlers.admin_handler.handler`, using
  `common/auth.py` allowlist + D-1 derived `cancellation_denied` / `cancellation_denied_at`).
- `GET /admin/requests`, `GET /admin/requests/{requestId}`,
  `PATCH /admin/requests/{requestId}/quote`, `POST /admin/requests/{requestId}/quote/send`,
  `POST /admin/requests/{requestId}/external-payment`, `POST /admin/job/start`,
  `POST /admin/job/complete` → `admin` Lambda.
- `POST /admin/review` → `review` Lambda (`handlers.review_handler.handler`).
- `POST /admin/assign` → `assign` Lambda (`handlers.assignment_handler.handler`).

---

## 4. Product decisions, blocked actions and gates

Approved (owner):
- **D-1 / D-3:** client-portal cancellation-denial marker; verified historical prior status only
  (BE-CANCEL-1 Option A restores captured `APPROVED`/`ASSIGNED`); **no denial email**. Mobile
  client marker deferred.
- **Android integrated workflow scope (source-only in PR #78):**
  - **#46 (`06ee9d6`):** M&G prerequisite recovery, explicit `READY_FOR_APPROVAL`, exact child-visit
    selection, and per-child in-memory draft notes ([release note](../release-notes/android-booking-workflow-remediation.md)).
  - **#67 (`d60b1b2`):** owner/admin mobile `DRAFT` quote create/edit/send with S1-R1 authoritative
    `GET /admin/requests/{id}` hydration, superseding `#46`'s web-only `QUOTE_NEEDED` handoff
    ([release note](../release-notes/android-s1-admin-quote-editor.md)).
  - **#68 (`257e045`):** `owner | admin | staff` visit `Start`/`Complete` (`const canExecuteVisits = role === 'owner' || role === 'admin' || role === 'staff'` in `mobile/src/screens/RequestDetailScreen.tsx`),
    superseding `#46`'s staff-only execution boundary.
  - **#69 (`e4040ef`):** owner/admin mobile cancellation decisions (`PUT /admin/cancel/decision`)
    with D-4 `cancellation_request_id` cycle forwarding, `ApiError.code` handling, and `O-1 = A`
    `DENY` prior-status (`APPROVED`/`ASSIGNED`) verification
    ([release note](../release-notes/android-s2-cancellation-decisions.md)).

Source acceptance & integration CI status (NOT merged, deployed, built, distributed, or device-accepted):
- **Source accepted after independent review & 5/5 green GitHub CI in Draft PR #78 (`2ef5a1f43b256189860a9c5f97d87e274c338211`):**
  `#75` (`b91e8cc`), `#76` (`2d69045`), `#71` (`ccf2d84`), `#72` (`56174ce`), `#73` (`6f1c60a`),
  `#77` (`16471f8`), `#46` (`06ee9d6`), `#67` (`d60b1b2`), `#68` (`257e045`), `#69` (`e4040ef`),
  and `#78` (`2ef5a1f`).
- *(B5-B update 2026-11-13: all of the above, plus the B4/B4.1 docs (`77e8ec8`), are now
  **MERGED to `main` at `cac3cd6a82220353c1d48599b484368f78251033`** — still NOT deployed, built,
  distributed, or device-accepted. See §4.2.)*

Initial B4 pending owner product & release decisions (preserved from initial 2026-11-12 B4 snapshot — see **B4.1 Owner Planning Decision Update** immediately below):
1. **Legacy Multi-Day Calendar Event Format (`LEGACY_MULTIDAY_CALENDAR_DECISION=PENDING` at initial B4 snapshot; updated to `OPTION_3A_SELECTED` in B4.1 below):**
   In PR #75/#78, `job_handler.py` (`_legacy_parent_visit_window`) copies a valid parent
   `visit_window` (`MORNING`, `MIDDAY`, `AFTERNOON`, `EVENING`, `ANYTIME`) onto legacy
   (non-canonical) multi-day child `JOB` records without persisting `start_time`. When
   `job_handler.py` calls `sync_calendar_event(item)` in `common/google_calendar.py`:
   - **Option 3A — Estimated Start-Time Timed Events (Current PR #78 Code):** `google_calendar.py`
     maps `MORNING`/`MIDDAY`/`AFTERNOON`/`EVENING` via `WINDOW_START_HOURS` (`08:00`, `11:00`,
     `14:00`, `17:00` `America/New_York`) into timed Calendar events (`start.dateTime` /
     `end.dateTime`) with note `⏰ Estimated from booking window`, matching single-day legacy
     bookings. Zero code change needed.
   - **Option 3B — Label-Only All-Day Events:** Keep legacy multi-day child Calendar events as
     all-day banners (`start.date` / `end.date`) while displaying the inherited window label in the
     event summary/description (`🐾 <Pet> — <Service> (Morning)`). Requires a bounded code + test
     update in `src/backend/common/google_calendar.py` before `job` Lambda deployment.
2. **W1 & Accumulated `main` Backend Release Scope (`W1_PRODUCTION_RELEASE_AUTHORIZED=NO`):**
   Whether a future approved backend release will (a) converge the operational Lambdas with
   `main` + PR #78 (requiring explicit authorization to activate Workstream 1 `pet_ids` and Ryan
   Slice `W1` `WALK_20MIN` / `CHECK_IN` / `OVERNIGHT`), or (b) use a curated backend RC targeting
   only `cancellation`, `review`, and `admin` Lambdas while keeping W1 dormant.
3. **Merge Strategy & Gate C3c Authorization (`MERGE_AUTHORIZATION=NOT_ISSUED`):**
   **Proposed Consolidated Merge Strategy (proposal only, NOT merge authorization):** Merge the
   verified full-stack candidate (PR #78 `2ef5a1f43b256189860a9c5f97d87e274c338211`, or this
   stacked B4 branch which adds only reconciled documentation on top of `#78`) in a single
   Gate C3c-authorized operation rather than 8+ sequential merges, then close superseded component
   Draft PRs with pointers to the merged SHA. No PR may be marked Ready or merged without Matthew's
   explicit structured `MERGE AUTHORIZATION` block.

### 4.1 B4.1 Owner Planning Decision Update (2026-11-13)

Following review of the initial B4 snapshot above, Matthew recorded the following planning decisions (preserving the initial B4 pending-decision text above as history):

1. **Consolidated PR #78 Integration Strategy APPROVED; `MERGE AUTHORIZATION` NOT ISSUED (`CONSOLIDATED_PR78_INTEGRATION_STRATEGY=APPROVED`; `MERGE_AUTHORIZATION=NOT_ISSUED`):**
   - Matthew approves the **consolidated integration strategy** for PR `#78` (`2ef5a1f43b256189860a9c5f97d87e274c338211`) plus the reconciled B4/B4.1 documentation.
   - **`MERGE AUTHORIZATION` is NOT ISSUED.** No PR (`#78`, `#79`, or any constituent PR) may be marked Ready for Review or merged until Matthew relays an explicit structured Gate C3c `MERGE AUTHORIZATION` block naming the target PR and immutable head SHA.
2. **Calendar Option 3A SELECTED (`LEGACY_MULTIDAY_CALENDAR_DECISION=OPTION_3A_SELECTED`):**
   - Retain current estimated-start-time behavior (`WINDOW_START_HOURS` in `src/backend/common/google_calendar.py`: `08:00`, `11:00`, `14:00`, `17:00` `America/New_York` with note `⏰ Estimated from booking window`), without any new Calendar code change.
3. **Full Pilot Convergence Chosen for PLANNING ONLY (`PILOT_CONVERGENCE_PLANNING_SCOPE=FULL_CONVERGENCE_PLANNING_ONLY`):**
   - Release planning targets full pilot convergence across backend, web, and Android rather than a cancellation-only slice, for **planning only** (not deployment or W1 execution authorization).
4. **`W1_PRODUCTION_RELEASE_AUTHORIZED=NO` Remains UNCHANGED:**
   - Both **Workstream 1 (`W1`) canonical existing-pet association (`pet_ids`, PR #26 `429f3b9`)** and **Ryan Slice `W1` 20-Minute Walk (`WALK_20MIN`, `c51828e`)** remain **NOT AUTHORIZED** for production deployment (`W1_PRODUCTION_RELEASE_AUTHORIZED=NO`; `W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES`).
5. **All Execution & Production Gates Remain NOT AUTHORIZED:**
   - AWS/Terraform/D-2 inventory, backend/web deployment, Android builds/distribution, Ryan testing, tenant changes, and Stripe live remain **NOT AUTHORIZED**.

### 4.2 B5 Gate C3c Merge Authorization — Issued & Executed (2026-11-13)

Item 1 of §4.1 (`MERGE_AUTHORIZATION=NOT_ISSUED`) is preserved above as the B4.1 state; it was
**updated to `MERGE_AUTHORIZATION=ISSUED_AND_EXECUTED` for PR #78 only**:

- **Authorization (relayed by Matthew, 2026-11-13, America/New_York):** repository
  `mattnicomn/togs_and_dogs_website`; PR #78; head `77e8ec8fbefe92134b829ebc9533c516af0f6262`;
  target `main`; method `squash`; `delete_branch_after: no`; restrictions: integration only, scope =
  exactly the approved 89-file diff; NOT deployment / AWS / Terraform / W1 activation / Stripe live /
  tenant changes / production testing / Ryan testing / mobile builds or distribution.
- **B5-A (separately approved):** single non-force fast-forward of
  `integration/b2c-full-stack-verification` `2ef5a1f` → `77e8ec8` (adds only the 12 B4/B4.1 docs
  files; runtime byte-identical). CI run `43463005295` on `77e8ec8`: 5/5 `SUCCESS`.
- **B5-B pre-merge checklist (`guardrails.md` items 1–10):** all PASS — repository, OPEN/Draft/base
  `main`, exact head SHA, 89-file scope (no infra/secrets/tfvars/tfplan), 5/5 checks (none required
  by ruleset), MERGEABLE/CLEAN, `main` unchanged at `8fe7fa7` since approval, author-only review
  recorded (no independent human GitHub review), no blockers, clean worktree.
- **Execution:** Draft → Ready, immediate re-check, then GitHub PR merge API (`squash`, expected
  head `sha` precondition) — **merged 2026-11-13T17:50:52Z as
  `cac3cd6a82220353c1d48599b484368f78251033`** (single parent `8fe7fa7`; tree
  `f875c2c1583eba400a20ba3733f2e1c922077e90` identical to the approved head; 89 files,
  +11,872 / −727). Source branches retained.
- **Post-merge:** no CI run on `main` (workflow is `pull_request`-only); no deployment,
  infrastructure, AWS or Terraform action occurred.
- **Scope of this authorization is consumed.** No other PR is authorized for Ready or merge.

Not approved / blocked (`NOT AUTHORIZED`):
- **D-2 production cancellation inventory:** `NOT AUTHORIZED`. No production reads or writes.
- **AWS / Terraform checks:** `NOT AUTHORIZED`. No live AWS CLI queries or `terraform plan`/`apply`.
- **Merge or Ready conversion of any PR:** `NOT AUTHORIZED`. *(B5-B: the PR #78-only authorization
  in §4.2 was issued and consumed; no other PR — including the §15 closure candidates and #45 — is
  authorized for Ready, merge, or closure.)*
- **Production deployment (backend Lambdas or web S3/CloudFront):** `NOT AUTHORIZED`.
- **Mobile EAS build, Play Internal Testing upload, TestFlight, or Ryan testing:** `NOT AUTHORIZED`.
- **Production test data, tenant changes, tenant-resolution mode change, or Stripe live:** `NOT AUTHORIZED`.

Gate owners: Matthew for every merge, deploy, build, distribution, production data, tenant, Stripe
and Ryan action. ChatGPT reviews. Kiro/AG execute only approved, bounded scope.

---

## 5. December 11 assessment: AT RISK — RECOVERING

**B5 update (2026-11-13):** The repository-level integration blocker is resolved — PR #78 is
**merged to `main` at `cac3cd6a82220353c1d48599b484368f78251033`** (§4.2). The pilot remains
**AT RISK** because nothing on the critical path is yet deployed to AWS, built via EAS,
distributed to Play Internal Testing, or accepted on a device. Current remaining blockers, in
dependency order:

1. **Pre-deploy verification & D-2 inventory (B6, `NOT AUTHORIZED`).**
2. **W1 / backend release-scope decision (`W1_PRODUCTION_RELEASE_AUTHORIZED=NO`;
   `W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES`)** — full convergence is chosen for planning only;
   any curated vs. converged backend release needs explicit owner authorization.
3. **Coordinated backend → web deployment + bounded acceptance (B7, `NOT AUTHORIZED`).**
4. **Android EAS build, Play Internal distribution, device acceptance and Ryan testing (B8,
   `NOT AUTHORIZED`).**

The text below is the preserved B4.1 assessment (pre-merge); item 1(a) there is superseded by §4.2.

 Batches B1-A (#75), B1-B (#76), B2-A (#77), B2-B (Android source audit), and B2-C (#78) resolved the
two repository-level blockers from the initial checkpoint (the red CI baseline on `main` and the
unreviewed/un-CI-verified stacked Android PRs), producing **Draft PR #78 (`2ef5a1f43b256189860a9c5f97d87e274c338211`)**
with **5/5 green GitHub Actions CI checks**. However, **no item on the critical path has yet been
merged to `main`, deployed to AWS, built via EAS, distributed to Play Internal Testing, or
accepted on a device.** Remaining blockers to December 11 GO:

1. **Owner decisions & authorizations (§4 / §4.1):** (a) Consolidated PR `#78` integration strategy is **APPROVED**, while Gate C3c **`MERGE AUTHORIZATION` is NOT ISSUED**; (b) Full pilot convergence is chosen for **PLANNING ONLY**, while **`W1_PRODUCTION_RELEASE_AUTHORIZED=NO` remains unchanged** for both Workstream 1 `pet_ids` and Ryan Slice `W1` `WALK_20MIN` deployment; and (c) Legacy multi-day Calendar event format **Option 3A is SELECTED** (`LEGACY_MULTIDAY_CALENDAR_DECISION=OPTION_3A_SELECTED`: retain current `WINDOW_START_HOURS` behavior in `google_calendar.py` with no new Calendar code change).
2. **Pre-deploy verification & D-2 inventory (`NOT AUTHORIZED`):** Read-only AWS Lambda hash check,
   D-2 query for any legacy `CANCELLATION_REQUESTED` records lacking `cancellation_request_id` /
   `cancellation_prior_status`, and targeted read-only `terraform plan`.
3. **Coordinated Backend → Web → Mobile release sequencing (`NOT AUTHORIZED`):** `BE-CANCEL-1`
   (`cancellation` + `review` Lambdas) and `D-1` (`admin` Lambda) must deploy and pass contract
   verification before `WEB-CANCEL-1` (`#72` web) and Android `S2` (`#69` mobile) are used.
4. **Android build, distribution & device acceptance (`NOT AUTHORIZED`):** EAS build (`versionCode 5`+),
   Play Internal Testing upload, physical device/emulator acceptance, and separate Ryan testing gate.

**NOT FEASIBLE** if App Store publication, Stripe live, a second customer tenant, or SaaS maturity
items are pulled into December 11 pilot scope.

---

## 6. Release board (Android / web / backend pilot scope)

State key: `DEP` = deployed · `MRG` = **merged to `main` at `cac3cd6` via PR #78 squash (2026-11-13),
NOT deployed / built / distributed** · `SRC-ACC` = source accepted & 5/5 CI green in PR #78 (NOT
merged or released; historical state of rows 1–9 at the 2026-11-12 / B4.1 snapshot) · `IMPL` =
implemented on `main`, not deployed · `NOT` = not implemented / not executed · `UNK` = unknown.

*(Board updated 2026-11-13 in B5-C1. At the 2026-11-12 / B4.1 snapshot, rows 1–9 were `SRC-ACC`
in Draft PR #78 `2ef5a1f`, and each row's first remaining action was "Merge" / Gate C3c
`MERGE AUTHORIZATION`; that step is now complete and has been removed from the remaining-action
column.)*

| # | Feature (user value) | State | PR / SHA / deps | Remaining action → acceptance check | Blocks | Gate / owner | Pri |
|---|---|---|---|---|---|---|---|
| 1 | Green CI baseline & full-stack source integration | `MRG` | #75 `b91e8cc`, #76 `2d69045`, #77 `16471f8`, #78 head `77e8ec8` (run `43463005295` 5/5 `SUCCESS`) → **`main` `cac3cd6`** | ✅ Merged (B5-B). Next: B6 read-only pre-deploy verification (no CI runs on `main`; workflow is `pull_request`-only) | Android + web | Matthew (B6 approval) | P0 |
| 2 | Android booking continuation + exact visit access + per-child draft notes | `MRG` | #46 `06ee9d6` (in `cac3cd6`) | EAS build → device check of M&G approval & child-visit selection | Android | Matthew (build) | P0 |
| 3 | Android owner/admin `DRAFT` quote create/edit/send + S1-R1 hydration | `MRG` | #67 `d60b1b2` (in `cac3cd6`) | EAS build → emulator/device run (`DRAFT → SENT`) | Android | Matthew (build) | P0 |
| 4 | Android `owner/admin/staff` visit Start/Complete (`const canExecuteVisits` in `RequestDetailScreen.tsx`) | `MRG` | #68 `257e045` (in `cac3cd6`) | EAS build → device check against `/admin/job/start` & `/complete` | Android | Matthew (build) | P0 |
| 5 | Android owner/admin cancellation decisions + D-4 BE-CANCEL-1 compatibility (`cancellation_request_id`, `ApiError.code`, `O-1 = A` `DENY` restores `APPROVED`/`ASSIGNED`) | `MRG` | #69 `e4040ef` (in `cac3cd6`); depends on #71 deployed | Deploy #71 backend first → EAS build → device acceptance | Android | Matthew (deploy/build) | P0 |
| 6 | Server-safe cancellation decisions (`PUT /admin/cancel/decision`, exact literals, atomic gate, cycle id, `require_existing=True`, `/admin/review` guard) | `MRG` | #71 `ccf2d84` (in `cac3cd6`) | D-2 inventory check → targeted `cancellation`+`review` Lambda deploy → bounded contract check | Android + web | Matthew (D-2/deploy) | P0 |
| 7 | Web explicit Approve/Deny cancellation modal (removes `Cancel = DENY` bug; sends `cancellation_request_id`) | `MRG` | #72 `56174ce` (in `cac3cd6`); depends on #71 deployed | Deploy after #71 backend verified → admin smoke | Web | Matthew (deploy) | P0 |
| 8 | Client portal "cancellation declined" marker (`cancellation_denied`, `cancellation_denied_at`) | `MRG` | #73 `6f1c60a` (in `cac3cd6`); depends on #71 deployed | Deploy `admin` Lambda projection then web → client smoke | Web | Matthew (deploy) | P1 |
| 9 | R7E legacy multi-day child `visit_window` inheritance + Calendar Option 3A (`WINDOW_START_HOURS` in `google_calendar.py`) | `MRG` | #75 `b91e8cc` (in `cac3cd6`) | **Option 3A SELECTED (B4.1):** retain current `WINDOW_START_HOURS` behavior (no code change) → `job` Lambda deploy gate | Backend (`job` Lambda) | Matthew (deploy) | P1 |
| 10 | Accumulated merged-not-deployed scheduling/workflow (A–C, C1, Ryan W1 Walk `WALK_20MIN`, O1 Overnight, E1, E2, W4 Option A, Workstream 1 `pet_ids`) | `IMPL` (merged on `main`) | on `main` since `8fe7fa7` (now within `cac3cd6`) | **Full convergence chosen for PLANNING ONLY (B4.1):** **`W1_PRODUCTION_RELEASE_AUTHORIZED=NO` unchanged**; requires explicit W1 & backend deployment authorization | Android + web | Matthew (W1 & deploy gate) | P0 |
| 11 | Android EAS build + Play internal distribution | `NOT` (for new code) | last build `vc4` `bf9f80d` | After backend deploy: approved EAS build → Play internal → device acceptance | Android | Matthew (EAS, Play, Ryan) | P0 |
| 12 | Web deployment of `main` + cancellation web (#72/#73/#76) | `NOT` | last web deploy W2C 2026-10-08 (`7c1a8f1`) | Build from approved RC → S3/CloudFront deploy → authenticated smoke | Web | Matthew (deploy) | P0 |
| 13 | Mobile cancellation marker for clients | `NOT` (deferred by D-1) | — | Post-pilot | — | Matthew | P2 |
| 14 | Branded password-reset email (Cognito → Postmark) | `IMPL` (deferred in `infra/deferred/`) | see `current-state.md` | Separate approved release | Neither (generic email works) | Matthew | P1 |
| 15 | Archive/delete/purge of pending cancellations | `UNK` | noted in #71/#72 | Verify behaviour before pilot | Web | — | P1 |
| 16 | Web Request List / Visit Requests queue correction; client onboarding completion | `NOT` | backlog items 16–17 | Post-pilot unless owner promotes | Web | Matthew | P1 |
| 17 | Multi-tenant SaaS maturity (PTM-0..13, F02), Stripe live, subscription billing, App Store publication | `NOT` / blocked | backlog | Out of December 11 scope | SaaS only | Matthew | P2 |

---

## 7. Critical path (dependency order)

Each batch is bounded, ends at a Draft/evidence stop, and needs its own owner approval.

1. ✅ **B1-A (#75) & B1-B (#76) — Completed (Draft PRs):** Backend pytest (`2,474 passed / 0 failed`)
   and Web ESLint (`0 errors / 6 warnings`) remediated; `PlatformTenantDetail.jsx` stale-response
   race fixed.
2. ✅ **B2-A (#77), B2-B & B2-C (#78) — Completed (Draft PRs & Audit):** Combined backend/web PR #77
   (`16471f8`, 61 files, 5/5 CI green), independent read-only audit of Android PRs #46/#67/#68/#69
   (`ACCEPTABLE`), and full-stack Draft PR #78 (`2ef5a1f`, 86 files, 5/5 CI green).
3. ✅ **B3 — Completed (Read-Only Assessment):** Evaluated PR #78 merge scope, undeployed `main`
   inventory, distinct W1 concepts, Calendar Option 3A vs 3B decision, release compatibility,
   predeploy manifest, and documentation consistency.
4. ✅ **B4 / B4.1 — Documentation and Release-Gate Reconciliation (Current Batch — PR #79):** Reconciles
   continuity, backlog, release-note navigation, supersession notes, code-reference attribution
   (`const canExecuteVisits` in `mobile/src/screens/RequestDetailScreen.tsx`), live CI workflow run
   IDs (`43349187490` for `#76`, `43355736742` for `#77`, `43359979814` for `#78`), owner planning
   decisions (§4.1), and this December 11 checkpoint in documentation-only **Draft PR #79** stacked
   on `#78`. Stops for ChatGPT review.
5. ✅ **B5 — Consolidated Integration Execution (Gate C3c — `MERGE_AUTHORIZATION=NOT_ISSUED` at
   B4.1; updated to `ISSUED_AND_EXECUTED` for PR #78 on 2026-11-13):**
   Consolidated PR `#78` integration strategy is **APPROVED**, Calendar **Option 3A** is **SELECTED**
   (no code change), and full pilot convergence is selected for **PLANNING ONLY** (with
   `W1_PRODUCTION_RELEASE_AUTHORIZED=NO` unchanged). Execution of the consolidated integration into
   `main` awaits Matthew's explicit structured Gate C3c `MERGE AUTHORIZATION` block. *(Completed:
   B5-A non-force fast-forward `2ef5a1f` → `77e8ec8`; B5-B Ready + squash merge →
   `main` `cac3cd6a82220353c1d48599b484368f78251033`; B5-C read-only superseded-PR audit (§15);
   B5-C1 this post-merge documentation reconciliation. See §4.2.)*
6. ⏳ **B6 — Authorized Read-Only Pre-Deploy Verification & Plan (`NOT AUTHORIZED`):** Verify live AWS Lambda
   `CodeSha256` hashes and API Gateway `n40vai`, run read-only D-2 pending-cancellation inventory,
   capture rollback artifacts, and run a targeted read-only `terraform plan`.
7. ⏳ **B7 — Authorized Backend & Web Deployment + Bounded Acceptance (`NOT AUTHORIZED`):** Requires
   explicit owner deployment authorization (and explicit `W1_PRODUCTION_RELEASE_AUTHORIZED=YES` if
   W1 Lambdas `intake`/`job` are included). Deploy approved backend Lambdas first, verify production
   cancellation/projection contract, then deploy Web to S3/CloudFront and run authenticated smoke checks.
8. ⏳ **B8 — Authorized Android Build, Play Internal Distribution & Device Acceptance (`NOT AUTHORIZED`):** Run
   approved EAS Android build (`versionCode 5`+), upload to Play Internal Testing, complete
   emulator/physical device acceptance, and separately gate Ryan pilot testing.

---

## 8. Current batch and next action

- **Current batch (2026-11-13, B6-C1):** **Production Baseline Documentation Reconciliation** on a
  single documentation-only Draft PR (branch `docs/b6c1-production-baseline-reconciliation` from
  `main` `61e84d9649d016f462a4f436f8ec266b83e2d2de`; exactly 4 files: `current-state.md`, this
  checkpoint, `master-handoff-prompt.md`, and a limited factual note on `guardrails.md` O1 status).
  It records the read-only B6-B1 verification (§16). **STOP FOR CHATGPT REVIEW.**
- **Next recommended actions after review (each separately owner-gated; none authorized today):**
  1. Gate C3c `MERGE AUTHORIZATION` for the B6-C1 docs Draft PR.
  2. Owner decision on the W1 gate wording given Ryan Slice W1 Walk `BACKEND_CODE_DEPLOYED` (§3).
  3. Owner decision on the release option (B6-A2: recommended Option A — `cancellation` + `review` +
     `admin` from `main` plus a curated web build), R7E inclusion, AC-9 exclusion and W4 Option A
     web ride-along.
  4. Curated web candidate: off-by-default existing-pet flag in `web/src/components/IntakeForm.jsx`
     (and later `mobile/src/screens/IntakeScreen.tsx`) so no client `pet_ids` reach the pre-W1
     intake; code PR + CI + separate merge authorization.
  5. **B6-B2** (`NOT AUTHORIZED`): D-2 read-only legacy pending-cancellation inventory; `admin`
     `GlA3mUtq…` rollback capture (two hash-verified copies); web bucket versioning check and
     11-object pre-deploy snapshot; offline candidate hash of the `main` build; saved
     `terraform plan -target` for `cancellation`/`review`/`admin` expecting `0/3/0`.
  6. **B7 / B8** (`NOT AUTHORIZED`): backend → web deploy, then Android build/distribution/device
     acceptance and separate Ryan testing.

*(Previous §8 content for B5-C1, preserved:)*

- **Current batch (2026-11-13):** **B5-C1 — Post-Merge Documentation Reconciliation** on a single
  documentation-only Draft PR (branch `docs/b5c-post-merge-reconciliation` from `main`
  `cac3cd6a82220353c1d48599b484368f78251033`; exactly 4 files: `current-state.md`, this checkpoint,
  `document-map.md`, `docs/release-notes/index.md`).
- **Stopping condition:** Draft PR open, not Ready, not merged; **STOP FOR CHATGPT REVIEW**.
- **Next recommended actions after ChatGPT review (each separately owner-gated):**
  1. **Docs PR integration:** a separate structured Gate C3c `MERGE AUTHORIZATION` for this B5-C1
     docs Draft PR (no authorization exists today).
  2. **Superseded PR closure:** separate Matthew approval to close the §15 closure candidates with
     pointer comments to `cac3cd6` (branches retained); separate policy decision on #45.
  3. **B6-A — Offline release manifest (no AWS / no Terraform):** from `main` `cac3cd6`, reproduce the
     expected backend archive / `source_code_hash` offline, map which of the 13 Lambdas change
     behaviour vs. the recorded deployed hashes (flagging W1 activation per Lambda), and draft
     curated (`cancellation`/`review`/`admin`) vs. full-convergence deploy options with ordering and
     rollback capture. Docs-only Draft PR stop.
  4. **B6-B — Read-only AWS pre-deploy verification (`NOT AUTHORIZED`):** live Lambda/API hash check,
     D-2 legacy pending-cancellation inventory, rollback capture, targeted read-only `terraform plan`.
  5. **B7 / B8 (`NOT AUTHORIZED`):** keep `W1_PRODUCTION_RELEASE_AUTHORIZED=NO` until Matthew
     explicitly authorizes; backend → web deploy, then Android build/distribution/device acceptance.

*(Previous §8 content, preserved as the B4.1 record:)*

- **Current batch:** **B4.1 — Final Documentation Accuracy Correction** on **Draft PR #79** (branch
  `docs/b4-release-gate-reconciliation`, stacked on verified Draft PR #78
  `2ef5a1f43b256189860a9c5f97d87e274c338211`).
- **Stopping condition:** Draft PR #79 updated with bounded B4.1 corrections (12 documentation files
  only vs. PR #78); **STOP FOR CHATGPT REVIEW** before the AG-to-Kiro integration handoff.
- **Next recommended action after ChatGPT review:**
  1. **Consolidated Integration Gate (Gate C3c):** Matthew issues an explicit structured Gate C3c
     `MERGE AUTHORIZATION` block for the chosen consolidated integration vehicle (either fast-forwarding
     PR `#78` to include the verified B4.1 docs commit so PR `#78` merges code + docs in one 5/5
     CI-verified PR, or retargeting PR `#79` to `main` and waiting for 5/5 CI before merging `#79`;
     currently **`MERGE_AUTHORIZATION=NOT_ISSUED`**).
  2. **Read-Only Pre-Deploy Verification (`B6`):** Separate explicit owner authorization for
     read-only AWS Lambda/API verification, D-2 legacy pending-cancellation inventory, and targeted
     `terraform plan` (`NOT AUTHORIZED` today).
  3. **W1 & Production Release Gates (`B7`/`B8`):** Keep `W1_PRODUCTION_RELEASE_AUTHORIZED=NO`
     until Matthew explicitly authorizes production deployment of Workstream 1 `pet_ids` and Ryan
     Slice `W1` `WALK_20MIN`.

---

## 9. Known baseline failures on `origin/main` (`8fe7fa7`) vs. PR #78 (`2ef5a1f`) remediation

*(B5-B update 2026-11-13: these remediations are now on `main` at `cac3cd6`. The `8fe7fa7` column
is historical. Final pre-merge CI evidence is run `43463005295` on `77e8ec8` (5/5 `SUCCESS`); the
job IDs below are from the earlier `2ef5a1f` run `43359979814`. No CI runs on `main` itself because
`ci.yml` triggers on `pull_request` only.)*

| Area | `origin/main` (`8fe7fa7`) Baseline | Status in PR #78 (`2ef5a1f`) & B4 |
|---|---|---|
| Backend CI (`pytest tests/backend`) | 74 failed / 2,067 passed (run `40735985571`) | **RESOLVED in #75/#77/#78:** `2,474 passed / 0 failed` (CI job `131670898725` `SUCCESS`) |
| Web ESLint (`npm run lint`) | 54 errors / 9 warnings (63 problems) | **RESOLVED in #76/#77/#78:** `0 errors / 6 warnings` (CI job `131670898715` `SUCCESS`) |
| Web tests & Vite build | Skipped on `main` after lint failed; `AdminDashboardWorkflowActions` timing flake | **RESOLVED in #72/#76/#77/#78:** Node 24/24, Vitest 36 suites / 566 passed, Vite build `SUCCESS` |
| Mobile (`tsc` + `jest --ci`) | 35 suites / 321 tests at #46 | **VERIFIED in #78:** `tsc` 0 errors; 43 suites / 608 passed (CI job `131670898457` `SUCCESS`) |
| Shared contract validators | 4 validator scripts | **VERIFIED in #78:** 4/4 validators pass (CI job `131670898759` `SUCCESS`) |
| Local vs CI Python/moto env | Local Python 3.13 / moto 5.0.0 vs CI Python 3.12 / moto 5.1.4 | Verified passing in both local worktree and GitHub Actions Ubuntu Python 3.12 runner |

---

## 10. Kiro shell reliability and fallback

On this Windows workstation the Kiro cmd channel stalls intermittently (output arrives late or not
at all; exit codes always report -1).

- Write every command's output to a file under `%TEMP%` and read the file. Run scripts with
  `call <absolute .cmd>`; never write and run a script in the same batch.
- Put every irreversible step (commit, push, PR create) in one script with a lock file and
  re-verification of base/branch/HEAD and `gh pr list --head` before acting.
- After about two failed probes, stop. Report BLOCKED with exactly what is unverified, and either
  ask Matthew to restart Kiro or hand over the exact commands to run in a separate PowerShell
  window. Re-read expected out-files after recovery; never re-issue a possibly executed step.

---

## 11. Cross-session startup checklist

1. Read [`README.md`](README.md), [`current-state.md`](current-state.md),
   [`guardrails.md`](guardrails.md) (full), [`master-handoff-prompt.md`](master-handoff-prompt.md),
   [`document-map.md`](document-map.md), the
   [SaaS backlog](../backlog/saas-maturity-and-multi-business-owner-readiness.md),
   [release-notes index](../release-notes/index.md), then this file.
2. `git fetch`; record `origin/main`, branch, worktree status, stash list.
3. `gh pr view` each PR in §2; compare heads with this file; report any drift before acting.
4. State: latest production milestone, current batch, next action, gates.
5. Confirm the owner's latest approval text and its exact scope. Infer nothing beyond it.

---

## 12. Stale-document flags reconciled in B4 vs. remaining external PR descriptions

- **Reconciled in B4 documentation:**
  - `current-state.md` now records the 2026-11-12 full-stack candidate (PR #78), preserves the
    2026-10-29 #46 entry with an explicit supersession note for #67/#68/#69, and clarifies that the
    2026-10-27 deployment paragraph's `FUNCTIONAL_ACCEPTANCE=PENDING` was completed later that day
    by `W3C2_FUNCTIONAL_ACCEPTANCE=COMPLETE`.
  - `document-map.md` and `docs/release-notes/index.md` now index `#67` (`android-s1-admin-quote-editor.md`),
    `#69` (`android-s2-cancellation-decisions.md`, including `#68` visit RBAC context), `#71`
    (`be-cancel-1-cancellation-decision-safety.md`), `#73` (`d1-client-denial-marker.md`), W3-C2,
    W3-C1, W3-B, PR #22, PR #19, and this checkpoint file.
  - Standalone release notes (`android-booking-workflow-remediation.md`,
    `android-s1-admin-quote-editor.md`, `android-s2-cancellation-decisions.md`,
    `be-cancel-1-cancellation-decision-safety.md`, `d1-client-denial-marker.md`) now carry explicit
    2026-11-12 supersession/integration notes without altering their historical text.
- **Remaining in external GitHub PR metadata (untouched by B4):**
  - `master-handoff-prompt.md` "CURRENT STATE SUMMARY" body retains its historical pre-W3-C2 text,
    while its `FIRST:` reading list now directs every agent to `current-state.md` and this active
    checkpoint file.
  - Standalone PR #72 description still contains the literal `WEB_RESULTS_PLACEHOLDER` under
    "Tested", and standalone PR #69 description text predates its D-4 commit `e4040ef`. Both
    branches are superseded by full-stack Draft PR #78 (`2ef5a1f43b256189860a9c5f97d87e274c338211`).

---

## 13. RESUME BLOCK (Active — B6-C1 Production Baseline Documentation Reconciliation)

- **Timestamp:** 2026-11-13
- **`origin/main`:** `61e84d9649d016f462a4f436f8ec266b83e2d2de` (PR #80 docs on top of PR #78
  squash `cac3cd6a82220353c1d48599b484368f78251033`). Re-verify live before acting.
- **Integration status:** `FULL_STACK_PR78_MERGED_TO_MAIN_NOT_DEPLOYED` (unchanged).
- **Production baseline:** `PRODUCTION_BASELINE_VERIFIED_READ_ONLY` (B6-B1, §16) — `admin`
  `GlA3mUtq…`; other 12 `W6cqyudl…`; `$LATEST` only, no aliases; API `n40vai`; IAM `v3`; Web W2C
  `7c1a8f1` at `toganddogs.usmissionhero.com`.
- **Ryan slices:** O1, E3A child start, W1 Walk and R1 = `BACKEND_CODE_DEPLOYED` (not
  runtime-accepted, not Ryan-tested). Workstream 1 `pet_ids` = NOT DEPLOYED.
- **Current batch / branch:** B6-C1 docs-only Draft PR, branch
  `docs/b6c1-production-baseline-reconciliation` (worktree `%TEMP%\togs-b6c1`).
- **Gates (unchanged):** `W1_PRODUCTION_RELEASE_AUTHORIZED=NO`;
  `W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES`; D-2, AWS writes, Terraform, deployment, Android
  builds/distribution, Ryan testing, tenant changes and Stripe live NOT AUTHORIZED.
- **Open owner decisions:** W1 gate wording; release option A/B/C; R7E; AC-9; W4 Option A web
  ride-along; mobile `pet_ids` flag before B8; §14/§15 superseded-PR closures; #45 policy.
- **December 11 assessment:** **AT RISK — RECOVERING** (§5).
- **Next action:** STOP FOR CHATGPT REVIEW of the B6-C1 docs Draft PR; then §8.

---

### 13.0 Historical Resume Block (B5-C1 Post-Merge Documentation Reconciliation) — preserved; superseded by §13 on 2026-11-13

- **Timestamp:** 2026-11-13
- **`origin/main`:** `cac3cd6a82220353c1d48599b484368f78251033` (PR #78 squash merge; parent
  `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`; tree `f875c2c1583eba400a20ba3733f2e1c922077e90`
  == approved head `77e8ec8fbefe92134b829ebc9533c516af0f6262` tree). Re-verify live before acting.
- **Integration status:** `FULL_STACK_PR78_MERGED_TO_MAIN_NOT_DEPLOYED` — 89 files (backend
  BE-CANCEL-1 / D-1 / R7E + test isolation, web B1-B / WEB-CANCEL-1 / D-1, Android #46/#67/#68/#69,
  B4/B4.1 docs). Approved CI run `43463005295` 5/5 `SUCCESS`. No CI on `main` (pull_request-only).
- **Merge authorization:** `MERGE_AUTHORIZATION=ISSUED_AND_EXECUTED` for PR #78 only (§4.2);
  consumed. No other PR authorized for Ready/merge/closure.
- **Current batch / branch:** B5-C1 docs-only Draft PR, branch `docs/b5c-post-merge-reconciliation`
  (worktree `%TEMP%\togs-b5c`), 4 files: `docs/project-continuity/current-state.md`,
  `docs/project-continuity/december-11-delivery-checkpoint.md`,
  `docs/project-continuity/document-map.md`, `docs/release-notes/index.md`.
- **Owner decisions in force:** `CONSOLIDATED_PR78_INTEGRATION_STRATEGY=APPROVED` (executed);
  `LEGACY_MULTIDAY_CALENDAR_DECISION=OPTION_3A_SELECTED`;
  `PILOT_CONVERGENCE_PLANNING_SCOPE=FULL_CONVERGENCE_PLANNING_ONLY`.
- **Production state (recorded, not re-verified against AWS):** unchanged since 2026-10-27 —
  `admin` `GlA3mUtq…`, other 12 Lambdas `W6cqyudl…`, API stage `n40vai`, Web `7c1a8f1`, Android
  `vc4` / iOS `(6)` from `bf9f80d`. Latest completed production milestone remains
  `W3C2_FUNCTIONAL_ACCEPTANCE=COMPLETE` (2026-10-27).
- **Explicitly unchanged / NOT AUTHORIZED gates:** `W1_PRODUCTION_RELEASE_AUTHORIZED=NO`;
  `W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES` (an untargeted apply would now also ship all merged PR #78
  backend scope); D-2 production inventory; AWS reads/writes; `terraform plan`/`apply`;
  backend/web deployment; Android EAS build; Play/TestFlight distribution; Ryan testing; tenant
  changes; Stripe live — all **NOT AUTHORIZED**.
- **Open PRs:** §15 closure candidates (#75, #76, #77, #71, #72, #73, #46, #67, #68, #69, #74, #62,
  #43) remain OPEN/Draft pending separate approval; #45 pending owner policy decision.
- **December 11 assessment:** **AT RISK — RECOVERING** (§5).
- **Next action:** STOP FOR CHATGPT REVIEW of the B5-C1 docs Draft PR; then the separately gated
  options in §8.

---

### 13.1 Historical Resume Block (B4.1 Final Documentation Accuracy & Owner Planning Decision Reconciliation) — preserved; superseded by §13 on 2026-11-13

- **Timestamp:** 2026-11-13
- **`origin/main`:** `8fe7fa78ad707ac67a05d29059d2771a9aa256c8` (unchanged)
- **Source-Accepted Base PR:** Draft PR #78 (`2ef5a1f43b256189860a9c5f97d87e274c338211`, 86 changed
  files vs `main`, 5/5 GitHub CI checks `SUCCESS` in run `43359979814`, untouched and preserved)
- **Current Batch / Branch / PR:** B4.1 Final Documentation Accuracy Correction on **Draft PR #79**,
  branch `docs/b4-release-gate-reconciliation` (worktree `%TEMP%\togs-b4`, initial B4 commit
  `7dd395bdbb1f46bccc2889a2ea26556ef2a2be56` followed by B4.1 accuracy commit), stacked directly on
  PR #78 (`2ef5a1f43b256189860a9c5f97d87e274c338211`)
- **Documentation Files Changed vs. PR #78 (12 files, docs-only):**
  `docs/project-continuity/README.md`, `docs/project-continuity/master-handoff-prompt.md`,
  `docs/project-continuity/document-map.md`, `docs/project-continuity/current-state.md`,
  `docs/project-continuity/december-11-delivery-checkpoint.md`,
  `docs/backlog/saas-maturity-and-multi-business-owner-readiness.md`,
  `docs/release-notes/index.md`,
  `docs/release-notes/android-booking-workflow-remediation.md`,
  `docs/release-notes/android-s1-admin-quote-editor.md`,
  `docs/release-notes/android-s2-cancellation-decisions.md`,
  `docs/release-notes/be-cancel-1-cancellation-decision-safety.md`,
  `docs/release-notes/d1-client-denial-marker.md`
- **B4.1 Corrections Recorded:**
  1. **Code-reference accuracy:** Corrected `canExecuteVisits` attribution across B4 docs to
     `const canExecuteVisits = role === 'owner' || role === 'admin' || role === 'staff'` in
     `mobile/src/screens/RequestDetailScreen.tsx` (never `mobile/src/utils/bookingWorkflow.ts`).
  2. **CI workflow run IDs:** Reconciled live-verified GitHub Actions CI run IDs in §2:
     `#76` (`2d69045d9bd50e3a6f3f4cee0c4b8fd80ffcdd79`) → `43349187490`;
     `#77` (`16471f858062f20ec3814e22a5cae76524d0a94b`) → `43355736742`;
     `#78` (`2ef5a1f43b256189860a9c5f97d87e274c338211`) → `43359979814`.
  3. **Owner planning decisions (§4.1):**
     - Consolidated PR `#78` integration **STRATEGY APPROVED** (`CONSOLIDATED_PR78_INTEGRATION_STRATEGY=APPROVED`);
       **`MERGE AUTHORIZATION` NOT ISSUED** (`MERGE_AUTHORIZATION=NOT_ISSUED`).
     - **Calendar Option 3A SELECTED** (`LEGACY_MULTIDAY_CALENDAR_DECISION=OPTION_3A_SELECTED`):
       retain current estimated-start-time behavior (`WINDOW_START_HOURS` in `google_calendar.py`),
       without a new Calendar code change.
     - **Full pilot convergence chosen for PLANNING ONLY** (`PILOT_CONVERGENCE_PLANNING_SCOPE=FULL_CONVERGENCE_PLANNING_ONLY`).
- **Deployment / Release Status:** NONE. Nothing merged, marked Ready, built, deployed, or
  distributed. `W3C2_FUNCTIONAL_ACCEPTANCE=COMPLETE` (2026-10-27 single-settlement scenario) remains
  the latest completed production milestone.
- **Explicitly Unchanged / NOT AUTHORIZED Gates:**
  - **`W1_PRODUCTION_RELEASE_AUTHORIZED=NO`** (`W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES`; Workstream 1
    `pet_ids` and Ryan Slice `W1` `WALK_20MIN` remain **NOT AUTHORIZED** for production deployment).
  - **`MERGE_AUTHORIZATION=NOT_ISSUED`** (no PR Ready conversion or merge authorized).
  - `D-2` production cancellation inventory, AWS checks, `terraform plan`/`apply`, backend/web
    deployment, Android EAS build, Play/TestFlight distribution, Ryan testing, tenant changes, and
    Stripe live: **NOT AUTHORIZED**.
- **Next Action:** STOP for ChatGPT review of B4.1 on Draft PR #79, followed by Matthew's explicit
  structured Gate C3c `MERGE AUTHORIZATION` for the consolidated integration gate.

---

## 14. PR #74 Reconciliation Log (Adopted vs. Superseded Content) & Historical PR #74 Resume Block

### 14.1 Explicit Mapping of Draft PR #74 (`afa75c4a3b9ac52198b7ff193686df3968957ebd`) Content
| PR #74 Section / File | Disposition in B4 | Details |
|---|---|---|
| `docs/project-continuity/README.md` (item 10 link) | **ADOPTED VERBATIM** | Links `december-11-delivery-checkpoint.md` as item 10 in the continuity hub. |
| `docs/project-continuity/master-handoff-prompt.md` (item 4 link) | **ADOPTED VERBATIM** | Adds `docs/project-continuity/december-11-delivery-checkpoint.md` to the startup reading list. |
| `docs/project-continuity/document-map.md` (checkpoint link) | **ADOPTED & EXTENDED** | Adopts the PR #74 checkpoint row and adds the missing release-note rows for `#67`, `#69`, `#71`, `#73`, `W3-C2`, `W3-C1`, `W3-B`, `PR #22`, and `PR #19` identified in PR #74 §12. |
| §1 Standing rules, §10 Kiro shell reliability, §11 Cross-session startup checklist | **ADOPTED VERBATIM** | Preserved unchanged from PR #74 (`afa75c4`). |
| §2 Verified snapshot (2026-11-12) | **UPDATED (Prior state preserved below)** | Retains all PRs from PR #74 §2 (`#46`, `#67`, `#68`, `#69`, `#71`, `#72`, `#73`, `#62`, `#43`, `#45`) and adds the new verified Draft PRs `#74` (`afa75c4`), `#75` (`b91e8cc`), `#76` (`2d69045`), `#77` (`16471f8`), and `#78` (`2ef5a1f`, 5/5 CI green). |
| §3 Production versus source-only | **ADOPTED & EXPANDED** | Preserves W3-C2 2026-10-27 milestone, Lambda hashes, and undeployed `main` list; adds the explicit distinction between Workstream 1 (`pet_ids`) and Ryan Slice `W1` (`WALK_20MIN`) plus the verified API route contract (`PUT /admin/cancel/decision` canonical). |
| §4 Product decisions, blocked actions and gates | **UPDATED** | Records B2-B source review completion (`#46`, `#67`, `#68`, `#69`, `#73`) and 5/5 CI green on `#78` (superseding PR #74's red-baseline CI gate blocker), while adding the pending Legacy Multi-Day Calendar choice (`Option 3A` vs `Option 3B`) and preserving all `NOT AUTHORIZED` gates (`D-2`, merge, deploy, Terraform, EAS, Play, Ryan). |
| §5–§9 Assessment, Release board, Critical path, Current batch, Known baseline failures | **UPDATED** | Reflects completion of B1-A (`#75`), B1-B (`#76`), B2-A (`#77`), B2-B, B2-C (`#78`), and B3, advancing the current batch from `CONTINUITY-DEC11` / `B1` to `B4` / `B5`. |
| §12 Stale-document flags & §13 Resume block | **RECONCILED & PRESERVED** | Resolves the repository doc flags in B4 and preserves PR #74's original §13 Resume Block verbatim below. |

### 14.2 Preserved Historical Resume Block from Draft PR #74 (`afa75c4a3b9ac52198b7ff193686df3968957ebd`)
- **Timestamp:** 2026-11-12 (initial PR #74 checkpoint prior to B1-A/B1-B/B2/B3/B4)
- **`origin/main`:** `8fe7fa78ad707ac67a05d29059d2771a9aa256c8` (unchanged by that batch)
- **Branch / PR:** `docs/december-11-delivery-checkpoint`, Draft PR #74 (worktree
  `%TEMP%\togs-dec11-ckpt`); first commit `bb5a8ab`, corrected by follow-up docs commit `afa75c4`
- **Files changed in PR #74:** `docs/project-continuity/december-11-delivery-checkpoint.md` (new,
  corrected); `docs/project-continuity/README.md`, `docs/project-continuity/master-handoff-prompt.md`,
  `docs/project-continuity/document-map.md` (one link each)
- **Tests in PR #74:** documentation only; Markdown link, scope and structure checks. No application tests.
- **Deployment status at PR #74:** none. Nothing merged, built, deployed or distributed.
- **Source acceptance at PR #74 (prior to B2-B/B2-C):** #69, #71, #72 source accepted (independent
  ChatGPT review); #73 final acceptance separate; #46/#67/#68 independent review to be established
  (subsequently completed in B2-B and integrated in #78).
- **Latest owner approval in scope at PR #74:** D-1/D-3 product policy; Dec 11 continuity direction
  and PR #74 docs-only corrections. D-2 production inventory NOT authorized.

---

## 15. B5-C Superseded Draft PR Audit (read-only, 2026-11-13; closure NOT authorized)

Because PR #78 was squash-merged, constituent heads are not ancestors of `main`; ancestry was
not used as the sole test. Evidence per PR: (a) ancestry to the pre-squash head `77e8ec8` (whose
tree equals `main`'s), (b) per-file blob comparison of the PR's own diff vs `cac3cd6`, (c) a
3-way `git merge-tree` of the PR head into `main`, and (d) for squash-combined PRs, targeted
recombination against #76. No PR was closed, edited or commented on.

| PR | Head | Evidence | Disposition |
|---|---|---|---|
| #75 | `b91e8cc` | merge into `main` is a no-op (result tree == `main` tree); 17/17 files identical | Fully represented — closure candidate |
| #62 | `057de19` | merge into `main` is a no-op; 13/13 files identical | Fully represented (consolidated by #75) — closure candidate |
| #76 | `2d69045` | ancestor of `77e8ec8`; 38/40 identical; `AdminDashboard.jsx`/`ClientPortal.jsx` later changed only by B2-A `16471f8` | Represented, later extended — closure candidate |
| #77 | `16471f8` | ancestor; 59/61 identical; 2 release notes gained only B4 lines (`7dd395b`) | Represented — closure candidate |
| #71 | `ccf2d84` | not an ancestor (combined in `16471f8`); 8/8 code/test files identical; release note = PR text + B4 note | Fully represented — closure candidate |
| #72 | `56174ce` | not an ancestor; #76 + #72 recombination conflicts only on one import line, resolved in `main` keeping #72's `getAdminRequest` and #76's removal of unused `disableClient`; other 7 files identical | Represented — closure candidate |
| #73 | `6f1c60a` | not an ancestor; #76 + #73 merges cleanly to exactly `main`'s `ClientPortal.jsx`; other code/test files identical | Fully represented — closure candidate |
| #46 | `06ee9d6` | ancestor; differing files changed later only by #67/#68/#69 (`134ba5a`, `257e045`, `ec806a7`) and B4/B4.1 docs | Represented; intentionally superseded by #67/#68/#69 — closure candidate |
| #67 | `d60b1b2` | ancestor; 8/12 identical; others extended by #68/#69 and B4 | Represented — closure candidate |
| #68 | `257e045` | ancestor; 2/3 identical; `RequestDetailScreen.tsx` only gained #69 lines (`canExecuteVisits` intact) | Represented — closure candidate |
| #69 | `e4040ef` | ancestor; 7/8 identical; release note gained only B4 lines | Represented — closure candidate |
| #74 | `afa75c4` | not an ancestor; checkpoint rewritten in B4 with §14 adopted/superseded mapping and the PR #74 resume block preserved verbatim | Intentionally superseded — closure candidate |
| #43 | `9a5dc1d` | not an ancestor; merging #43 into #76 is a no-op (result == #76 tree) | Superseded by #76 — closure candidate |
| #45 | `3c5679d` | not an ancestor; content (191 added lines incl. +61 in `guardrails.md` and a new policy note) is **NOT in `main`** | Not superseded — requires a separate Matthew policy decision |

Closure of any candidate requires separate Matthew approval (recommended: pointer comment to
`cac3cd6`, branches retained). PR #79 is already shown as MERGED by GitHub (auto-marked in B5-A).

---

## 16. B6-B1 Verified Production Baseline, Rollback and Compatibility (2026-11-13)

**Verification scope:** owner-approved, read-only AWS metadata only — account `358604342897`,
region `us-east-1`, profile `usmissionhero-website-prod`. Every call was a describe/list/get with
field-restricted output. No DynamoDB/production data, D-2 inventory, Terraform, Lambda code
download, rollback capture, environment-variable/secret/policy-document read, application API call
or mutation. Disposition: `PRODUCTION_BASELINE_VERIFIED_READ_ONLY`.

### 16.1 Verified baseline (all match the documented record)

| Resource | Live value |
|---|---|
| `togs-and-dogs-prod-admin` | `CodeSha256 GlA3mUtq3O0RJcdc3i2MQjwcbuo8aiv52ACvacQH99o=`, 209,825 bytes, LastModified 2026-10-27T13:09:41Z |
| Other 12 Lambdas (`intake`, `review`, `assign`, `job`, `google-auth`, `pet`, `cancellation`, `device`, `ses-feedback`, `postmark-webhook`, `stripe-webhook`, `platform`) | `CodeSha256 W6cqyudlRQF3Zw7uN2V42JzziwYITg8r5mCnsGdDAq4=`, 178,814 bytes, LastModified 2026-10-22 |
| Runtime / handlers | All 13 `python3.11`; handlers as defined in `infra/prod/main.tf`; exactly 13 functions with the `togs-and-dogs-prod-` prefix |
| Versions / aliases (`admin`, `review`, `cancellation`, `intake`, `job`) | `$LATEST` only; no aliases |
| API Gateway `a022yxuiue` stage `prod` | deployment `n40vai` |
| IAM `togs-and-dogs-prod-dynamodb-access` | default version `v3` (content not read) |
| Web bucket `togs-and-dogs-prod-toganddogs-hosting` | 11 objects incl. `index.html`, `assets/index-DrAWpyW_.js`, `assets/index-DEfFpwho.css` |
| CloudFront `E35L00QPA2IRCY` | `Deployed`; alias `toganddogs.usmissionhero.com` |
| Public `index.html` | SHA-256 `cc453a6eae57fc8b913d32087b732de59928b7616dde5866e7b92de283b85a57` (matches the W2C record); references `/assets/index-DrAWpyW_.js`, `/assets/index-DEfFpwho.css` |

### 16.2 Ryan slice status

The live 12-Lambda artifact `W6cqyudl…` is byte-identical (same base64 SHA-256) to the retained
rollback ZIP, whose 49 files match RC `b94455ac530e3ecca9a2fc2ddc69ed54902b84db`
(`release/pr22-client-request-privacy-rc`) member for member. That RC contains Ryan O1 Overnight
(`46bb6b8`), E3A child start (`e10a98e`), Ryan W1 Walk `WALK_20MIN` (`c51828e`) and R1
(`66d6cc3`). Status: **`BACKEND_CODE_DEPLOYED`** on the 12 non-admin Lambdas. **Not verified or
claimed:** runtime acceptance, customer use, Ryan testing. Slices A–C, C1, E1 and E2 backend
presence was not individually re-verified. **NOT DEPLOYED:** Workstream 1 `pet_ids`
validation/linking (#26 `429f3b9`), PR #78 scope, AC-9, W4 Option A web. Gates unchanged:
`W1_PRODUCTION_RELEASE_AUTHORIZED=NO`; `W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES`.

### 16.3 W2C date note (not resolved)

The recorded W2C deployment milestone (2026-10-08, `current-state.md` and the W2C release note) is
preserved. The live bucket objects report LastModified 2026-10-10 UTC (12:19Z for `index.html` and
the JS/CSS assets). Related observations: source commit `7c1a8f1` is dated 2026-10-10 07:46 −04:00
and the W2C release note's own pre-deploy snapshot path is labelled `w2c-web-2026-10-10`. These
are recorded without inferring that either date is wrong; resolution needs further release
evidence or an owner decision.

### 16.4 Rollback facts and gaps

- **Packaging:** all 13 Lambdas share one `src/backend` ZIP; no `publish`/alias/version resources in
  Terraform and only `$LATEST` live (verified for 5 functions), so there is no AWS-side version to
  roll back to. Terraform cannot regenerate an older artifact once `main` builds a different ZIP.
- **`W6cqyudl…` (12 non-admin Lambdas):** two local hash-verified copies (`release-artifacts`
  w3c2-phaseb copy and its OneDrive mirror, each with a SHA-256 sidecar) — byte-identical to the
  live artifact; valid restore source for any of the 12.
- **`1EPLbycK…` (pre-`263b3e7` admin):** one copy located (`D:\petcare-rollback\admin-1EPLbycK\`);
  the second copy recorded on 2026-10-27 was not located in the B6-A1 search.
- **`GlA3mUtq…` (current admin): NOT captured.** Two hash-verified copies are required before any
  `admin` apply (B6-B2).
- **API Gateway:** prior deployment `hhryhc` was destroyed; API rollback is fix-forward only.
  Lambda-only targeted applies do not change the API (deployment fingerprint hashes API semantics
  only).
- **Web:** bucket versioning was recorded as disabled at W2C; an 11-object pre-deploy snapshot is
  required before any web deploy.

### 16.5 Compatibility constraints for the next release

- **Backend-first cancellation rollout:** the current backend's DENY sets `CANCELLATION_DENIED`,
  which the new web (WEB-CANCEL-1) does not expect, so the backend (`cancellation` + `review`, and
  `admin` for D-1) must deploy before web. The new backend accepts the current web's decisions
  without `cancellation_request_id` (optional field).
- **Legacy DENY 409:** after BE-CANCEL-1, a DENY on a pending request that has no stored
  `cancellation_prior_status` returns HTTP 409 `LEGACY_PRIOR_STATUS_UNKNOWN` and must be resolved
  manually; the D-2 inventory sizes this. `/admin/review` returns 409
  `CANCELLATION_TRANSITION_NOT_ALLOWED` when the current status is `CANCELLATION_REQUESTED` or the
  target is `CANCELLATION_REQUESTED`/`CANCELLATION_DENIED`; in the current web this affects only
  generic/bulk status transitions — "Review Cancellation" uses `PUT /admin/cancel/decision`.
  Clients may request cancellation only from `APPROVED`, `ASSIGNED`, `BOOKED`, `SCHEDULED`,
  `JOB_CREATED` (or repeat a pending request); legacy records never show the D-1 denial marker.
- **Curated web `pet_ids` incompatibility:** the deployed `intake` stores client `pet_ids` without
  ownership validation and its pet linking skips when `pet_ids` is present. A web or mobile build
  from `main` (existing-pet picker sending `pet_ids`) must therefore not ship before W1 is
  authorized and deployed, unless the picker is disabled by an off-by-default flag. Android
  versionCode 4 sends no `pet_ids` and has no cancellation call sites.
