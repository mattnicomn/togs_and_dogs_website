# Enforcement Roadmap

**Which governance controls must eventually be enforced technically (GitHub rulesets, CI/CD, and AWS IAM), rather than only documented.**

> This document references, and does not duplicate, the organization/repository decisions in **ADR 0004 §5** (and §6), which lives in a **separate repository**: `mattnicomn/usmissionhero-aws-foundation` at `docs/decisions/0004-github-organization-and-repository-naming.md`. Read that ADR for the authoritative decisions; this roadmap tracks which controls are currently **technically enforced** versus still **documented-only** here, and what the two outstanding owner-gated security follow-ups are.
>
> Nothing in this document authorizes execution. Applying any control below (rulesets, CI deploy, IAM/OIDC, environments) remains subject to the canonical policy in [`guardrails.md`](guardrails.md) and explicit Matthew approval. `terraform apply` stays human-gated.

---

## Enforcement status (technical vs. documented)

The table below distinguishes **technically enforced** controls (GitHub rejects the action server-side) from **documented-only** requirements (convention, dependent on agent/operator discipline). Status verified read-only on 2026-10-11.

| Control | Target state | Status |
|---------|--------------|--------|
| Branch protection / ruleset on `main` | Require PR; block direct push, force-push, and branch deletion | ✅ **Technically enforced** — repo ruleset `protect-main-mvp` (ID `24878098`), active, PR-required with 0 approvals, force-push + deletion blocked, empty bypass list (see Gate C2 below). Independent-review enforcement (≥1 approval) is a separate later step. |
| Secret scanning | Enabled on the repository | ✅ **Technically enforced** — `secret_scanning = enabled` (verified 2026-10-11). |
| Secret scanning push protection | Enabled on the repository | ✅ **Technically enforced** — `secret_scanning_push_protection = enabled` (verified 2026-10-11). |
| `CODEOWNERS` | Required reviewers routed by path | ❌ Not present (meaningful only once ≥1 required approval + an independent reviewer exist) |
| Minimal CI on PR | Typecheck + unit/property tests + web build run on every PR | ❌ Not present (documented-only; no `.github/workflows` yet) |
| Independent review (≥1 approval) | Require review from a non-author before merge | ❌ Not enforced (requires a second reviewer account; owner cannot approve own PR) |
| GitHub OIDC + protected deployment environments | For any future CI-driven deploy (short-lived credentials, environment approval gates) | ❌ Not present |
| Human-gated `terraform apply` | `terraform apply` remains human-gated (plan → review → explicit approval) | ✅ Keep as-is (never automate without a separately approved design) |

These controls operationalize the documented guardrails (PR-only integration, no direct push to `main`, no secrets, test-before-deploy). The branch ruleset and secret-scanning controls above are now **server-enforced**; the remaining ❌ rows are still **convention-enforced only** and depend on agent/operator discipline.

### Gate C2 — `protect-main-mvp` ruleset (executed 2026-10-11)

- **Ruleset ID:** `24878098` · **Name:** `protect-main-mvp` · **Target:** `refs/heads/main` only · **Enforcement:** `active`.
- **Rules:** require a pull request before merging (`required_approving_review_count: 0`), block force pushes (`non_fast_forward`), block branch deletion (`deletion`).
- **Bypass actors:** none (`[]`); `current_user_can_bypass: "never"`. Direct push / force-push / deletion to `main` are blocked for everyone including the owner. Normal PR merges with zero approvals remain available to the owner (GitHub never lets an author approve their own PR, so 0 approvals is the correct ceiling for a single-collaborator repo).
- **Rollback (not executed):** a repository admin can disable or delete the ruleset through Repo → Settings → Rules → Rulesets → `protect-main-mvp` (set Enforcement to Disabled, or Delete). Ruleset administration is an admin settings capability independent of the empty bypass list, so there is no administrative lockout. API equivalents: `PUT …/rulesets/24878098 {"enforcement":"disabled"}` or `DELETE …/rulesets/24878098`.

> **Organization-migration caveat.** `protect-main-mvp` is a **repository-level** ruleset on the current personal-account repo. Per ADR 0004 §8, this repository is a future org-migration target. A GitHub repository transfer does **not** carry repository-level rulesets with it — after any org migration this ruleset must be **revalidated and recreated** (or replaced by an organization-level ruleset) under the new owner. Treat the control as present only while the repo remains at `mattnicomn/togs_and_dogs_website`.

---

## Outstanding owner-gated security follow-ups

These are tracked here as explicit, separate items. Both remain **approval-gated** and are **not** done.

1. **Stripe test-credential rotation — NOT done, approval-gated, sandbox/test-mode only.**
   - The identified Stripe **test** API key and **test** webhook-signing secret have **not** been rotated.
   - Rotation requires separate explicit Matthew approval and remains **sandbox/test-mode only** (no live-mode activity is implied or authorized).
   - Do not display, search for, reuse, or record the exposed values.

2. **Repository public → private exposure review — deferred.**
   - The repository is **currently PUBLIC**. ADR 0004 §6 (separate repo, referenced above) targets **PRIVATE**.
   - A visibility/exposure review is **deferred** and remains Matthew-gated. No repository visibility or permission change is authorized by this document.

---

## Scope note

This roadmap is documentation only. It does not change repository settings, CI, IAM, or Stripe configuration, and it does not supersede the canonical policy or ADR 0004. Reconcile against ADR 0004 in the separate foundation repo before implementing any control listed here.
