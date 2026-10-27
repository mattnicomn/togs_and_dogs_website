# PR #19 — Canonical Quote Cents Read Fix: Production Deployment + M4-B Verification

**Disposition:** `PR19_PRODUCTION_DEPLOYED_M4B_VERIFIED_PHASE_COMPLETE`
**Date:** 2026-10-20
**Production account:** `358604342897`

## Summary

Deployed the backend canonical-quote-cents read-normalization fix (merged PR #19) to
production as a code-only, 13-Lambda in-place update, and verified the mobile client
M4-B quote display defect is resolved. The Android quote total now renders `$200.00`
(was `$20,000.00` — an exact ×100 scale error).

## Defect fixed

Canonical `*_cents` money fields (`quote_amount_cents`, `deposit_amount_cents`) are
stored as integer minor units (cents). DynamoDB returns stored numbers as `Decimal`,
and the canonical read path fed that `Decimal` through the generic `to_cents(...)`,
which treats a non-`int` as MAJOR units and multiplies ×100. A stored `Decimal('20000')`
became `2_000_000`, and the correct ÷100 mobile formatter rendered `$20,000.00`. The fix
adds a dedicated `normalize_stored_cents(...)` helper (preserves already-cents magnitude
for both `int` and `Decimal`) applied only at canonical stored-cents read sites, and
re-points the three admin-response echo sites. Generic `to_cents` major-unit semantics
and the legacy PET major-unit converter are unchanged.

## Release lineage / provenance

- Merged PR: **#19**, squash commit `9a269aca2ae6311f4e7e6eb201e6e6118382e82d` on `main`
  (parent = pre-merge main `9f1c4be92827fe730ffcccf78569afbb80c15f14`).
- Deployment RC: `release/pr19-canonical-cents-rc @ d082517791774ea2619b100e14dc523774de4438`
  = OPS-3A.3 clean baseline `ce6b72414444511dd2ce36df023329943f255946` + clean cherry-pick
  of the PR #19 squash. Runtime delta vs the deployed OPS-3A.3 baseline = exactly two files
  (`src/backend/common/quote_contract.py`, `src/backend/handlers/admin_handler.py`).
- `google_auth_handler.py` byte-identical to the pre-AC-9 OPS-3A.3 baseline → **AC-9 remained
  excluded**. No scheduling / tenant / API / IAM ride-along.
- Saved plan SHA-256 `1DCC0491E51C9B2462365C6AF3B053173859A8A0A7142B64E814E14870104040`.

## Deployment (Gate: owner-approved apply)

- `terraform apply "pr19-cents.tfplan"` → **`Apply complete! Resources: 0 added, 13 changed, 0 destroyed.`**
- All 13 Lambdas updated **in place** (no recreation) from `CodeSha256 gBjdlXDUn0+0gHHyF/W5aKv35NROe81lsQZbBf4YR6I=`
  to **`QgEdTeYYMYF3k+b4f22NoHv2I7GEowtO1ynQ7ISafVk=`**, all Active / LastUpdateStatus Successful,
  runtime `python3.11`.
- API Gateway unchanged: REST API `a022yxuiue`, prod stage deployment `hhryhc`.
- `TENANT_RESOLUTION_MODE=multi` unchanged; zero env/config/IAM/API/DynamoDB/Cognito/SNS/SES/Stripe/tenant change.
- Pre-apply identity re-verified at apply time: account `358604342897`, saved-plan SHA match, RC HEAD match.

## M4-B verification (read-only)

- Infrastructure evidence (post-deploy): account `358604342897`; 13 Lambdas on the target
  package hash; all Active/Successful; API `a022yxuiue` / stage `hhryhc`; TRM=multi; AC-9 excluded.
- Mobile evidence (owner-supplied, Android Pixel 8 emulator screenshot):
  - `M4_B_QUOTE_VISIBILITY=PASS`
  - `M4_B_AMOUNT_DISPLAY=PASS` — total renders `$200.00` (prior `$20,000.00` ×100 defect resolved)
  - `M4_B_PAYMENT_REQUIREMENT_DISPLAY=PASS` — "No payment required" / "Not required"
  - `M4_B_ACCEPT_VISIBILITY=PASS`
  - `M4_B_DECLINE_VISIBILITY=PASS`
  - `M4_B_CRASH_REGRESSION=PASS`
  - **`M4_B_RESULT=PASS`**
- No Accept / Decline / Send performed during verification.

## Validation (pre-deploy, carried)

Focused quote suites 132 passed; full RC backend 90 failed / 1652 passed with zero quote-related
failures and no cents-fix regression (pre-existing `ce6b724`-lineage baseline failures only).

## Rollback

- Rollback target preserved (NOT executed): baseline commit `ce6b724` + previous deployed package
  `CodeSha256 gBjdlXDUn0+0gHHyF/W5aKv35NROe81lsQZbBf4YR6I=`; retained `backend.zip` and
  `ops3a3-production.tfplan` intact in the historical OPS-3A.3 RC worktree (untouched).

## Gates preserved

- `M4_C_DECLINE_AUTHORIZED=NO` — exactly one client Decline of the M4 test quote remains a
  separate, explicit future owner decision. No Accept/Decline performed.
- `SCHEDULING_WORKSTREAM_STATUS=DRAFT_PR_DELIVERY_CHECKPOINT`, `SCHEDULING_PR_MERGE_AUTHORIZED=NO` —
  scheduling workstream untouched.
- Stripe sandbox-only; Ryan testing NO; no second tenant; no tenant-resolution change; no mobile
  distribution change; no production test data created.

## Next owner decision

`M4_C_DECLINE_AUTHORIZED=NO — OWNER DECISION REQUIRED` (the single mobile Decline of the M4 test quote).
