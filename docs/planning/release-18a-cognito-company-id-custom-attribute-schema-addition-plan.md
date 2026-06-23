# Release 18A: Cognito Company ID Custom Attribute Schema Addition Plan

**Status:** Planning
**Date:** 2026-06-22
**Priority:** High (unblocks user backfill → strict mode → second tenant)
**Scope:** Design safe addition of `custom:company_id` to Cognito user pool schema

---

## 1. Context

During the 17Z manual Cognito review, Matthew confirmed that `custom:company_id` does not exist on the user pool schema. This means:
- No user currently has this attribute
- The attribute must be added to the pool schema before it can be set on users
- Without it, the `TENANT_RESOLUTION_MODE=multi` strict mode cannot be safely enabled

---

## 2. Recommended Attribute Design

| Property | Value | Rationale |
|----------|-------|-----------|
| **Attribute name** | `company_id` | Results in claim `custom:company_id` in JWT |
| **Data type** | String | Matches company_id slug format |
| **Mutable** | Yes | Must be settable by admin CLI/tooling for backfill |
| **Required** | No | Existing users don't have it yet; cannot enforce required retroactively |
| **Min length** | 1 | Non-empty when set |
| **Max length** | 64 | Sufficient for slugs like `tog_and_dogs`, `paws_and_claws_nyc` |
| **Expected values** | Lowercase slugs: `tog_and_dogs`, `test_tenant_alpha`, etc. | Consistent with DynamoDB company_id pattern |

### Important: Immutable vs Mutable

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| Mutable | Admin can fix mistakes, backfill existing users | User could theoretically self-edit if app client allows writes | ✅ **Recommended** — restrict via app client permissions |
| Immutable | Cannot be changed after set — strongest isolation | Cannot fix mistakes without recreating user | ❌ Too rigid for MVP |

**Decision: Mutable** — but restrict write access via app client configuration so normal users cannot self-edit.

---

## 3. Implementation Method Evaluation

