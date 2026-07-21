# Release Notes: Phase 1B.4A–E — Client Drawer Frontend Production Deployment

**Date:** 2026-07-21 (UTC)
**Status:** ✅ FRONTEND DEPLOYED — AUTHENTICATED VALIDATION PENDING MATTHEW
**Type:** Frontend-only production deployment (React/Vite)

---

## 1. Summary of Actions Taken

This release documents the successful deployment of Phase 1B.4A–E Client Drawer Editor Consolidation frontend build to the existing production hosting environment.

The following operations were completed:
1.  **Repository State Verification**: Checked HEAD at `83ce27a` (final Kiro review). Verified branch `main`, clean working tree, empty stash, and `origin/main` alignment.
2.  **Application Delta Review**: Verified the application source delta between the previously deployed hotfix commit `925edda` and current HEAD `83ce27a` is strictly limited to Phase 1B.4A–E client drawer consolidation. Confirmed no `web/src` changes occurred after `9248de0`.
3.  **AWS Profile & Identity Verification**: STS caller identity checked on profile `usmissionhero-website-prod`. Region confirmed as `us-east-1`, production S3 bucket and CloudFront distribution verified.
4.  **Local Build & Test Validation**:
    *   Legacy tests: **96 passed** / 0 failed.
    *   Component tests: **73 passed** / 0 failed.
    *   Total: **169 passed** / 0 failed.
    *   Linter: Verified clean code (project baseline remains at 52 errors, 10 warnings).
    *   Vite Build: Succeeded cleanly, transforming 107 modules.
5.  **Static Artifact Generation**: Fresh assets verified in `web/dist` (no source maps, credentials, or fixtures present).
6.  **S3 Sync Deployment**: Deployed `web/dist/` to `s3://togs-and-dogs-prod-toganddogs-hosting` (superseded bundle `index-BnpMcuCZ.js` deleted).
7.  **CloudFront Invalidation**: Invalidated `/*` on distribution `E35L00QPA2IRCY` (completed successfully).
8.  **Public Route Availability Check**: Performed unauthenticated fetches to all deep-links; confirmed they serve the new index body and point to the newly compiled bundle `index-B-lRTVkt.js`.

---

## 2. Scope & Behavioral Changes

*   **Client Details Drawer Consolidation**: The right-side slide-out drawer (`ClientDetailDrawer`) is now the single source of truth for both reading and writing client profiles, adopting the UX flow from the Staff drawer.
*   **Retirement of Inline Editor**: The duplicate large inline client creation/edit forms previously occupying the top of the Client Management screen have been fully retired and removed.
*   **Unsaved-Change Protection**: Closing or canceling a dirty drawer via the close button, Escape key, or clicking the background overlay triggers a browser discard confirmation modal.
*   **Create Mode**: Opening the drawer in create mode initializes empty defaults, supports creation mode selector (onboard invitation vs profile-only), and enforces email presence for invitation mode.
*   **Guardrails Preserved**: Cognito invitation links, temporary password setup, password reset triggers, and account activation/deletion controls remain wired correctly. Destructive actions are disabled for protected profiles.

---

## 3. AWS Targets & Profiles

- **AWS Account:** `358604342897` (assumed role: `AWSReservedSSO_AdministratorAccess`)
- **AWS Region:** `us-east-1`
- **S3 Hosting Bucket:** `togs-and-dogs-prod-toganddogs-hosting`
- **CloudFront Distribution ID:** `E35L00QPA2IRCY`
- **Distribution Domain:** `d2nr4rfm2afckd.cloudfront.net`
- **Public Domain Name:** `https://toganddogs.usmissionhero.com`

---

## 4. Deployment Artifacts Metadata

| File Name | Size (Bytes) | SHA256 Hash |
| :--- | :--- | :--- |
| `index.html` | 1473 | `2a69dd69f2ba2a475df10a90160b03b00b4a55f563c76cd40bd73e2860f03a90` |
| `assets/index-B-lRTVkt.js` | 970479 | `5b38f0792bed5c92cd0c3296b459e6dd81e67fc7ace6ebd1b745e2cce068cbce` |
| `assets/index-CRQyBP3J.css` | 83302 | `fcacbfb9194c8e5989180c3b8e71620cdc53f45f031cbef044f44e7eeebb140a` |
| `sw.js` | 931 | `c380be95e881562faff0632c7081d4a6a19da5c2730261538b846c36f69f4e57` |
| `manifest.webmanifest` | 695 | `2839a8915a522cb4d386241c4e4dcce5d21de7116b60fc06820ca0fff04cb5e9` |

---

## 5. Invalidation Details

- **Invalidation ID:** `ID5H1L9JROIZ8HW96F6VU2CLQ3`
- **Invalidation Path:** `/*`
- **Create Time:** `2026-07-21T19:08:25.894Z`
- **Final Status:** `Completed`

---

## 6. Public Availability Checks (Unauthenticated)

Programmatic fetch checks were executed against all deep links:

| Route | HTTP Status | Content-Type | Content-Length | Body SHA256 | X-Cache | Matched JS Bundle |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | 200 | `text/html` | 1473 | `2a69dd6...` | `Hit from cloudfront` | `index-B-lRTVkt.js` |
| `/admin` | 200 | `text/html` | 1473 | `2a69dd6...` | `Error from cloudfront` | `index-B-lRTVkt.js` |
| `/admin/` | 200 | `text/html` | 1473 | `2a69dd6...` | `Error from cloudfront` | `index-B-lRTVkt.js` |
| `/index.html` | 200 | `text/html` | 1473 | `2a69dd6...` | `Hit from cloudfront` | `index-B-lRTVkt.js` |

*Unauthenticated verification confirms that all route fallbacks return `200 OK` and serve the correct index payload referencing the new Phase 1B.4A-E JavaScript bundle.*

---

## 7. Project Integrity & Safety Verification

*   **No AWS Infrastructure Mutation**: CloudFront behaviors, S3 bucket settings, Route 53 records, or certificate configurations were not altered.
*   **No Backend Changes**: No Lambda packages, API Gateway endpoints, or DynamoDB tables were updated.
*   **No Auth Writes**: No user password resets or pool updates were made in Cognito.
*   **No Stripe or Google Calendar Mutation**: Safe from sandbox or production API side-effects.
*   **No Tenant Changes**: No second tenants created or configured.
*   **No Mobile Distribution Changes**: No App Store or TestFlight action taken.
*   **No Ryan Testing**: Verification scoped to isolated local automated/unauthenticated checks.

---

## 8. Next Gate: Authenticated Validation by Matthew

The Phase 1B.4A–E client drawer consolidation is successfully deployed. The status is updated:
- **Phase 1B.4 Status**: Deployed $\rightarrow$ **Awaiting Matthew Authenticated Admin Smoke Test**
- **Latest Completed Release**: Remains Phase 1B.3 until validation passes.
- **Phase 1B.4F–H**: Remain deferred to a later release.

Matthew must sign in to the Staff Portal on `/admin` and verify:
1.  **Client Management**: Selecting a client profile card opens the side drawer in View mode.
2.  **View Details**: Selecting the view details button opens View mode.
3.  **Edit Profile**: Transitions View to Edit mode. Cancel/close alerts if modified; save updates state.
4.  **Add New Client**: Opens the drawer in Create mode.
5.  **Staff Management**: Unchanged.
