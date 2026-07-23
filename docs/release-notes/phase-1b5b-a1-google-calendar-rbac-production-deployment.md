# Phase 1B.5B-A.1: Google Calendar Integration RBAC Production Deployment Record

## 1. Deployment Metadata
* **Status:** ⏳ **DEPLOYED — AWAITING MATTHEW ROLE-BASED VALIDATION**
* **Deployment Date:** 2026-07-23
* **Implementation Commit:** `9e522473f4f20176fe8fe86f6ec1e5c107c7fad2`
* **Audit Commit:** `574aa4b3211a76c8c4a176865d448651c62f27ad`
* **Repository HEAD Used:** `014096437dc5d795cfdd8843711ae842157ede6e`
* **AWS Account:** `358604342897`
* **AWS Region:** `us-east-1`
* **SSO Profile:** `usmissionhero-website-prod`
* **S3 Hosting Bucket:** `s3://togs-and-dogs-prod-toganddogs-hosting`
* **CloudFront Distribution:** `E35L00QPA2IRCY`

---

## 2. Infrastructure Deployment Summary (Terraform & Backend)
* **Saved Plan Applied:** `infra/prod/phase-1b5b-a1-google-calendar-rbac.tfplan`
* **Terraform Apply Result:** `Apply complete! Resources: 0 added, 13 changed, 0 destroyed.`
* **Action Type:** In-place updates only (updates code package hashes for functions sharing `backend.zip`).
* **Destructive Actions:** None (0 additions, 0 replacements, 0 destroys).

### Updated Lambda Resources (13 Functions)
1. `aws_lambda_function.intake` (`togs-and-dogs-prod-intake`)
2. `aws_lambda_function.admin` (`togs-and-dogs-prod-admin`)
3. `aws_lambda_function.review` (`togs-and-dogs-prod-review`)
4. `aws_lambda_function.assign` (`togs-and-dogs-prod-assign`)
5. `aws_lambda_function.job` (`togs-and-dogs-prod-job`)
6. `aws_lambda_function.google_auth` (`togs-and-dogs-prod-google-auth`)
7. `aws_lambda_function.pet` (`togs-and-dogs-prod-pet`)
8. `aws_lambda_function.cancellation` (`togs-and-dogs-prod-cancellation`)
9. `aws_lambda_function.device` (`togs-and-dogs-prod-device`)
10. `aws_lambda_function.ses_feedback` (`togs-and-dogs-prod-ses-feedback`)
11. `aws_lambda_function.postmark_webhook` (`togs-and-dogs-prod-postmark-webhook`)
12. `aws_lambda_function.stripe_webhook` (`togs-and-dogs-prod-stripe-webhook`)
13. `aws_lambda_function.platform` (`togs-and-dogs-prod-platform`)

* **Unrelated Configuration Changes:** None. Zero modifications were made to DynamoDB, Cognito, IAM roles, API Gateway, Secrets Manager, Route 53 DNS records, or environment variables.

---

## 3. Frontend Web Assets Deployment (S3 & CloudFront)
* **S3 Hosting Target:** `s3://togs-and-dogs-prod-toganddogs-hosting`
* **Deployment Command:** `aws s3 sync dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod`
* **S3 Sync Result:** Completed successfully (Exit code: 0).
  * *Uploaded assets:* `index.html`, `assets/index-BkvaNs0X.js`, `assets/index-DTVmrIT-.css`, `assets/usmh-logo-CrRnxp7-.png`.
  * *Deleted stale assets:* `assets/index-B347XrXA.js`.
* **CloudFront Distribution:** `E35L00QPA2IRCY`
* **CloudFront Invalidation Command:** `aws cloudfront create-invalidation --distribution-id E35L00QPA2IRCY --paths "/*" --profile usmissionhero-website-prod`
* **Invalidation ID:** `I3DLKJ92IZXJ8FPDUEB8T1L7KV`
* **Invalidation Status:** `Completed` (Edge nodes successfully cleared and synchronized).