| Method | Safety | Drift Risk | Repeatability | Recommendation |
|--------|--------|-----------|---------------|----------------|
| **Terraform** (if pool is Terraform-managed) | ✅ | ✅ Low (stays in state) | ✅ | ✅ **Preferred** |
| AWS Console (manual) | ⚠️ | ⚠️ High (Terraform doesn't know) | ❌ | ⚠️ Only if Terraform not managing schema |
| AWS CLI (`add-custom-attributes`) | ⚠️ | ⚠️ High (Terraform drift) | ✅ | ⚠️ Same drift issue as Console |

### Recommendation: Check Terraform State First

The existing Cognito user pool is created via `modules/auth/`. If Terraform manages the pool schema:
- **Add the custom attribute in Terraform** → `terraform plan` shows schema addition → `terraform apply`
- This prevents drift and keeps infrastructure-as-code consistent

If Terraform does NOT manage individual schema attributes (only the pool resource):
- AWS CLI `add-custom-attributes` is acceptable
- Document the change for future Terraform reconciliation

### Terraform Example (if applicable)

```hcl
resource "aws_cognito_user_pool" "admin" {
  # ... existing config ...

  schema {
    name                = "company_id"
    attribute_data_type = "String"
    mutable             = true
    required            = false

    string_attribute_constraints {
      min_length = 1
      max_length = 64
    }
  }
}
```

### AWS CLI Example (if Terraform doesn't manage schema)

```powershell
aws cognito-idp add-custom-attributes ^
  --user-pool-id <POOL_ID> ^
  --custom-attributes Name=company_id,AttributeDataType=String,Mutable=true,StringAttributeConstraints="{MinLength=1,MaxLength=64}" ^
  --profile usmissionhero-website-prod
```

---

## 4. App Client Token/Permission Requirements

### Token Inclusion

For `custom:company_id` to appear in the JWT token:
- The attribute must be **readable** by the app client
- Check app client settings: `ReadAttributes` should include `custom:company_id`
- After a user gets the attribute set and re-authenticates, the claim appears in the ID token

### Write Permission Control

| Setting | Recommendation | Reason |
|---------|---------------|--------|
| App client `ReadAttributes` | ✅ Include `custom:company_id` | Backend needs to read it from JWT |
| App client `WriteAttributes` | ❌ Do NOT include `custom:company_id` | Normal users must not self-assign their tenant |

**Critical:** If `custom:company_id` is in `WriteAttributes`, any authenticated user could call `UpdateUserAttributes` and change their own tenant assignment. This would bypass all isolation.

### Terraform App Client Example

```hcl
resource "aws_cognito_user_pool_client" "admin_client" {
  # ... existing config ...

  read_attributes  = [..., "custom:company_id"]
  # write_attributes should NOT include "custom:company_id"
}
```

### Verification After Implementation

- User logs in → inspect ID token → `custom:company_id` claim is present (after backfill)
- User attempts `UpdateUserAttributes` with `custom:company_id` → should be rejected by Cognito

---

## 5. Post-Schema Manual Backfill Steps (For Matthew)

After the attribute is added to the schema:

| # | Step | Command |
|---|------|---------|
| 1 | List all users | `aws cognito-idp list-users --user-pool-id <POOL_ID>` |
| 2 | For each active user, set attribute | `aws cognito-idp admin-update-user-attributes --username <USER> --user-attributes Name=custom:company_id,Value=tog_and_dogs` |
| 3 | Verify Matthew's own token after re-login | Inspect JWT in browser dev tools → look for `custom:company_id` claim |
| 4 | Verify /admin still works | Normal login |
| 5 | Verify /platform-admin still works | Platform admin login |

### Do NOT

- Do not set values for non-existent second tenants
- Do not create new users
- Do not change passwords or groups
- Do not document usernames/emails in repo

---

## 6. Validation Checklist (After Schema + Backfill)

| # | Check | Expected |
|---|-------|----------|
| 1 | `custom:company_id` attribute exists on pool schema | ✅ Visible in pool config |
| 2 | App client can read the attribute (in token) | ✅ Claim appears in ID token |
| 3 | App client cannot write the attribute (user self-edit blocked) | ✅ UpdateUserAttributes rejected |
| 4 | Matthew admin login works | ✅ /admin loads |
| 5 | Matthew platform_admin login works | ✅ /platform-admin loads |
| 6 | JWT includes `custom:company_id = tog_and_dogs` | ✅ After re-auth |
| 7 | `TENANT_RESOLUTION_FALLBACK` drops to zero in CloudWatch | ✅ After all users backfilled |
| 8 | `TENANT_RESOLUTION_MODE` remains `single` | ✅ Not changed |
| 9 | No second tenant created | ✅ |
| 10 | Staff/client login works (if applicable) | ✅ |

---

## 7. Rollback / Irreversibility Notes

### Cannot Be Undone

- **Custom attributes cannot be deleted from a Cognito user pool after creation**
- If `custom:company_id` is added incorrectly, it remains on the schema permanently
- However, it can be left unused with no operational impact

### Safe Properties

- Adding the attribute does NOT affect existing users (they just don't have it yet)
- Adding the attribute does NOT change login behavior
- Adding the attribute does NOT break existing tokens (claim simply absent until set)
- The `TENANT_RESOLUTION_MODE=single` fallback continues working regardless

### If Something Goes Wrong

| Scenario | Resolution |
|----------|------------|
| Attribute added with wrong name | Leave unused; add the correct one separately |
| Attribute added with wrong constraints | Leave as-is; constraints only affect new values |
| User set with wrong company_id value | Admin can update to correct value (mutable) |
| Token doesn't include claim after set | Check app client ReadAttributes; may need re-login |
| Login breaks after attribute addition | Attribute addition alone cannot break login — investigate other causes |

---

## 8. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **18A** | Schema addition plan (this document) | ✅ Kiro (done) |
| **18B** | Schema addition implementation (Terraform or CLI) + app client config | AG + Matthew |
| **18C** | Manual user backfill (Matthew sets attribute on all users) | Matthew |
| **18D** | Fallback metric observation (7 days, zero fallbacks) | AG monitoring |
| **18E** | Strict mode approval gate (Matthew approves) | Matthew |
| **18F** | Strict mode enablement (`TENANT_RESOLUTION_MODE=multi`) | AG + Matthew |
| **18G** | Second-tenant creation approval gate | Matthew |
| **18H** | Second-tenant dry run | AG + Matthew |

---

## 9. What This Document Does NOT Authorize

- ❌ Adding the custom attribute to Cognito
- ❌ Running Terraform plan or apply
- ❌ Running AWS CLI add-custom-attributes
- ❌ Modifying user attributes
- ❌ Creating users
- ❌ Enabling multi mode
- ❌ Creating a second tenant
- ❌ Code changes
- ❌ DynamoDB writes
- ❌ Frontend/mobile changes
- ❌ Stripe/Postmark changes
- ❌ Ryan/tester changes

This is a planning document. Schema implementation (18B) requires separate approval.
