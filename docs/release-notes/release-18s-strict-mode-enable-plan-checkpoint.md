# Release 18S: Strict Mode Enablement Plan and Terraform Plan-Only Checkpoint

**Status:** Plan Generated (Pending Approval)  
**Type:** Infrastructure / Security Hardening  
**Date:** 2026-06-26  

---

## 1. Goal

The goal of this release is to prepare the configuration changes needed to transition the application to strict multi-tenant resolution mode (`TENANT_RESOLUTION_MODE=multi`) for all backend Lambda functions. This change ensures that any incoming requests from Cognito users who do not have the `custom:company_id` claim configured will be blocked with a `403 Forbidden` (`PermissionError`) instead of silently falling back to the `"tog_and_dogs"` tenant.

This is a **plan-only checkpoint**. No changes are applied yet.

---

## 2. Proposed Changes

### A. Environment Configuration
The environment variable `TENANT_RESOLUTION_MODE` is set to `"multi"` across all 13 backend Lambda functions.

*   **Shared Environment Configuration:**
    *   [infra/prod/locals.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/infra/prod/locals.tf): Added `TENANT_RESOLUTION_MODE = "multi"` to `local.notification_env_vars` (shared by `intake`, `admin`, `review`, `assign`, and `cancellation`).
*   **Specific Lambda Configuration:**
    *   [infra/prod/main.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/infra/prod/main.tf): Explicitly added `TENANT_RESOLUTION_MODE = "multi"` to the environment variables map for the remaining 8 Lambdas:
        1.  `job`
        2.  `google_auth`
        3.  `pet`
        4.  `device`
        5.  `ses_feedback`
        6.  `postmark_webhook`
        7.  `stripe_webhook`
        8.  `platform`

---

## 3. Terraform Plan Summary

A plan has been successfully generated and saved to `infra/prod/release18s-strict-mode.tfplan`.

*   **Plan output:** `0 to add, 13 to change, 0 to destroy`
*   **Affected Resources:** In-place updates to environment variables for the 13 backend Lambda functions:
    *   `aws_lambda_function.admin`
    *   `aws_lambda_function.assign`
    *   `aws_lambda_function.cancellation`
    *   `aws_lambda_function.device`
    *   `aws_lambda_function.google_auth`
    *   `aws_lambda_function.intake`
    *   `aws_lambda_function.job`
    *   `aws_lambda_function.pet`
    *   `aws_lambda_function.platform`
    *   `aws_lambda_function.postmark_webhook`
    *   `aws_lambda_function.review`
    *   `aws_lambda_function.ses_feedback`
    *   `aws_lambda_function.stripe_webhook`

### Guardrail Audit
*   **Cognito changes:** None.
*   **DynamoDB table changes:** None.
*   **API Gateway changes:** None.
*   **Stripe / Postmark / webhook / payment changes:** None.
*   **Frontend / mobile / App Store / TestFlight changes:** None.
*   **Destructive changes:** None.

---

## 4. Rollback Plan

If strict mode is applied and results in unexpected data blocking or authorization errors:
1.  Revert `TENANT_RESOLUTION_MODE` to `"single"` in `infra/prod/locals.tf` and the 8 specific Lambda definitions in `infra/prod/main.tf`.
2.  Re-run `terraform apply`.
3.  This restores the compatibility mode fallback within 5 minutes, routing any requests without the company ID claim back to the `"tog_and_dogs"` default tenant.
4.  *Optional:* If any users still experience issues due to cached authorization tokens, they should log out and log back in to get a fresh Cognito token containing their `custom:company_id`.