### Hashed Frontend Web Assets List
* `index.html` | `1,473` bytes | SHA256: `A841713ABDC374B3189B7A19201254DCCFCDC6EBD6753079AEE36348BC5524E0`
* `assets/index-BkvaNs0X.js` | `982,218` bytes | SHA256: `16CD559B7F337F9408FF4C5B48E38135F96D800C7954540BEFF886885D9F0FFC`
* `assets/index-DTVmrIT-.css` | `83,430` bytes | SHA256: `F5F8680BE3FD2F7065B994B5371A33873BA71CA065CE7D6DAFA5D1C97D352EDD`
* `assets/usmh-logo-CrRnxp7-.png` | `2,583,401` bytes | SHA256: `9C528F7EA13B41888E24CA434FF972604E9E0558E44F74AD1F10EC102282BA65`

---

## 4. Predeployment Validation Totals

### Frontend Tests
* **Total Passed:** **200**
* **Total Failed:** **0**
* **Total Skipped:** **0**
* **Total Errors:** **0**
* *Includes:* 96 legacy Node tests, 104 component tests (including 5 new GoogleCalendarRBAC tests).
* *Lint Status:* Changed files are lint-clean; baseline remains 49 errors and 9 warnings.

### Backend Tests
* **Total Collected:** **772**
* **Total Passed:** **703**
* **Total Failed:** **69** (Established repository baseline, 0 regressions)
* **Total Warnings:** **108**

---

## 5. Live Read-Only Public Verification
* **Public Frontpage Reachability:** Verified `https://d2nr4rfm2afckd.cloudfront.net` responds successfully.
* **HTML Reference Verification:** Verified index.html contains:
  `<script type="module" crossorigin src="/assets/index-BkvaNs0X.js"></script>`
  `<link rel="stylesheet" crossorigin href="/assets/index-DTVmrIT-.css">`
* **JavaScript Asset Loading:** Checked `/assets/index-BkvaNs0X.js` returns valid compiled script payload successfully (HTTP 200).

---

## 6. Access Control Safeguards Statement
* ❌ **No OAuth initiation or token generation was executed.**
* ❌ **No calendar connection, reconnection, or disconnection operations were run.**
* ❌ **No database modifications, Cognito alterations, or Stripe changes occurred.**

---

## 7. Rollback Procedures

### Frontend Rollback
1. Restore/check out the application source code from pre-remediation checkpoint `8efd153`.
2. Rebuild the frontend production assets from that pre-remediation source. (Note: The previously deployed frontend bundle set was `assets/index-B347XrXA.js` with its matching assets). Do not directly copy single JavaScript files without rebuilding the complete matching `dist` artifact set.
3. Sync the rebuilt pre-remediation `dist` directory to the target S3 bucket using the `aws s3 sync` command.
4. Invalidate the CloudFront CDN cache paths (`/*`) only after receiving explicit approval from Matthew.

### Backend Rollback
1. Restore/check out the application source code from pre-remediation checkpoint `8efd153`.
2. Rebuild the `backend.zip` package from that pre-remediation source.
3. Run a new Terraform plan (`terraform plan -out=rollback.tfplan`) to target the code hash reversion.
4. Review the generated rollback plan with Matthew and obtain separate explicit approval.
5. Execute `terraform apply "rollback.tfplan"` only after receiving explicit approval.

---

## 8. Matthew Role-Based Validation Checklist
Matthew should authenticate into the production dashboard with the appropriate roles to verify correct operation:

1. **Staff Role (`staff`) Verification**:
   * Log in to the scheduler as a sitter.
   * Verify the Master Scheduler displays visits and is responsive.
   * Go to the Integration card/banner. Confirm the connection status reads "Needs Reconnect" or "Not Connected" but the **Connect Calendar** / **Reconnect Calendar** buttons are **completely hidden**.
2. **Owner Role (`owner` / `admin`) Verification**:
   * Log in to the dashboard as an owner/admin.
   * Verify that the **Connect Calendar** / **Reconnect Calendar** action buttons are visible and active.
3. **API Access Control Verification**:
   * Confirm that any direct API invocation of `/admin/auth/google` (initiate) or `/admin/auth/google` (disconnect) using a non-owner/non-admin JWT token returns a `403 Forbidden` response.
