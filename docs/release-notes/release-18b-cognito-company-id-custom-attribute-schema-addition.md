# Release 18B: Cognito Company ID Custom Attribute Schema Addition Implementation

**Status:** ✅ Completed  
**Type:** Infrastructure / Cognito Schema / Verification  
**Date:** 2026-06-23  
**Baseline:** Release 18A (`f4c1487`)

---

## 1. Context

During the 17Z manual Cognito review, it was identified that the `custom:company_id` custom attribute did not exist in the Cognito user pool schema. This schema addition is a critical pre-requisite for:
1. Backfilling existing users with the `custom:company_id` attribute (Release 18C).
2. Running the application in strict `multi` tenant resolution mode (Release 18F).
3. Onboarding a second tenant safely.

Release 18B adds the `custom:company_id` custom attribute schema safely via Terraform and updates the Cognito app client read/write attributes.

---

## 2. Files Created / Modified

| File | Action | Description |
|---|---|---|
| [modules/auth/main.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/modules/auth/main.tf) | 📝 Modified | Added `company_id` to schema and updated app client read/write attributes. |
| [docs/release-notes/release-18b-cognito-company-id-custom-attribute-schema-addition.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/release-notes/release-18b-cognito-company-id-custom-attribute-schema-addition.md) | 🆕 Created | This release notes document. |
| [docs/release-notes/index.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/release-notes/index.md) | 📝 Modified | Registered Release 18B in the index. |
| [docs/backlog/saas-maturity-and-multi-business-owner-readiness.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/backlog/saas-maturity-and-multi-business-owner-readiness.md) | 📝 Modified | Updated the status of Cognito `custom:company_id` enforcement item #5. |

---

## 3. Implementation Details

### User Pool Schema
The Cognito User Pool is Terraform-managed. The `custom:company_id` custom attribute was safely added to the schema:
- **Attribute Name:** `company_id` (accessible via claim `custom:company_id` in JWTs)
- **Data Type:** `String`
- **Mutable:** `true` (enables admin/manual backfill)
- **Required:** `false` (does not break existing users who lack the attribute)
- **Constraints:** `min_length = 1`, `max_length = 64`

### App Client Attribute Permissions
To prevent security issues where normal users could assign/change their own tenant via app client self-service APIs (`UpdateUserAttributes`), client read/write permissions were updated:
- **Read Attributes:** Includes `custom:company_id` (so it appears in user JWTs after authentication).
- **Write Attributes:** Excludes `custom:company_id` (self-service write is blocked).

---

## 4. Terraform Summary

- **Command Run:** `terraform apply -auto-approve` in `infra/prod`
- **Plan Result:** `Plan: 0 to add, 2 to change, 0 to destroy`
- **Apply Result:** Safe in-place update completed successfully for:
  1. `module.auth.aws_cognito_user_pool.admin`
  2. `module.auth.aws_cognito_user_pool_client.admin_client`

---

## 5. Verification

### User Pool Custom Schema Verification
AWS CLI command:
```bash
aws cognito-idp describe-user-pool --user-pool-id us-east-1_counlsXGU --profile usmissionhero-website-prod --region us-east-1 --query "UserPool.SchemaAttributes[?Name=='custom:company_id']"
```
**Output:**
```json
[
    {
        "Name": "custom:company_id",
        "AttributeDataType": "String",
        "DeveloperOnlyAttribute": false,
        "Mutable": true,
        "Required": false,
        "StringAttributeConstraints": {
            "MinLength": "1",
            "MaxLength": "64"
        }
    }
]
```

### App Client Read/Write Verification
AWS CLI command:
```bash
aws cognito-idp describe-user-pool-client --user-pool-id us-east-1_counlsXGU --client-id 1u4t7rfo339nkcgaf6q8s8sc6u --profile usmissionhero-website-prod --region us-east-1 --query "UserPoolClient.[ReadAttributes, WriteAttributes]"
```
**Output:**
```json
[
    [
        "custom:company_id",
        "email",
        "email_verified",
        "family_name",
        "gender",
        "given_name",
        "locale",
        "middle_name",
        "name",
        "nickname",
        "phone_number",
        "phone_number_verified",
        "picture",
        "preferred_username",
        "updated_at",
        "website",
        "zoneinfo"
    ],
    [
        "email",
        "family_name",
        "gender",
        "given_name",
        "locale",
        "middle_name",
        "name",
        "nickname",
        "phone_number",
        "picture",
        "preferred_username",
        "updated_at",
        "website",
        "zoneinfo"
    ]
]
```

---

## 6. Test Suite Results

All targeted and regression tests passed successfully:
- `tests/backend/test_r17w_company_id_resolution.py` — **33/33 Passed**
- `tests/backend/test_r17w_tenant_provisioning.py` — **46/46 Passed**
- `tests/backend/test_r17l_platform_admin.py` — **12/12 Passed**
- Full backend suite (`tests/backend`) — **533/533 Passed**

---

## 7. Operational Guardrails Verification

- **No Cognito users, groups, passwords, or user attributes were modified**.
- **No users were backfilled**.
- **`TENANT_RESOLUTION_MODE=multi` was not enabled** (continues to default to `single` compatibility mode).
- **No second tenant was created**.
- **No DynamoDB writes, tenant metadata changes, frontend/mobile deployment, Stripe, Postmark, TestFlight, App Store Connect, Ryan/tester, payment/email/SMS, or live key changes occurred**.

---

## 8. Recommended Next Release

**Release 18C: Manual Cognito User Company ID Backfill Closeout**
- Backfill all production users by setting `custom:company_id = tog_and_dogs` using AWS CLI/tooling.
- Monitor fallback metrics to confirm they drop to zero before transitioning to strict mode.
