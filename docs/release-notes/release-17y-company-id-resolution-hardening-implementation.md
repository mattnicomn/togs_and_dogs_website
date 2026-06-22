# Release 17Y: Company ID Resolution Hardening Implementation

**Status:** ✅ Completed  
**Type:** Code Implementation / Observability Configuration / Verification  
**Date:** 2026-06-22  
**Baseline:** Release 17W (`b7dafecde76d6542617f694f31cfa04a11f204ce`)

---

## 1. Context

Release 17X produced a design for Company ID Resolution Hardening to mitigate the security risk where Cognito users without a `custom:company_id` could silently fall back to `DEFAULT_COMPANY_ID` ("tog_and_dogs"), potentially gaining access to the wrong tenant's data.

Release 17Y implements this hardening:
1. Implements `TENANT_RESOLUTION_MODE=single|multi` environment toggle.
2. In `single` (compatibility) mode: Falls back to `DEFAULT_COMPANY_ID` and logs `TENANT_RESOLUTION_FALLBACK`.
3. In `multi` (strict) mode: Rejects missing/empty `custom:company_id` with `PermissionError` and logs `TENANT_RESOLUTION_FAILED`.
4. Emits structured JSON logs without private user data, JWT claims, emails, or usernames.
5. Deploys updated backend Lambda code to production.
6. Adds CloudWatch metric filters and alarms via Terraform.

**Strict/multi mode remains disabled in production.** The production environment continues to run in `single` mode for compatibility until Cognito user attributes are audited and updated (Release 17Z).

---

## 2. Files Created / Modified

| File | Action | Description |
|---|---|---|
| [src/backend/common/auth.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/auth.py) | 📝 Modified | Added `TENANT_RESOLUTION_MODE` logic and structured logging |
| [tests/backend/test_r17w_company_id_resolution.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r17w_company_id_resolution.py) | 📝 Modified | Added 7 unit tests covering single/multi modes and structured logging |
| [modules/observability/main.tf](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/modules/observability/main.tf) | 📝 Modified | Added CloudWatch metric filters and alarms for fallback/failed resolution |
| [docs/release-notes/release-17y-company-id-resolution-hardening-implementation.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/release-notes/release-17y-company-id-resolution-hardening-implementation.md) | 🆕 Created | This release notes document |
| [docs/release-notes/index.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/release-notes/index.md) | 📝 Modified | Registered Release 17Y |
| [docs/backlog/saas-maturity-and-multi-business-owner-readiness.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/backlog/saas-maturity-and-multi-business-owner-readiness.md) | 📝 Modified | Updated Cognito `custom:company_id` enforcement item and resume criteria |

---

## 3. Implementation Details

### `TENANT_RESOLUTION_MODE` Environment Toggle
- Default remains `"single"` to preserve backward compatibility.
- Strips whitespace and normalizes the `custom:company_id` custom attribute.
- Resolves valid `custom:company_id` value across both modes.

### Non-Sensitive Structured Logging
Logs are printed as JSON strings using Python's standard `logging` library. To prevent leakage of private user data (PUD) or credentials, no JWT claims, usernames, emails, tokens, cookies, auth headers, or Cognito exports are included.
- **`TENANT_RESOLUTION_FALLBACK` schema:**
  - `event`: `"TENANT_RESOLUTION_FALLBACK"`
  - `mode`: `"single"`
  - `is_empty_company_id`: `True|False`
  - `has_claims`: `True|False`
  - `default_company_id`: `"tog_and_dogs"`
  - `request_id`: AWS APIGateway request ID (if present)
- **`TENANT_RESOLUTION_FAILED` schema:**
  - `event`: `"TENANT_RESOLUTION_FAILED"`
  - `mode`: `"multi"`
  - `is_empty_company_id`: `True|False`
  - `has_claims`: `True|False`
  - `request_id`: AWS APIGateway request ID (if present)

---

## 4. Observability Metrics & Alarms

The following CloudWatch resources were added via Terraform in `modules/observability`:

### Metric Filters
- `tenant_resolution_fallback`: Scans logs for `"TENANT_RESOLUTION_FALLBACK"` pattern in all tenant-facing Lambda functions.
- `tenant_resolution_failed`: Scans logs for `"TENANT_RESOLUTION_FAILED"` pattern in all tenant-facing Lambda functions.

### Metric Alarms
- `tenant-resolution-fallback`: Triggers when `TenantResolutionFallback` > 0 in a 5-minute period. Alert indicates a legacy fallback occurred (requires Cognito user audit).
- `tenant-resolution-failed`: Triggers when `TenantResolutionFailed` > 0 in a 5-minute period. Alert indicates an access attempt was blocked due to missing `custom:company_id` in multi-tenant mode.

---

## 5. Test Suite Results

### Targeted Tests

```bash
py -m pytest tests/backend/test_r17w_company_id_resolution.py
# 33 passed in 0.36s
```

All 33 company ID resolution tests passed successfully, including:
- `test_default_mode_is_single`
- `test_single_mode_missing_company_id_fallback`
- `test_single_mode_empty_company_id_fallback`
- `test_single_mode_with_valid_company_id_does_not_log_fallback`
- `test_multi_mode_missing_company_id_raises_and_logs`
- `test_multi_mode_empty_company_id_raises_and_logs`
- `test_multi_mode_with_valid_company_id_passes`

### Full Regression

```bash
py -m pytest tests/backend
# 533 passed, 78 warnings in 8.21s
```

---

## 6. Operational Guardrails Verification

- **No production DynamoDB writes** occurred.
- **No second tenant was created**.
- **No Cognito users, groups, passwords, or attributes were modified**.
- **No tenant metadata was modified**.
- **No Stripe, Postmark, payment, mobile, EAS, TestFlight, App Store Connect, or live key changes** occurred.
- **No frontend deployment** was performed.
- **Strict/multi mode remains disabled in production.** The active mode is compatibility (`single`) mode.

---

## 7. Recommended Next Release

**Release 17Z: Cognito Company ID Attribute Audit / Manual Closeout**
- Conduct Cognito user attribute audit.
- Set `custom:company_id = tog_and_dogs` on all production Cognito users.
- Confirm zero `TENANT_RESOLUTION_FALLBACK` logs in CloudWatch over a monitoring period.
- Approve gate for enabling strict `multi` mode (Release 18A).
