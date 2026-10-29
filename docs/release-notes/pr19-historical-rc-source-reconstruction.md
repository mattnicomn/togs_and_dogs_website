# PR19 Historical RC — Accepted Source-Only Reconstruction

**Date:** 2026-10-28 (America/New_York)
**Disposition:** `PR19_SOURCE_ONLY_RECOVERY_ACCEPTED_HISTORICAL_ARTIFACTS_MISSING`
**Scope:** local evidence maintenance and documentation; no production operations.

## Owner decision and source identity

Matthew accepts the reconstructed PR19 source checkpoint as verified **source-only evidence**. This acceptance does not restore the original working tree, recover original deployment artifacts, authorize a release, or establish current production acceptance.

- Recovered source commit: `d082517791774ea2619b100e14dc523774de4438`.
- Verified Git tree: `7ae3b06ad254d340c27d5f52b8b207cd525e2216`.
- **1,128 committed files verified**: all committed blob objects were readable, and all reconstructed tracked files matched their Git blob identities byte-for-byte. Per-file sizes and SHA-256 evidence were recorded locally.
- The independent shallow source checkout is in durable local storage outside temporary directories, at detached HEAD, with no object alternates. Its working tree was clean and Git object-integrity verification passed.
- The recovery package recorded 1,169 verified checksum entries. The original damaged worktree, its surviving files and its Git administrative metadata were preserved without in-place repair; before/after checks matched. No existing worktree was removed or unregistered.

## Historical artifacts remain missing

| Historical PR19 artifact | Disposition | Expected identity |
| --- | --- | --- |
| Original saved plan, `pr19-cents.tfplan` | **MISSING** | 170,222 bytes; SHA-256 `1DCC0491E51C9B2462365C6AF3B053173859A8A0A7142B64E814E14870104040` |
| Original deployed `backend.zip` | **MISSING** | Base64 SHA-256 `QgEdTeYYMYF3k+b4f22NoHv2I7GEowtO1ynQ7ISafVk=`; original byte size not established in the reviewed release records |

The bounded search examined 19 candidate files in approved local project, backup and retention locations. No exact originals were found. Three inaccessible-location diagnostics were recorded; the search was not an exhaustive all-disk or archive-content search. **MISSING describes the evidence currently located, not proof that no backup exists anywhere.**

Neither artifact was Git-tracked. Reconstructing committed source does not recover an approved saved plan or prove possession of the original ZIP bytes. No historical plan or ZIP was regenerated, replaced or fabricated.

The file-deletion cause remains **unproven**. Temporary-directory cleanup is a possible explanation, not an established attribution. Historical execution records corroborate the plan's earlier existence and approved checksum; they do not supply the missing artifact itself.

## Offline rollback and PR22 evidence

During the recovery checkpoint, offline checksum verification passed for:

- Both current documented admin rollback copies: 208,721 bytes each; base64 SHA-256 `1EPLbycKQSFOwH58Y7c5xGU+eG/Ht8qNS7pxkoFdBKk=`. The copies were on separate physical disks.
- The PR22 RC backend ZIP and two documented older rollback copies: 178,814 bytes each; base64 SHA-256 `W6cqyudlRQF3Zw7uN2V42JzziwYITg8r5mCnsGdDAq4=`.
- The PR22 saved plan: SHA-256 `1E707B846999C2B1352BB77334BFB6DCA2F15681D594D6569A1B3D9DA6EBB170`.
- PR22 source remained clean at `b94455ac530e3ecca9a2fc2ddc69ed54902b84db`.

These are **offline file-integrity observations at the recovery checkpoint**. No AWS or production state was queried, no production operation was performed, and no new production acceptance is claimed. Verified current rollback copies do not erase the historical PR19 artifact impairment.

## Evidence boundaries and follow-up

The durable local recovery report, final manifest, per-file verification records and checksum inventory retain the detailed evidence. Raw manifests, private storage paths, environment values, tfvars, credentials and package contents are intentionally excluded from this repository note.

The original [PR19 deployment and M4-B verification](pr19-canonical-quote-cents-production-deployment.md) and [PR22 privacy deployment](pr22-client-request-privacy-production-deployment.md) remain historical records. Their dated retention qualifications describe the later evidence impairment without rewriting the original deployment outcomes.

Outstanding, separately scoped owner decisions/work:

- Further bounded backup recovery, or formal disposition of the missing historical artifacts; neither retirement nor deletion is authorized here.
- Storage ACL review/hardening and durable preservation of other retained RCs currently under temporary directories. These risks are documented follow-up work; no permissions, retention settings, worktree locations or retained artifacts were changed by this documentation closeout.
- Review/adoption of the durable retention standard proposal, verification cadence and any protected off-machine backup. **No new retention policy is adopted.**
- PR #43 merge-state policy clarification remains a separate proposed governance workstream. Source-only recovery acceptance does not resolve its integration gates or authorize a Ready transition or merge.

## Delivery boundary

This closeout changes documentation only. It does not alter canonical guardrails, application source, CI, GitHub rulesets, production configuration, Terraform, AWS, Stripe, tenants, W1 activation, Ryan testing or mobile distribution. No deployment, repair or deletion of the damaged original RC, or historical artifact regeneration is authorized or performed by this PR.
