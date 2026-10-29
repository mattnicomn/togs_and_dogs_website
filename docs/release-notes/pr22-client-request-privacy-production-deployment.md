# PR #22 — Client Request Quote-Field Privacy Projection: Production Deployment + Convergence Verified

**Disposition:** `PR22_PRIVACY_PRODUCTION_DEPLOYED_VERIFIED`
**Date:** 2026-10-22
**Authoritative source checkpoint:** `main == origin/main == fd60a760b8f60e34cec7a698fa1771bf3f8a8a99` (PR #22 squash merge)

Owner-approved production deployment of the merged PR #22 privacy remediation as a
code-only, 13-Lambda in-place update in account `358604342897`.

## Source / RC

- **Merged source:** `fd60a760b8f60e34cec7a698fa1771bf3f8a8a99`
- **Production RC:** `release/pr22-client-request-privacy-rc`
- **RC SHA:** `b94455ac530e3ecca9a2fc2ddc69ed54902b84db`
- **Parent production baseline:** `d082517791774ea2619b100e14dc523774de4438`
- **Runtime delta vs prior production — exactly two backend files:**
  - `src/backend/common/auth.py`
  - `src/backend/handlers/admin_handler.py`
  No other `src/backend` runtime file changed. (RC built on the PR #19 production
  baseline `d082517` + cherry-pick of only the PR #22 change-set, so the AC-9
  exclusion from the PR #19 baseline is preserved.)

## Privacy remediation (what changed)

`GET /client/requests` now builds each client booking-list item from an **explicit
client-safe allowlist projection** (`common.auth.project_client_request_list_item` /
`CLIENT_REQUEST_LIST_ALLOWLIST`) instead of passing raw REQUEST records through the
denylist-based `sanitize_booking_for_role`. A fresh dict is built from a vetted
allowlist, so any field not named is absent by construction (future REQUEST fields
cannot leak by default), and a non-dict/malformed record fails closed to an empty
projection.

This prevents incidental exposure of quote/commercial/internal REQUEST fields through
the client booking list, including: `quote_status`, `quote_revision`,
`quote_amount_cents`, `currency`, `deposit_amount_cents`, `payment_requirement`,
`payment_status`, `quote_notes_client`, `quote_notes_internal`,
`internal_pricing_notes`, `quote_history`, quote lifecycle timestamps/revisions,
decline reason, audit/admin/internal/staff fields, and raw `PK`/`SK`.

Known client booking-list consumers (mobile `BookingsScreen`, web `ClientPortal`)
were source-audited and all fields they legitimately depend on are preserved by the
allowlist. The dedicated `GET /client/quotes/{requestId}` projection is unchanged and
remains the authoritative client-safe commercial quote view (and continues to hide
DRAFT).

### Precise characterization (not a confirmed incident)

- The source-level exposure **path** was proven from source + tests.
- **No production customer/business records were inspected** at any point.
- **Actual historical exposure remains unknown.**
- This was a **privacy-hardening correction**, not a confirmed customer-data incident.

Status flags:
- `CLIENT_REQUEST_LIST_QUOTE_STATUS_CONTRACTUALLY_EXPOSED=NO`
- `CLIENT_REQUEST_LIST_QUOTE_STATUS_CAN_PASS_THROUGH_INCIDENTALLY=NO` (after this fix)

## Deployment

- **Authorized saved-plan SHA-256:** `1E707B846999C2B1352BB77334BFB6DCA2F15681D594D6569A1B3D9DA6EBB170`
- **Apply result:** `Apply complete! Resources: 0 added, 13 changed, 0 destroyed.`
- **Previous production package:** `QgEdTeYYMYF3k+b4f22NoHv2I7GEowtO1ynQ7ISafVk=`
- **New production package:** `W6cqyudlRQF3Zw7uN2V42JzziwYITg8r5mCnsGdDAq4=`
- **Post-deployment Lambda state:** 13/13 `Active`, 13/13 `LastUpdateStatus=Successful`,
  13/13 `CodeSha256=W6cqyudlRQF3Zw7uN2V42JzziwYITg8r5mCnsGdDAq4=`.
- **API unchanged:** REST API `a022yxuiue`, stage `prod`, deployment ID `hhryhc`.
- **Tenant mode unchanged:** `TENANT_RESOLUTION_MODE=multi`.
- **AC-9 remained excluded:** `AC9_DEPLOYED_BY_PR22_RC=NO` (RC `google_auth_handler.py`
  blob `130a4fe…` = PR #19 pre-AC-9 production baseline).
- Every one of the 13 changes was an in-place Lambda code-package update; zero
  env/handler/runtime/memory/timeout/IAM/API/DynamoDB/Cognito/SNS/SES/Stripe/tenant/
  scheduling changes.

## Terraform convergence (post-deploy)

Matthew manually ran `terraform plan -detailed-exitcode` from the PR #22 RC
infrastructure context in a fresh PowerShell session.
- Result: **`No changes. Your infrastructure matches the configuration.`**
- Exit code: **`0`**
- Therefore: `PR22_TERRAFORM_CONVERGENCE=PASS`.

## Rollback readiness (preserved, not executed)

- PR #19 baseline: `d082517791774ea2619b100e14dc523774de4438`
- Previous package: `QgEdTeYYMYF3k+b4f22NoHv2I7GEowtO1ynQ7ISafVk=`
- Historical RC worktrees/artifacts remain preserved and untouched.

## Acceptance boundary

Deployment acceptance for this release is infrastructure/package verification +
convergence only. No production business/customer records were inspected and no
functional quote mutation (Send/Accept/Decline) was performed.

## Gates after closeout

- `CLIENT_REQUEST_QUOTE_PRIVACY_REMEDIATION_MERGED=YES`; `PR22_PRIVACY_PRODUCTION_DEPLOYED_VERIFIED`.
- `W4_CAN_PROCEED_INDEPENDENTLY=YES`;
  `W4_IMPLEMENTATION_STATUS=READY_FOR_OWNER_APPROVED_IMPLEMENTATION`
  (selected architecture `W4_OPTION_A_FRONTEND_WORKFLOW_SUMMARY`; separate future phase).
- Scheduling: `SCHEDULING_WORKSTREAM_STATUS=DRAFT_PR_DELIVERY_CHECKPOINT`,
  `SCHEDULING_PR_MERGE_AUTHORIZED=NO`.
- Stripe sandbox-only; `RYAN_TESTING_AUTHORIZED=NO`; no second tenant; no mobile
  distribution; no production test data.

---

## 2026-10-28 — Historical PR19 rollback-evidence qualification

The deployment and convergence outcomes above remain the historical record. The earlier statement that historical RC worktrees/artifacts were preserved describes that deployment-time checkpoint. A later investigation found the PR19 original saved plan and deployed ZIP **MISSING**; the original damaged worktree was preserved without repair. Matthew accepts verified reconstructed PR19 source as **source-only evidence**, not recovery of the original `QgEdTeYYMYF3k+b4f22NoHv2I7GEowtO1ynQ7ISafVk=` package bytes.

The PR22 RC backend ZIP and saved plan, and the documented current admin rollback copies, passed offline checksum verification during the recovery checkpoint. This does not restore the missing PR19 rollback package, prove every historical rollback remains available, or constitute current production acceptance. No production operations occurred; deletion cause remains unproven. See [the source-only recovery closeout](pr19-historical-rc-source-reconstruction.md) for the precise integrity and retention status.
