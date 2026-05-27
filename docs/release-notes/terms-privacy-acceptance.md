# Release Notes: Terms and Privacy Acceptance (Phase 1)

## Overview

We have introduced explicit Terms of Use and Privacy Policy acceptance for all new public service requests to ensure compliance and maintain a clear record of customer consent.

## User-Facing Behavior Changes

- **New Policy Pages**: The terms of use and privacy policy are now accessible via dedicated `/terms` and `/privacy` pages.
- **Footer Links**: The footer links for "Privacy Policy" and "Terms of Service" now correctly navigate to the new policy pages instead of the home page.
- **Intake Form Checkbox**: When submitting a public service request, users must now check an "I agree to the Terms of Use and acknowledge the Privacy Policy" checkbox on the final step. Submission is blocked if unchecked.
- **Admin Visibility**: Admins reviewing requests in the portal will now see a new "Terms & Privacy" section in the CareCard overview, showing the acceptance status, version, and timestamp.

## Testing Checklist

- [x] **Frontend validation**: The intake form submit button is disabled when the checkbox is unchecked, and enabled when checked.
- [x] **Backend validation**: The backend rejects public intake submissions (`CUSTOMER_INTAKE`) if acceptance fields are missing or invalid, returning a 400 Bad Request.
- [x] **Acceptance record storage**: Valid submissions store `accepted_terms`, `accepted_privacy`, `terms_version`, `privacy_version`, `accepted_at`, and `accepted_by_email` in DynamoDB.
- [x] **Admin dashboard visibility**: The CareCard displays the acceptance metadata correctly for new records, and shows "Not recorded" for legacy records without crashing.
- [x] **Footer link navigation**: The footer links successfully navigate to the new `/terms` and `/privacy` pages.

## Rollback Procedure

If issues are detected:
1. **Backend**: Revert the `intake_handler` Lambda to the previous version to stop enforcing validation.
2. **Frontend**: Revert the frontend S3 deployment to the previous version and invalidate the CloudFront cache to remove the checkbox.
3. **Data**: No data deletion is required; any additive fields stored during the rollout will be safely ignored by the reverted code.

## Terraform Drift Note

Because local Terraform binaries were missing from the system PATH during deployment, the `togs-and-dogs-prod-intake` Lambda function was updated directly via the AWS CLI (`aws lambda update-function-code`).

**Follow-up action required:** Before the next backend infrastructure apply, developers must reconcile the Terraform state (specifically the `source_code_hash` for the intake lambda) to prevent Terraform from attempting to downgrade the lambda function. This can be resolved by packaging the code into `backend.zip` natively or refreshing the state.
