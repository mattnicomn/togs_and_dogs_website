# Phase 1B.5B-A.1: Google Calendar Integration RBAC Deployment Readiness

## 1. Deployment Readiness Metadata
* **Status:** 🔴 **READY FOR MATTHEW DEPLOYMENT DECISION / NOT DEPLOYED**
* **Implementation Commit:** `9e522473f4f20176fe8fe86f6ec1e5c107c7fad2`
* **Audit Commit:** `574aa4b3211a76c8c4a176865d448651c62f27ad`
* **AWS Account:** `358604342897`
* **AWS Region:** `us-east-1`
* **SSO Profile:** `usmissionhero-website-prod`
* **S3 Hosting Bucket:** `s3://togs-and-dogs-prod-toganddogs-hosting`
* **CloudFront Distribution:** `E35L00QPA2IRCY`

---

## 2. Access Control Specification
* **Allowed Roles (Mutations):** `owner`, `admin`
* **Denied Roles (Mutations):** `staff`, `client`, `platform_admin`, `unknown`
* **Read-only Status Visibility:** `staff` role retains read-only status and health alert visibility on both the frontend and backend.

---

## 3. Predeployment Test & Lint Verification

### Frontend Tests
* **Total Passed:** **200**
* **Total Failed:** **0**
* **Total Skipped:** **0**
* **Total Errors:** **0**
* *Includes:* 96 legacy Node tests, 104 component tests (including 5 new GoogleCalendarRBAC tests).
* *Lint Status:* 100% clean for changed files.

### Backend Tests
* **Total Collected:** **772**
* **Total Passed:** **703**
* **Total Failed:** **69** (Established repository baseline, 0 regressions)
* **Total Warnings:** **108**
* *Includes:* 3 focused Google Calendar RBAC tests, 40 callback/token/tenant-isolation tests.

---

## 4. Backend Package Audit
* **Package Path:** `infra/prod/backend.zip`
* **Size:** `133,147` bytes
* **SHA-256 Hex Hash:** `99883CB568080D0C88C0B666284C68FF9807F30EFFBD5DC4C1C27B7D21CD1373`
* **SHA-256 Base64 Hash:** `mYg8tWgIDQyIwLZmKExo/5gH8w7/vV3EwcJ7fSHNE3M=`
* **Top-Level Directory Listing:**
  * `common/` (modules: `audit`, `auth`, `billing`, `db`, `email`, `entitlement`, `google_calendar`, `protected_accounts`, `stripe_client`, etc.)
  * `handlers/` (lambda entrypoints: `admin_handler`, `assignment_handler`, `google_auth_handler`, `intake_handler`, `pet_handler`, etc.)
* **Exclusions Check:** verified no test suites, documentation, terraform plans, credentials, log files, caches, or agent-local scratch files are packaged.

---

## 5. Terraform Plan Summary
* **Plan Saved To:** `infra/prod/phase-1b5b-a1-google-calendar-rbac.tfplan`
* **Actions:** **0 to add, 13 to change, 0 to destroy** (In-place updates only)
* **Attribute Changes:** Updates the `source_code_hash` and `last_modified` fields of the 13 Lambda resources sharing `backend.zip`.

### Affected Resources (13 Lambda Functions)
1. `aws_lambda_function.intake` (`togs-and-dogs-prod-intake`) — Code update
2. `aws_lambda_function.admin` (`togs-and-dogs-prod-admin`) — Code update
3. `aws_lambda_function.review` (`togs-and-dogs-prod-review`) — Code update
4. `aws_lambda_function.assign` (`togs-and-dogs-prod-assign`) — Code update
5. `aws_lambda_function.job` (`togs-and-dogs-prod-job`) — Code update
6. `aws_lambda_function.google_auth` (`togs-and-dogs-prod-google-auth`) — Code update
7. `aws_lambda_function.pet` (`togs-and-dogs-prod-pet`) — Code update
8. `aws_lambda_function.cancellation` (`togs-and-dogs-prod-cancellation`) — Code update
9. `aws_lambda_function.device` (`togs-and-dogs-prod-device`) — Code update
10. `aws_lambda_function.ses_feedback` (`togs-and-dogs-prod-ses-feedback`) — Code update
11. `aws_lambda_function.postmark_webhook` (`togs-and-dogs-prod-postmark-webhook`) — Code update
12. `aws_lambda_function.stripe_webhook` (`togs-and-dogs-prod-stripe-webhook`) — Code update
13. `aws_lambda_function.platform` (`togs-and-dogs-prod-platform`) — Code update

> [!WARNING]
> Confirmed **zero** changes to DynamoDB, Cognito, IAM roles, API Gateway integrations, Route 53 DNS records, Secrets Manager, environment variables, or event rules.

---

## 6. Frontend Production Build Details
* **Build Directory:** `web/dist/`
* **Generated Asset Files & Hashes:**
  * `index.html` | `1,473` bytes | SHA256: `A841713ABDC374B3189B7A19201254DCCFCDC6EBD6753079AEE36348BC5524E0`
  * `assets/index-BkvaNs0X.js` | `982,218` bytes | SHA256: `16CD559B7F337F9408FF4C5B48E38135F96D800C7954540BEFF886885D9F0FFC`
  * `assets/index-DTVmrIT-.css` | `83,430` bytes | SHA256: `F5F8680BE3FD2F7065B994B5371A33873BA71CA065CE7D6DAFA5D1C97D352EDD`
  * `assets/usmh-logo-CrRnxp7-.png` | `2,583,401` bytes | SHA256: `9C528F7EA13B41888E24CA434FF972604E9E0558E44F74AD1F10EC102282BA65`

---

## 7. Proposed Deployment Commands

### Backend Infrastructure
```bash
# Executed in infra/prod/
terraform apply "phase-1b5b-a1-google-calendar-rbac.tfplan"
```

### Frontend Assets
```bash
# Executed in web/
aws s3 sync dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete \
  --profile usmissionhero-website-prod

aws cloudfront create-invalidation \
  --distribution-id E35L00QPA2IRCY \
  --paths "/*" \
  --profile usmissionhero-website-prod
```

---

## 8. Rollback Procedures

### Frontend Rollback
1. Re-sync the previous production build (`assets/index-B347XrXA.js`) to S3.
2. Invalidate the CloudFront cache.

### Backend Rollback
1. Checkout the previous commit (`574aa4b`).
2. Run `terraform plan -out=rollback.tfplan` and execute `terraform apply` to restore the original Lambda package hashes.

---

## 9. Separate Approval Gates
* [ ] **Gate 1:** Authorize `terraform apply` for Lambda code package updates.
* [ ] **Gate 2:** Authorize S3 sync of frontend assets.
* [ ] **Gate 3:** Authorize CloudFront CDN cache invalidation.
