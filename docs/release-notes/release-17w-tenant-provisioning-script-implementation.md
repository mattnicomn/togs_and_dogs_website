# Release 17W: Tenant Provisioning Script Implementation and Company ID Resolution Verification

**Status:** ✅ Completed  
**Type:** Script Implementation / Security Verification / Test Coverage  
**Date:** 2026-06-21  
**Baseline:** Release 17V Tenant Provisioning Runbook / Seed Tool Design (`cf08f5d`).

---

## 1. Context

Release 17V produced a runbook and design for a safe tenant provisioning seed tool.
Release 17W implements that design: a Python provisioning script, a full test suite
covering the script and the existing company ID resolution logic, and formal
documentation of the `DEFAULT_COMPANY_ID` fallback risk for multi-tenant readiness.

**Second-tenant creation remains blocked.** This release is code and test
implementation only. No production writes were performed. No Cognito users or groups
were created or modified.

---

## 2. Files Created / Modified

| File | Action | Description |
|---|---|---|
| [scripts/provision_tenant.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/scripts/provision_tenant.py) | 🆕 Created | Safe tenant provisioning script (dry-run default) |
| [tests/backend/test_r17w_tenant_provisioning.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r17w_tenant_provisioning.py) | 🆕 Created | 46 unit tests for the provisioning script |
| [tests/backend/test_r17w_company_id_resolution.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r17w_company_id_resolution.py) | 🆕 Created | 26 tests for company_id resolution and cross-tenant isolation |
| [docs/release-notes/release-17w-tenant-provisioning-script-implementation.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/release-notes/release-17w-tenant-provisioning-script-implementation.md) | 🆕 Created | This release note |
| [docs/backlog/saas-maturity-and-multi-business-owner-readiness.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/backlog/saas-maturity-and-multi-business-owner-readiness.md) | 📝 Modified | Updated items #2 and #3 to reflect 17W progress |
| [docs/release-notes/index.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/release-notes/index.md) | 📝 Modified | Registered Release 17W |

---

## 3. Provisioning Script (`scripts/provision_tenant.py`)

### Behavior

| Mode | How to Activate | Writes to AWS |
|---|---|---|
| **Dry-run** (default) | `python scripts/provision_tenant.py --company-id X --display-name Y` | ❌ None |
| **Apply** | `--apply --confirm-apply` (both flags required) | ✅ DynamoDB only |

### Dry-Run Output

Running in dry-run mode prints:
1. **Proposed tenant metadata record** — safe fields only, sensitive fields explicitly excluded
2. **Proposed PLATFORM_AUDIT record** — matches schema used by `platform_handler.py`
3. **Cognito CLI command templates** — placeholder values only (`<USER_POOL_ID>`, `<USERNAME_OR_EMAIL>`, `<TEMP_PASSWORD>`, `<EMAIL>`, `<COMPANY_ID>`)
4. **Rollback / disable guidance** — subscription_status approach, Cognito disable commands (placeholder)
5. **Idempotency notes** — explain the existence check and force-overwrite behavior

### Apply Mode (Future Gate — NOT YET APPROVED)

Apply mode:
- Checks for existing `TENANT#<company_id>/METADATA` before writing (idempotency guard)
- Skips metadata write if tenant already exists (unless `--force-overwrite` is set)
- Always writes a new `PLATFORM_AUDIT` record with a UUID SK (audit is always recorded)
- Requires **both** `--apply` and `--confirm-apply` flags; either alone is rejected

### Tenant Metadata Payload Summary

Fields written on provisioning:

| Field | Value |
|---|---|
| `PK` | `TENANT#<company_id>` |
| `SK` | `METADATA` |
| `company_id` | Provided via `--company-id` |
| `display_name` | Provided via `--display-name` |
| `entity_type` | `TENANT` |
| `subscription_tier` | `starter` (default) or `--tier` value |
| `subscription_status` | `active` (default) or `--status` value |
| `limits` | Derived from `TIER_LIMITS[tier]` |
| `is_active` | `True` |
| `notes` | Provided via `--notes`, or auto-generated with timestamp |
| `created_at` / `updated_at` | UTC ISO timestamp at provisioning time |
| `created_by` / `updated_by` | `platform_admin:system` (or custom `--actor`) |

**Intentionally excluded from provisioning payload:**
- `stripe_customer_id` — set by Stripe webhook only
- `stripe_subscription_id` — set by Stripe webhook only
- `owner_email` — sensitive; set manually or via Cognito
- `owner_cognito_sub` — sensitive; set after Cognito user creation
- `notification_email_from` — set per-tenant via platform admin
- OAuth / Google Calendar tokens

### Safety Guardrails

- `company_id='tog_and_dogs'` is explicitly rejected (production tenant protection)
- `company_id` format enforced: `^[a-z0-9_]{3,64}$`
- No private user data, credentials, secrets, tokens, or payment fields in any output

---

