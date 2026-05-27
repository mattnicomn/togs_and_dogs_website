# Implementation Plan: Terms and Privacy Acceptance (Phase 1)

This plan documents the implementation of the Terms of Use and Privacy Policy acceptance feature for public intake submissions.

## Deployable Changes

1. **Constants**: Added `TERMS_VERSION` and `PRIVACY_VERSION` (v1.0) and policy content to `web/src/constants/policy.js`.
2. **Pages**: Created `/terms` and `/privacy` routes using new `TermsOfUse.jsx` and `PrivacyPolicy.jsx` components.
3. **Footer Links**: Updated footer to link to the new pages.
4. **Intake Form**: Added an acceptance checkbox to step 3. The submit button is disabled unless checked. Added acceptance metadata fields to the submission payload.
5. **CareCard**: Added a "Terms & Privacy" read-only section to the overview tab to display acceptance status and timestamps to admins. Legacy records gracefully show "Not recorded".
6. **Backend Validation**: `src/backend/handlers/intake_handler.py` validates that `CUSTOMER_INTAKE` submissions include valid acceptance fields.
7. **Data Persistence**: Added persistence of `accepted_terms`, `accepted_privacy`, `terms_version`, `privacy_version`, `accepted_at`, `accepted_by_email`, and `source` to the DynamoDB request item.

## Deployment Order (CRITICAL)

1. **Frontend Update**: Deploy the frontend bundle first. At this point, the frontend will start sending the acceptance fields, and the backend will simply store them (DynamoDB is schema-less). No validation is enforced yet.
2. **Backend Update**: Deploy the updated Lambda handler. Now the backend enforces that `CUSTOMER_INTAKE` submissions include valid acceptance fields.

**Why this order matters**: If the backend is deployed first, all public intake submissions will be rejected because the frontend isn't sending the required fields yet.

## Inter-Component Dependencies

- Frontend `IntakeForm.jsx` depends on `constants/policy.js`.
- Backend `intake_handler.py` depends on the frontend sending the new `accepted_*` and `*_version` fields for public `CUSTOMER_INTAKE` requests.

## Rollback Notes

- **Backend**: Redeploy the previous Lambda version. Prior versions will ignore the acceptance fields.
- **Frontend**: Revert the S3 bundle and invalidate CloudFront. The form will stop displaying the checkbox and stop sending the payload.
- **Data**: No rollback needed. Additive DynamoDB fields will be safely ignored by old code.
