# December 11 Delivery Checkpoint (ACTIVE)

**Status:** ACTIVE delivery checkpoint for the single-business pilot (Togs & Dogs on PetCare Hero).
**Target:** usable Android + web application by **2026-12-11**.
**As of:** 2026-11-12. **Assessment:** **AT RISK** (see §5).

This file is the shared checkpoint for ChatGPT, Kiro Desktop/Web and authorized implementation
agents. It does not replace [`guardrails.md`](guardrails.md) (canonical policy) or
[`current-state.md`](current-state.md) (production record). It references existing release notes
rather than repeating them.

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
4. **Distinguish the stages.** Code complete ≠ merged ≠ deployed ≠ built ≠ distributed ≠
   acceptance-tested. Passing tests or an open Draft PR is not released functionality.

---

## 2. Verified snapshot (2026-11-12)

Verified with `git fetch` / `git rev-parse` / `gh pr view` / `gh pr checks` on 2026-11-12.

| Item | Value |
|---|---|
| `origin/main` | `8fe7fa78ad707ac67a05d29059d2771a9aa256c8` (2026-10-28, PR #14 test isolation; previous #5 CI workflow, #42 W3-C2 acceptance docs) |
| Stash (main checkout) | none |
| Main checkout | on `fix/web-eslint-baseline-20261011` (PR #6 branch) with one untracked `infra/prod/_gatea_plan_out.txt` — preserve |
| Ruleset `protect-main-mvp` | PR required, 0 approvals, no required status checks (per PR #45 CI notes) |

Release-relevant Draft PRs (all OPEN, Draft):

| PR | Branch → base | Head SHA | Mergeable | CI (main-targeting only) |
|---|---|---|---|---|
| #46 Android booking workflow remediation | `mobile/android-workflow-remediation` → `main` | `06ee9d628ac57d1a988e264ec74c26fe41174125` | MERGEABLE | mobile/shared/GitGuardian pass; backend+web red = baseline |
| #67 S1 owner/admin quote editor | `mobile/s1-admin-quote-editor` → #46 | `d60b1b203782c7b99382e2cfd525b96757dd720c` | MERGEABLE | not run (stacked) |
| #68 owner/admin visit Start/Complete | `mobile/s1-visit-rbac-a1` → #67 | `257e045fe15095c981a08b6345efd076ee80ba3f` | MERGEABLE | not run (stacked) |
| #69 S2 cancellation decisions | `mobile/s2-cancellation-decisions` → #68 | `e4040ef040cd49fb05bd3ba09b7999475f765ea5` | MERGEABLE | not run (stacked) |
| #71 BE-CANCEL-1 decision safety | `fix/be-cancel-1-decision-safety` → `main` | `ccf2d8460bde909e1bb63d812f360de1f62ecf8e` | MERGEABLE | mobile/shared/GitGuardian pass; backend+web red |
| #72 WEB-CANCEL-1 decisions + cycle id | `web/web-cancel-1-cycle-compatibility` → `main` | `56174ce7a947a83e41cf44ea0ac68e1e3bf0eb3c` | MERGEABLE | mobile/shared/GitGuardian pass; backend+web red |
| #73 D-1 client denial marker | `feat/d1-client-denial-marker` → `main` | `6f1c60ad2e32cb1ad06622d277cd0bf4cb50b287` | MERGEABLE | mobile/shared/GitGuardian pass; backend+web red |
| #62 C3.1 combined backend test isolation | `test/c3-1-combined-backend-test-isolation` → `main` | `057de19c01fbe24883192da3c68fbfda3bfadf1f` | MERGEABLE | not re-checked here |
| #43 web Class A lint cleanup | `pra-lint-only` → `main` | `9a5dc1dd313116e6cec70d9bf52bdb82c4b67c7e` | MERGEABLE | web lint 34 errors / 9 warnings |
| #45 inactive advisory-baseline policy | `governance/c3b-advisory-baseline-acceptance` → `main` | `3c5679d72dd3cb239ec6785ce31d96e5d95799cb` | MERGEABLE | adoption BLOCKED (own description) |

Mobile stack: **#69 → #68 → #67 → #46 → `main`**. Also open: #6 and #18 (CONFLICTING), #7–#17
(source PRs consolidated by #62), #37, #44, #47–#60 and #63–#66 (inactive contracts and
orchestrator work, not on the December 11 path).

---

## 3. Production versus source-only

**Latest completed production milestone:** W3-C2 MANUAL_EXTERNAL bounded functional acceptance,
**2026-10-27** (single full-settlement scenario only). See
[W3-C2 release note](../release-notes/w3c2-manual-external-payment-route.md) and
[`current-state.md`](current-state.md).

Recorded production state (from `current-state.md`, not re-verified against AWS here):

- Admin Lambda `GlA3mUtq…`; the other 12 Lambdas `W6cqyudl…` (PR #22 privacy release).
- `W1_PRODUCTION_RELEASE_AUTHORIZED=NO`; `W3C2_UNTARGETED_APPLY_ACTIVATES_W1=YES` — an
  untargeted apply would ship every merged-not-deployed backend change at once. Prohibited.
- Mobile internal builds: iOS `1.0.0 (6)` / Android `1.0.0` versionCode `4`, both from
  `bf9f80d`. **None** of the D1/D2, E3B/E3B.1 or #46–#69 mobile work is in a build.
- Stripe sandbox-only (EIN). `TENANT_RESOLUTION_MODE=multi` unchanged.

**Merged to `main` but NOT deployed** (would ride along with any new full backend/web release):
Ryan Slices A–C, C1, D1–D2, R1, W1 Walk, O1 Overnight, E1, E2; Workstream 1 `pet_ids`
association (PR #26/#27); W3-B payment domain (PR #29, except inside the admin artifact);
W4 Option A client status presentation (PR #24, web/mobile). See
[`document-map.md`](document-map.md) for each release note.

**Source-only (Draft PRs):** everything in the §2 table.

---

## 4. Product decisions, blocked actions and gates

Approved (owner):
- **D-1 / D-3:** client-portal cancellation-denial marker; verified historical prior status only
  (BE-CANCEL-1 Option A restores captured `APPROVED`/`ASSIGNED`); **no denial email**. Mobile
  marker deferred.

Not approved / blocked:
- **D-2 production inventory:** NOT approved. No production reads/writes for inventory.
- Merge or Ready of any PR; any deployment; Terraform plan/apply; EAS build; Play/TestFlight
  changes; Ryan or tester changes; production test data; tenant changes; tenant-resolution mode
  change; Stripe live.
- Integration gate: canonical guardrails require clean mergeability and RC integrity. Every
  main-targeting PR is UNSTABLE on the documented red CI baseline, and PR #45 (advisory-baseline
  acceptance) is itself blocked. **An owner decision is needed on how integration proceeds**
  (fix the baseline first, or an explicit per-PR owner acceptance mechanism).

Gate owners: Matthew for every merge, deploy, build, distribution, production data, tenant, Stripe
and Ryan action. ChatGPT reviews. Kiro/AG execute only approved, bounded scope.

---

## 5. December 11 assessment: AT RISK

Repository evidence supports the code for a usable pilot existing mostly in source. **No item on
the critical path has been merged, deployed, built or device-accepted.** About four weeks remain.
The main risks:

1. **Integration gate unresolved** (red CI baseline + blocked PR #45) — blocks every merge.
2. **Release accumulation:** the next full backend/web release ships many merged-not-deployed
   items (§3) that were never accepted together, including W1 activation.
3. **Cross-PR contract gap:** PR #71 changes DENY to restore the prior status and adds
   `cancellation_request_id`; mobile #69 expects `CANCELLATION_DENIED` and does not send the
   cycle id. #69 needs a follow-up before it is safe with #71 deployed.
4. **Mobile stack CI unverified:** #67–#69 never ran GitHub CI (stacked). No emulator/device run
   of #67–#69 is recorded.
5. **No independent review** of #46, #67–#69, #71–#73 (author self-review only).
6. **Android delivery needs separate gates:** EAS build, Play internal upload, device acceptance,
   Ryan testing.

It becomes **GO** only if the integration decision is made in the next few days and each batch
below completes in about one week or less. **NOT FEASIBLE** if App Store publication, Stripe live,
second tenant or SaaS maturity items are pulled into scope.

---

## 6. Release board (Android / web / backend pilot scope)

State key: DEP = deployed · SRC-ACC = source accepted (merged, reviewed) · IMPL = implemented,
not accepted (Draft or merged-not-deployed) · NOT = not implemented · UNK = unknown.

| # | Feature (user value) | State | PR / SHA / deps | Remaining action → acceptance check | Blocks | Gate / owner | Pri |
|---|---|---|---|---|---|---|---|
| 1 | Integration path (any change can reach `main`) | NOT | #62 `057de19`, #43 `9a5dc1d`, #45 `3c5679d` | Owner decision; then backend baseline via #62 + web lint → main-targeting CI matches the accepted baseline | Android + web | Matthew | P0 |
| 2 | Android booking continuation + exact visit access | IMPL | #46 `06ee9d6` | Independent review → merge → build → device check of M&G approval, child-visit selection | Android | Matthew (merge/build) | P0 |
| 3 | Android owner/admin quote create/edit/send | IMPL | #67 `d60b1b2` (on #46) | CI on a main-targeting evidence branch; review; emulator run → quote DRAFT→SENT on device | Android | Matthew | P0 |
| 4 | Android owner/admin visit Start/Complete | IMPL | #68 `257e045` (on #67) | Same as #3; verify deployed `/admin/job/start` owner/admin behaviour (source-only today) | Android | Matthew | P0 |
| 5 | Android owner/admin cancellation decisions | IMPL, contract gap | #69 `e4040ef` (on #68), depends on #71 | Follow-up: send `cancellation_request_id`, accept restored status after DENY → tests + device check | Android | Matthew | P0 |
| 6 | Server-safe cancellation decisions (exact literals, atomic, cycle id, review guard) | IMPL | #71 `ccf2d84` | Independent review → merge → targeted backend deploy → bounded acceptance | Android + web | Matthew (deploy) | P0 |
| 7 | Web explicit Approve/Deny cancellation (removes Cancel=DENY bug) | IMPL | #72 `56174ce`, depends on #71 | Fill the PR body test placeholder; review → merge after #71 → web deploy → admin smoke | Web | Matthew | P0 |
| 8 | Client sees "cancellation declined" marker | IMPL | #73 `6f1c60a`, depends on #71 deployed | Review → merge after #71 → deploy backend projection then web → client smoke | Web | Matthew | P1 |
| 9 | Accumulated merged-not-deployed scheduling/workflow (A–C, C1, W1 Walk, O1, E1, E2, W4, pet_ids) | IMPL (merged) | on `main` | Release-candidate plan listing every item + combined acceptance; W1 activation decision | Android + web | Matthew | P0 |
| 10 | Android build + Play internal distribution | NOT (for new code) | last build vc4 `bf9f80d` | After #2–#5 merged: EAS build → Play internal → device acceptance | Android | Matthew (EAS, Play, Ryan) | P0 |
| 11 | Web deployment of current `main` + cancellation web | NOT | last recorded web deploy W2C 2026-10-08 (verify) | Build from RC → S3/CloudFront deploy → authenticated smoke | Web | Matthew | P0 |
| 12 | Mobile cancellation marker for clients | NOT (deferred by D-1) | — | Post-pilot | — | Matthew | P2 |
| 13 | Branded password-reset email (Cognito → Postmark) | IMPL (committed, not deployed) | see current-state | Terraform plan/apply when approved | Neither (generic email works) | Matthew | P1 |
| 14 | Legacy multi-day window fidelity | IMPL | #18 `bfaf683` CONFLICTING | Rebase + review | Neither | Matthew | P2 |
| 15 | Archive/delete/purge of pending cancellations | UNK | noted in #71/#72 | Verify behaviour before pilot | Web | — | P1 |
| 16 | Web Request List / Visit Requests queue correction; client onboarding completion | NOT | backlog items 16–17 | Post-pilot unless owner promotes | Web | Matthew | P1 |
| 17 | Multi-tenant SaaS maturity (PTM-0..13, F02), Stripe live, subscription billing, App Store publication | NOT / blocked | backlog | Out of December 11 scope | SaaS only | Matthew | P2 |

---

## 7. Critical path (dependency order)

Each batch is bounded, ends at a Draft/evidence stop, and needs its own owner approval.

1. **B1 — Integration gate.** Owner decides the integration mechanism. Execute: verify PR #62 CI on
   its current head (expected 6 remaining backend failures, IDs listed in #62); scope the remaining
   web lint (34 after #43). Tests: backend full suite vs baseline node-ID set; web lint diff by
   file/rule/message.
2. **B2 — Mobile S2-R1 cancellation compatibility** (recommended next, §8). Tests: mobile focused
   + full `npm run test:ci`, typecheck, mutation check.
3. **B3 — Mobile stack CI evidence.** Temporary main-targeting Draft from the #69(+S2-R1) head,
   labelled CI-evidence-only (precedent: closed PR #70). Tests: CI mobile job; backend/web compared
   against baseline.
4. **B4 — Independent review** of #71, #72, #73 and the mobile stack (two-model semantic review).
   Fix findings in place.
5. **B5 — Integration** (owner MERGE AUTHORIZATION per PR, in order): #62 → #71 → #72 → #73 →
   #46 → #67 → #68 → #69, retargeting each stacked PR to `main` only after its parent merges.
6. **B6 — Release candidate plan.** Enumerate everything on `main` not yet deployed; decide on W1;
   produce a targeted, plan-only Terraform scope. Tests: full suites on the RC; offline hash
   reproduction.
7. **B7 — Deploy + acceptance** (owner-gated): backend, then web, bounded smoke with synthetic
   non-customer data only if approved.
8. **B8 — Android build + Play internal + device acceptance** (owner-gated; Ryan testing separate).

**Android done:** #46–#69 (+S2-R1) merged; a new EAS Android build from the accepted RC is on Play
internal testing; owner/admin can approve bookings, send quotes, Start/Complete visits and decide
cancellations on a physical device against the deployed backend; no new crash in the existing
client flows.

**Web done:** #71–#73 merged and deployed with the RC; admin decides cancellations through the new
modal; client sees the denial marker; authenticated smoke passes for intake, review, assignment
and the client portal; no tenant or Stripe change.

---

## 8. Current batch and next action

- **Current batch:** CONTINUITY-DEC11 (this documentation PR). Stops at Draft PR for ChatGPT review.
- **Next development batch (recommended): B2 — MOBILE-S2-R1.** On a new branch stacked on #69
  (`e4040ef`): send `cancellation_request_id` in `PUT /admin/cancel/decision` when present, and
  accept either the restored prior status (BE-CANCEL-1) or `CANCELLATION_DENIED` (deployed backend)
  after DENY, mirroring WEB-CANCEL-1 (#72). Mobile source and tests only.
- **Stopping condition:** Draft PR open with focused + full mobile tests passing and typecheck
  clean; no merge, build or distribution.
- **Parallel owner decision needed:** B1 integration mechanism.

---

## 9. Known baseline failures (do not treat as new)

| Area | Baseline | Evidence |
|---|---|---|
| Backend CI | 74 failed / 2,067 passed on `main` | baseline run 40735985571, job 122984539482; matched by #43/#45/#46 CI and #71/#73 local runs |
| Backend after #62 | 6 expected remaining (`test_r7a_optional_email` ×3, `test_r18l_client_booking_limits` ×2 date-dependent, `test_r7e_multi_day_jobs` ×1) | PR #62 description |
| Web lint | 54 errors / 9 warnings (63) on `main`; 34/9 with #43 | run 40735985571; PR #43 |
| Web CI | tests/build skipped after lint fails — no CI web test/build evidence on any PR | PR #45/#46 CI notes |
| Web flake | `AdminDashboardWorkflowActions` "navigates ASSIGNED locally" timing flake | fixed in #72; seen in #73 local baseline |
| Local vs CI env | local Python 3.13.3 / moto 5.0.0 / boto3 1.42.56 vs CI Python 3.12 / moto 5.1.4 / boto3 1.37.1 | PR #62, #71 |

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

## 12. Stale-document flags (for a separately scoped correction)

- `master-handoff-prompt.md` "CURRENT STATE SUMMARY" stops before W3-C2 and does not mention the
  2026-10-27 acceptance or the cancellation/mobile Draft PRs.
- `document-map.md` lists no W3-B, W3-C1, W3-C2, PR #19 or PR #22 release notes.
- `current-state.md` header is dated 2026-10-27; `main` later advanced to `8fe7fa7` (CI workflow
  #5 and test isolation #14). No production impact, but the snapshot is stale.
- PR #72 description still contains the literal `WEB_RESULTS_PLACEHOLDER` under "Tested".
- PR #69 description predates #71: it lists backend blockers that #71 addresses, and expects
  `CANCELLATION_DENIED` after DENY.

---

## 13. RESUME BLOCK

- **Timestamp:** 2026-11-12
- **`origin/main`:** `8fe7fa78ad707ac67a05d29059d2771a9aa256c8` (unchanged by this batch)
- **Branch:** `docs/december-11-delivery-checkpoint` (worktree `%TEMP%\togs-dec11-ckpt`)
- **Files changed:** this file (new); `README.md`, `master-handoff-prompt.md`, `document-map.md`
  (link only)
- **Tests:** documentation only; Markdown link, scope and structure checks. No application tests.
- **Deployment status:** none. Nothing merged, built, deployed or distributed.
- **Remaining blockers:** integration-gate decision (B1); #69 contract gap; no independent reviews;
  release-accumulation and W1 decision; all deploy/build/distribution gates.
- **Latest owner approval in scope:** D-1/D-3 product policy; D-1 Draft PR #73 delivery (complete).
  Nothing else is approved.
- **Next action:** ChatGPT review of this checkpoint PR; owner B1 decision; then B2 MOBILE-S2-R1
  if approved.
