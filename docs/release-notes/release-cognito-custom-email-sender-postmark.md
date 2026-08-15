# Cognito Custom Email Sender + Postmark

## 1. Status

- **Status:** ✅ **LOCAL IMPLEMENTATION COMPLETE / NOT DEPLOYED**
- **Date:** 2026-08-15
- **Starting checkpoint:** `d670127fbe4309a9a88b550f6c0a697942f1984f`
- **Production status:** Existing Cognito default email remains active; no AWS resource or configuration in this note has been deployed.

This candidate replaces generic Cognito password-recovery delivery with a branded Postmark message while preserving Cognito as the authority for code generation, code validation, and password reset completion. It is local repository work only and requires independent review plus a separate, explicit production-deployment approval.

## 2. Architecture

The bounded design is:

```text
Amazon Cognito ForgotPassword
  -> CustomEmailSender_ForgotPassword event
  -> dedicated Cognito email sender Lambda
  -> AWS Encryption SDK decrypts the Cognito code envelope
  -> Postmark /email API
  -> customer password-reset email
```

The sender source is isolated in `src/cognito_email_sender`. It is not under `src/backend`, whose archive is shared by the existing Lambda fleet. The Terraform resource points only to the dedicated `cognito-email-sender.zip`; no existing backend Lambda package, handler, role, or source hash is changed by the new sender artifact.

## 3. Cognito and KMS Configuration

The auth module accepts the sender Lambda ARN and KMS key ARN together and configures:

- `lambda_config.custom_email_sender`
- `lambda_version = "V1_0"`
- `lambda_config.kms_key_id`
- a Cognito service-principal Lambda invocation permission scoped to the existing user-pool ARN and workload account

Terraform defines a dedicated customer-managed `SYMMETRIC_DEFAULT` KMS key, automatic key rotation, a 30-day deletion window, and alias `alias/<name-prefix>-cognito-email-sender`.

Per the AWS Cognito Custom Sender model, the IAM principal that creates or updates the user pool must have `kms:CreateGrant` permission. The standard account-root key-policy delegation permits an appropriately authorized workload-account deployment role to create the Cognito grant. Selecting and verifying that deployment principal remains a production deployment prerequisite; no grant was created locally.

The Lambda role has `kms:Decrypt` only for the dedicated key, restricted to a Cognito `userpool-id` encryption context in the configured region. The handler also verifies that the authenticated encryption context's exact `userpool-id` matches the invoking event before using the plaintext code.

## 4. Isolated Dependency Package

`scripts/build_cognito_email_sender_package.py` constructs the dedicated package from:

- `src/cognito_email_sender/cognito_email_sender_handler.py`
- `src/cognito_email_sender/requirements.lock`

All deployment dependencies are pinned, including `aws-encryption-sdk==4.0.6`. The builder requests Python 3.11 `manylinux2014_x86_64` wheels, installs them in a temporary staging directory, removes deployment-irrelevant host console launchers and generated `RECORD` metadata, copies only the dedicated handler, and writes files in sorted order with normalized ZIP timestamps and permissions. The ignored local output is:

`artifacts/cognito-email-sender/cognito-email-sender.zip`

Terraform fails before plan/apply if the isolated package does not exist and hashes it when present. The package was built locally to validate dependency resolution. It was not uploaded or deployed.

## 5. Dedicated Least-Privilege IAM

The Lambda execution role permits only:

- `logs:CreateLogStream` and `logs:PutLogEvents` for its pre-created log group
- `secretsmanager:GetSecretValue` for the existing Postmark server-token secret ARN
- `kms:Decrypt` for the dedicated code-envelope KMS key and Cognito encryption context

It has no DynamoDB, Cognito administrator, SES, SNS, Step Functions, Stripe, Google Calendar, unrelated Lambda invocation, or broad existing backend-role access.

The KMS key policy necessarily uses `Resource = "*"` because resource references in a KMS key policy identify the key to which the policy is attached. The Lambda's identity policy remains exact-key scoped. The account-root `kms:*` statement is the standard key-administration/delegation statement, not a Lambda runtime permission.

## 6. Handler Behavior

Only `CustomEmailSender_ForgotPassword` with event version `1` is supported. The handler validates the event, encrypted code, user-pool identifier, and a single recipient email before decryption or delivery. All other triggers fail closed and make no Postmark request.

The code is base64-decoded and decrypted with the AWS Encryption SDK using `REQUIRE_ENCRYPT_ALLOW_DECRYPT`; raw `boto3 kms.decrypt` is not used. The decrypted code exists in memory only, is context-bound to the invoking user pool, and is never logged.

The Postmark request uses:

- **From:** `Togs & Dogs <support@usmissionhero.com>`
- **Reply-To:** `support@usmissionhero.com`
- **Subject:** `Togs & Dogs — Your password reset code`
- **Message stream:** `outbound`
- lightweight HTML and matching plain-text bodies

No reset link, customer-email echo, username, password, or unrelated user attribute is included. Credential retrieval, decrypt, malformed event, recipient validation, HTTP/transport, invalid response, and Postmark rejection failures all raise safely. Logs contain only safe trigger and exception-type metadata; exception text and raw events are omitted.

## 7. Validation

- Focused sender and infrastructure tests: **27/27 passed**
- Stable sender + notification regression set: **216/216 passed**
- Broader notification-linked set: **206 passed / 11 failed**
  - Archived clean `d670127` baseline: **the same 206 passed / 11 failed**
  - The 11 unchanged failures are legacy tenant-status/payment-fixture failures; the candidate introduces none.
- Full backend candidate: **862 passed / 97 failed**
- Archived clean `d670127` full backend baseline: **835 passed / 97 failed**
  - The candidate adds 27 passing tests and exactly zero new full-suite failures.
- Isolated Linux package build: **PASS**; two consecutive builds produced the same SHA-256 (`3c7fa3cde634ead0e7ad4543c8cdc6c85f5a90024ca154d462bb80d4aaba8213`)
- Terraform format check for all changed Terraform: **PASS**
- Terraform validation from `infra/prod`: **PASS**
- `git diff --check`: **PASS** at local closeout

All sender tests use mocks. No real Cognito or Postmark call was made.

## 8. Static Security Review

Candidate scans found:

- no decrypted-code, encrypted-code, token, password, JWT/session, raw-event, or private-attribute logging
- no hardcoded Postmark token or secret value
- no SES permission or SES delivery implementation
- no DynamoDB, SNS, Cognito admin, Calendar, Stripe, or unrelated Lambda permission
- exact Postmark secret and KMS key resources in the Lambda identity policy
- only the documented KMS key-policy `Resource = "*"` semantics and standard account key-administration statement
- no `.tfvars`, `.tfplan`, generated log, credential, or package ZIP tracked by the candidate

## 9. Deployment Gate

Before any separately approved deployment:

1. independently review this local candidate;
2. build and hash the isolated package in the approved release environment;
3. verify the exact Terraform apply principal can create the Cognito KMS grant;
4. review an approved Terraform plan, including confirmation that the existing backend Lambda functions are unchanged;
5. obtain Matthew's explicit approval for Terraform apply and production validation;
6. after deployment, perform a separately approved controlled Forgot Password delivery test without exposing the code or token.

No Terraform plan or apply, Lambda upload, Cognito update, KMS grant, Postmark message, password-reset request, frontend/backend deployment, Preview V1 deployment, Phase 24A deployment, SES change, tenant change, or production write occurred in this implementation.

**Disposition:** `COGNITO_POSTMARK_LOCAL_IMPLEMENTATION_READY_FOR_REVIEW`
