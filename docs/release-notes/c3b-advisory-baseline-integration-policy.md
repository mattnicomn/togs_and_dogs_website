# C3b Advisory Baseline Integration Policy — Draft Proposal

**Date:** 2026-10-28 (America/New_York)
**Disposition:** `C3B_ADVISORY_BASELINE_POLICY_DRAFT_NOT_ACTIVE`
**Authority:** development, validation, non-force push and Draft PR delivery only.

## Status and decision boundary

This is a **prospective proposal, not active policy**. It grants no advisory exception, historical impairment acceptance, Ready transition, merge or deployment. The existing main guardrails govern adoption. Neither this branch, its CI results, this release note nor approval to develop the proposal authorizes its own integration.

The proposed procedures become usable only after explicit Matthew adoption of an exact policy revision through a separately valid governance transition and integration of that revision into main. Record the activation decision, immutable policy head, base, resulting integration SHA and time. Until then, the existing CLEAN and RC-intact requirements remain controlling. No retroactive merge authorization is created.

## Problem and terminology

The current [canonical checklist](../project-continuity/guardrails.md#pre-merge-verification-checklist-all-must-pass-any-failure--hard-stop) requires all items to pass: item 5 requires passing required checks, item 6 requires clean merge state, item 9 prohibits unresolved blockers, and item 10 requires RC integrity.

GitHub `mergeable=MERGEABLE` addresses merge conflicts; it is not policy approval. `mergeStateStatus=CLEAN` includes passing commit status. `UNSTABLE` identifies mergeability with non-passing status. Check `isDraft` separately. A non-required failing check may be advisory to GitHub enforcement while still blocking the current project policy. See [GitHub's merge-state definitions](https://docs.github.com/en/graphql/reference/pulls#mergestatestatus).

The effective main ruleset observed at authoring is `protect-main-mvp` (`24878098`): PR required, force-push/deletion blocked, zero required approvals, no required status checks and no bypass actors. This is a dated observation, not a promise that requirements remain unchanged. Re-read effective rules for every future case. No ruleset or CI setting is changed here.

## Proposed acceptance procedure and safeguards

The authoritative proposed wording is in [the inactive canonical annex](../project-continuity/guardrails.md#c3b-advisory-baseline-and-historical-impairment-proposal--not-active). After valid activation only:

- Normally require CLEAN. Only UNSTABLE attributable to individually accepted non-required baseline failures can qualify for the narrow CI exception; require OPEN, non-Draft, conflict-free mergeability and all effective protections.
- Initially limit eligibility to already-authorized documentation-only changes or reviewed Class A behavior-preserving unused-variable cleanup. No runtime behavior, auth/tenant/payment logic, production configuration, CI or ruleset change is authorized.
- Require all effective required and security checks to pass. No pending/missing required check, canceled/timed-out/unknown result, unexplained failure or security concern can be swept into a baseline exception.
- Bind the case to exact repository, PR, head, current base, target, reviewed file/diff digest, rules snapshot, run IDs/attempts and comparable test/runtime/dependency inputs.
- Compare failing identities, multiplicity and signatures, explain removals, record passing counts and prove zero new regressions. Counts alone are insufficient. Do not suppress tests, assertions, coverage or failures.
- Disclose skipped tests/build stages. Supply appropriate credential-free compensating validation for affected behavior; carried evidence for documentation-only changes requires input equivalence and honest provenance. Required/security checks cannot be replaced with local or carried results.
- Obtain explicit Matthew acceptance of each advisory failure and residual coverage limit, separate from the existing structured MERGE AUTHORIZATION. Report author-agent versus independent-human review honestly; configured review requirements remain binding.
- Retain sanitized audit summaries and checksum-linked detailed evidence with an independently controlled digest/reference. Recheck immediately before any separately authorized merge and record its result afterward.
- Expire acceptance on any bound head/base, scope, run/attempt, failure, workflow, protection or requirement change. New required checks are never grandfathered; no standing exception applies to future PRs.

## Historical PR19 impairment is a separate case

Known historical checkpoint:

- Accepted reconstructed source: `d082517791774ea2619b100e14dc523774de4438`.
- Verified tree: `7ae3b06ad254d340c27d5f52b8b207cd525e2216`; 1,128 committed files verified.
- Original damaged worktree and Git metadata preserved; original saved plan and deployed ZIP **MISSING**. Deletion cause remains unproven.
- Original plan expected identity: 170,222 bytes; SHA-256 `1DCC0491E51C9B2462365C6AF3B053173859A8A0A7142B64E814E14870104040`.
- Original deployed ZIP expected base64 SHA-256: `QgEdTeYYMYF3k+b4f22NoHv2I7GEowtO1ynQ7ISafVk=`; original byte size not established in the reviewed release records.
- Current admin rollback copies and PR22 evidence passed recorded offline checks. Those observations are not current production acceptance and do not establish possession of the missing originals.

Matthew's source-only acceptance remains valid within its stated scope; it is **not** acceptance of the historical artifact impairment. [PR44](https://github.com/mattnicomn/togs_and_dogs_website/pull/44) separately proposes the recovery documentation closeout. The [original PR19](pr19-canonical-quote-cents-production-deployment.md) and [PR22](pr22-client-request-privacy-production-deployment.md) deployment outcomes remain historical records, not new attestations of present artifact availability.

The proposed historical treatment requires a distinct prospective owner record for the specific PR19 impairment and one otherwise-eligible integration. Verify reconstructed source, preserve original evidence, identify every missing artifact and unavailable historical recovery path, verify all designated current RC/rollback evidence, and establish that the proposed integration does not depend on the missing originals. If a required active recovery path is impaired, STOP. Bind the disposition to integration head/base/diff, owner acceptance/time and audit evidence.

Only that expressly accepted historical component could then receive a disposition under items 9 and 10. Always report **historical impairment accepted; artifacts still MISSING**, never **restored** or **all historical RCs intact**. New/current RCs and designated current rollback evidence must remain intact. No source acceptance, CI acceptance or generic merge instruction silently waives this gate. No historical impairment acceptance is granted here.

Non-executable record outline; no field below is a completed acceptance:

```text
HISTORICAL RC IMPAIRMENT ACCEPTANCE — TEMPLATE ONLY
repository: <owner/repository>
integration_pr_head_base_diff: <exact prospective case>
historical_checkpoint: <commit/tree and specific known loss>
missing_artifact_identities: <originals remain MISSING>
source_verification: <reconstruction identity and evidence digest>
original_preservation: <unchanged original and Git metadata evidence>
current_rc_and_rollback_verification: <designated copies and required identities>
recovery_dependencies_and_limits: <no required active path depends on missing bytes>
audit_and_followup_reference: <sanitized record and controlled evidence digest>
accepted_by: <Matthew — pending>
accepted_at: <pending>
advisory_ci_acceptance: <separate if needed>
merge_authorization: <separate structured authorization still required>
```

ACL hardening, durable preservation of other Temp RCs, additional backup recovery and retention-standard adoption remain separately scoped follow-ups. No artifacts, ACLs, retention settings or RC locations are changed. Raw manifests, environment values, credentials, tfvars, private storage paths and package contents are excluded from this proposal.

## Evidence snapshot for PR43 and PR44

Both were OPEN and Draft, MERGEABLE/UNSTABLE, with no submitted reviews or unresolved review threads at review. No independent human approval is claimed. Both share base/main `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`.

| Case | Immutable head | Scope | CI run | Web lint | Backend |
| --- | --- | --- | --- | --- | --- |
| [PR43](https://github.com/mattnicomn/togs_and_dogs_website/pull/43) | `9a5dc1dd313116e6cec70d9bf52bdb82c4b67c7e` | Nine-file lint cleanup | [40799639824](https://github.com/mattnicomn/togs_and_dogs_website/actions/runs/40799639824) | 34 errors / 9 warnings | 74 failed / 2,067 passed |
| [PR44](https://github.com/mattnicomn/togs_and_dogs_website/pull/44) | `b784b79d09f5841e7e3c60662cd5b9ea09740a99` | Seven-file documentation closeout | [40804939315](https://github.com/mattnicomn/togs_and_dogs_website/actions/runs/40804939315) | 54 errors / 9 warnings | 74 failed / 2,067 passed |

Baseline [40735985571](https://github.com/mattnicomn/togs_and_dogs_website/actions/runs/40735985571), head `3badce421b44a9cfe16f3b20b5e7be6fa7fcbaf0`, has full tree `8598ed333c2b97a51f46d1ea6dccf1a54cc753f4`, identical to the base/main tree. Baseline web lint: 54 errors / 9 warnings; backend: 74 failed / 2,067 passed. All 74 backend failing identities and summary signatures matched both PR runs; passing counts were unchanged. Mobile, shared validators and security passed on both PRs.

PR43's earlier local evidence recorded all 543 web tests and the Node 22 build passing, while CI skipped web tests/build after lint. PR44 changed no runtime files; no local application suite/build was rerun for that documentation delivery. These facts support potential advisory-case review; they are not blanket coverage, current acceptance records or production assurance.

Under existing wording, both PRs remain BLOCKED by Draft/UNSTABLE and unresolved RC gate treatment. Under the proposed wording, their CI evidence may be considered only after activation and complete per-case owner acceptance, with independent RC disposition and every other gate satisfied. Neither PR is approved here. Policy adoption moves main; all subsequent cases require fresh base/head/diff/check verification, not automatic reuse of this snapshot.

## Adoption bootstrap conflict

**This proposal cannot authorize its own merge.** The current CLEAN requirement and RC-intact gate remain operative. At authoring, existing main CI evidence includes failed web lint (54 errors / 9 warnings) and backend pytest (74 failed / 2,067 passed); required checks are not configured, but current canonical item 6 still requires a clean state. PR19 historical impairment is unresolved under item 10. The policy Draft's own resulting CI evidence must be inspected and recorded independently in its PR; do not assume it matches this baseline.

A normal MERGE AUTHORIZATION alone does not silently override those prerequisites. If they remain unmet, **adoption under the existing checklist is BLOCKED; stop for Matthew's owner action**. No agent may apply the unadopted exception to bootstrap itself, infer an RC waiver, alter rulesets, force integration or mark Ready based on this document.

### Separate one-time governance transition proposal — NON-EXECUTABLE

Matthew may first choose to resolve the existing prerequisites through separately authorized work. If he instead wants a one-time governance transition, he must separately determine and explicitly authorize a prospective amendment to the operative requirements for one exact governance adoption case. This paragraph neither asserts that such a transition is permitted by the current unchanged checklist nor grants it. Any conflict remains a stop for owner action.

The separate owner decision would have to identify:

- Exact repository, future policy PR number, immutable head, then-current base, reviewed seven-file scope/diff digest and the intended policy revision.
- The precise operative clauses requiring prospective treatment, the failed non-required checks and exact run/attempt evidence, baseline identities/signatures, zero-new-regression proof and disclosed skipped-stage validation.
- Passing required/security checks and satisfied protection/review requirements; no bypass or weakening is proposed.
- A separate, explicit treatment of the known historical PR19 impairment, with verified current recovery evidence and preserved original/MISSING distinctions. No new/current artifact loss can be excused.
- Independent-review status, audit references, single-attempt expiry, and restrictions to governance integration only.
- Separate explicit authority for any Ready transition, structured MERGE AUTHORIZATION, and any activation decision. None exists from development authorization.

Do not fill or execute this outline as an authorization. No transition or activation is assumed. Existing owner permissions are unchanged; no direct push to main, rule bypass, self-approval or retroactive merge authorization is introduced.

## Migration and remaining decisions

1. Deliver and review this inactive Draft; record its actual CI results and exact head in the PR audit summary.
2. Matthew decides policy adoption, the narrow historical-treatment design, and the separate bootstrap conflict. No policy procedure is usable before a separately valid adoption and main integration.
3. If a valid adoption is later authorized, recheck exact head/base/scope/rules/runs and preservation evidence immediately beforehand; record the resulting integration SHA and activation decision/time afterward. Never use this proposal to supply its own missing authority.
4. Reassess each candidate PR against the new main. Any changed source head, base, conflicts, scope or CI evidence requires fresh review/acceptance; PR43 and PR44 remain untouched in this development package.
5. Require separate per-case advisory acceptance, historical impairment disposition where applicable, all remaining checklist passes and structured MERGE AUTHORIZATION. Production/deployment remains separately gated.

No runtime, production, Terraform/AWS, tenant, payment/Stripe, Ryan/W1 or mobile action is authorized or performed. This Draft changes only the seven approved documentation/steering files and preserves existing PRs, branches, worktrees and retained evidence.
