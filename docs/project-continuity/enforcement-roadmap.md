# Enforcement Roadmap

**Which governance controls must eventually be enforced technically (GitHub rulesets, CI/CD, and AWS IAM), rather than only documented.**

> This document references, and does not duplicate, the organization/repository decisions in **ADR 0004 §5** (and §6), which lives in a **separate repository**: `mattnicomn/usmissionhero-aws-foundation` at `docs/decisions/0004-github-organization-and-repository-naming.md`. Read that ADR for the authoritative decisions; this roadmap only tracks what is currently **missing** here and what the two outstanding owner-gated security follow-ups are.
>
> Nothing in this document authorizes execution. Applying any control below (rulesets, CI deploy, IAM/OIDC, environments) remains subject to the canonical policy in [`guardrails.md`](guardrails.md) and explicit Matthew approval. `terraform apply` stays human-gated.

---

## Currently-missing enforcement (to be added, each separately approved)

| Control | Target state | Status |
|---------|--------------|--------|
| Branch protection / ruleset on `main` | Require PR + at least 1 review; block direct push and force-push | ❌ Not enforced |
| `CODEOWNERS` | Required reviewers routed by path | ❌ Not present |
| Secret scanning + push protection | Enabled on the repository | ❌ Not enforced |
| Minimal CI on PR | Typecheck + unit/property tests + web build run on every PR | ❌ Not present |
| GitHub OIDC + protected deployment environments | For any future CI-driven deploy (short-lived credentials, environment approval gates) | ❌ Not present |
| Human-gated `terraform apply` | `terraform apply` remains human-gated (plan → review → explicit approval) | ✅ Keep as-is (never automate without a separately approved design) |

These controls operationalize the documented guardrails (PR-only integration, no direct push to `main`, no secrets, test-before-deploy). Until they are enforced, the guardrails remain **convention-enforced only** and depend on agent/operator discipline.

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