## 4. Cognito Command Template Summary

The script prints **placeholder-only** CLI templates. No real values are ever included.

Templates cover:
- `admin-create-user` with `custom:company_id=<COMPANY_ID>` attribute set
- `admin-add-user-to-group` with `--group-name owner` (tenant-level)
- Group verification commands

**Role Clarification:**
- Tenant owner must be added to `owner` group only
- `platform_admin` group is reserved for usmissionhero operators only
- A second-tenant owner must **never** receive `platform_admin`

---

## 5. Company ID Resolution Findings

**Source:** `src/backend/common/auth.py`

### Current Behavior (Lines 215–229)

```python
DEFAULT_COMPANY_ID = os.environ.get("DEFAULT_COMPANY_ID", "tog_and_dogs")

def get_current_company_id(event, claims=None):
    custom_company = claims.get('custom:company_id')
    if custom_company:
        return custom_company
    return DEFAULT_COMPANY_ID
```

**`custom:company_id` claim takes full precedence.** This is the correct multi-tenant mechanism.

### Is the DEFAULT_COMPANY_ID Fallback Safe?

| Scenario | Result | Safe? |
|---|---|---|
| User with `custom:company_id=tog_and_dogs` | Routes to `tog_and_dogs` | ✅ Correct |
| User with `custom:company_id=acme_pets` | Routes to `acme_pets` | ✅ Correct |
| User with **no** `custom:company_id` claim | Routes to `DEFAULT_COMPANY_ID` (`tog_and_dogs`) | ⚠️ **KNOWN RISK** |
| platform_admin user via platform_handler | Bypasses tenant enforcement | ✅ Correct |

### ⚠️ Known Risk: DEFAULT_COMPANY_ID Fallback

> **A Cognito user created WITHOUT `custom:company_id` set on their account will silently fall through to `DEFAULT_COMPANY_ID` ("tog_and_dogs") and be able to access that tenant's data.**

This is intentional and safe for the **current single-tenant deployment**.
It becomes a **cross-tenant data access risk** for multi-tenant.

**Required mitigation before second-tenant Cognito users are created:**
1. Set `custom:company_id=<company_id>` on every Cognito user at creation time (`admin-create-user`).
2. The provisioning script's Cognito CLI templates already include this attribute.
3. Optionally: add a Lambda post-authentication trigger that rejects JWTs without `custom:company_id`.

### Cross-Tenant Isolation (`validate_tenant_ownership`)

`validate_tenant_ownership` in `auth.py` correctly enforces:
- Items with `company_id=tog_and_dogs` are inaccessible to `acme_pets` users
- Items with `company_id=acme_pets` are inaccessible to `tog_and_dogs` users
- Items without a `company_id` field are assumed to belong to `DEFAULT_COMPANY_ID`

The isolation mechanism is **structurally correct** and already multi-tenant-capable, contingent on `custom:company_id` being set on all Cognito users.

---

## 6. Test Suite Results

### New Tests (Release 17W)

| Suite | Tests | Result |
|---|---|---|
| `test_r17w_tenant_provisioning.py` | 46 | ✅ 46/46 passed |
| `test_r17w_company_id_resolution.py` | 26 | ✅ 26/26 passed |

### Full Regression

```bash
py -m pytest tests/backend/ -v
# 526 passed, 78 warnings in 8.24s
```

All 526 backend tests passed. No regressions introduced.

---

## 7. Operational Guarantees

- **No production DynamoDB writes** occurred in this release.
- **No second tenant was created** in any environment.
- **No Cognito users, groups, or passwords were created, modified, or deleted.**
- **No tenant metadata was modified** (including `tog_and_dogs`).
- **No Stripe, Postmark, payment, mobile, EAS, TestFlight, App Store Connect, or live key changes** occurred.
- **No frontend deployment** was performed.
- **No Terraform** was run.

---

## 8. Dry-Run Validation

```bash
python scripts/provision_tenant.py \
    --company-id acme_pets \
    --display-name "Acme Pet Sitting" \
    --tier starter
```

Expected output includes:
- `DRY-RUN MODE — NO WRITES WILL OCCUR`
- Proposed tenant metadata JSON (starter tier limits, no sensitive fields)
- Proposed PLATFORM_AUDIT record JSON
- Cognito CLI command templates with `<PLACEHOLDER>` values only
- Rollback and disable guidance
- Idempotency notes

---

## 9. Recommended Next Steps

**Release 17X / Gate G7:** Multi-tenant Cognito `custom:company_id` enforcement.
- Add a Lambda post-authentication trigger that rejects JWTs without `custom:company_id`.
- This closes the `DEFAULT_COMPANY_ID` fallback risk before any second-tenant user is created.

**Second-tenant provisioning (future gate):**
- Requires explicit Matthew approval.
- Run `provision_tenant.py --apply --confirm-apply` only after gate approval.
- Execute Cognito CLI commands manually with real values replacing placeholders.
