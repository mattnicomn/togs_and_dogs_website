# Release 17G: Entitlement Enforcement Observability and Denial Logging

**Status:** Completed  
**Type:** Backend Observability & Production Deployment  
**Date:** 2026-06-21  
**Baseline Commit:** `ad0ccc4` (Release 17E closeout)

---

## 1. Goal

The goal of this release was to implement safe, structured logging for entitlement decisions across all Phase 1 gates before enforcement is enabled in production. This observability layer ensures that a future enablement release can easily identify unexpected denials or access checks.

---

## 2. Implementation Details

We updated the core entitlement logic in `src/backend/common/entitlement.py` to write JSON-structured logs to Python's standard `logging` library.

### Log Event Names
- **`ENTITLEMENT_ALLOWED`**: Logged whenever an entitlement check successfully permits an action.
- **`ENTITLEMENT_DENIED`**: Logged when an entitlement check denies an action (raised as `EntitlementDenied`).

### Log Fields
To enable robust querying in CloudWatch without leaking sensitive user details, logs include:
- `event`: `ENTITLEMENT_ALLOWED` or `ENTITLEMENT_DENIED`
- `company_id`: The ID of the tenant being checked
- `check_type`: `feature | limit | subscription`
- `feature_key` / `limit_key`: Key of the checked feature or limit (when applicable)
- `subscription_tier`: Resolved subscription plan of the tenant
- `subscription_status`: Plan billing status (e.g. `active`, `past_due`, `canceled`)
- `enforcement_enabled`: Feature flag state (boolean)
- `allowed`: Outcome of the check (boolean)
- `reason`: Explanation of the outcome
- `current_count` / `max_allowed`: Limit values (when checking limits)
- `protected_admin_bypass`: Set to `true` if bypass was triggered (boolean)
- `request_id`: Extracted correlation ID from API Gateway request context (when available)

> [!WARNING]
> **PII Protection & Security Guardrails:** Logs strictly exclude client/staff names, pet names, addresses, phone numbers, emails, auth/session tokens, cookies, secrets, or raw request payloads. Bypass indicators are logged only as a boolean (`protected_admin_bypass: true`) without emitting user identities or raw Cognito claim values.

---

## 3. Automated Test Coverage

We created `tests/backend/test_r17g_entitlement_observability.py` to comprehensively verify:
1. **Low-Noise / No-Spam Enforcement**: Zero logs are emitted when `ENTITLEMENT_ENFORCEMENT_ENABLED=false` is set.
2. **Allowed Features**: `ENTITLEMENT_ALLOWED` events are written for enabled features when enforcement is on.
3. **Denied Features**: `ENTITLEMENT_DENIED` events are written for disabled plan features when enforcement is on.
4. **Limits (Under, At, Over)**: Emits correct counts and outcomes based on numeric thresholds.
5. **Subscription Status blocks**: `ENTITLEMENT_DENIED` events are generated when subscription status is blocked.
6. **Bypass Checks**: Emits bypass flag `true` and suppresses actual credentials/emails from log lines.

All 29 entitlement-related tests and 442 total backend test cases passed successfully.

---

## 4. Production Deployment

1.  **AWS Identity Verification:**
    *   **Account:** `358604342897` (Production)
    *   **User/Role:** `assumed-role/AWSReservedSSO_AdministratorAccess_11c170f9e933c874/multi_account_user`
2.  **Deployment Method:**
    *   Regenerated fresh `infra/prod/backend.zip` code package.
    *   Executed `terraform plan` and `terraform apply tfplan`.
    *   **Summary:** `0 to add, 12 to change, 0 to destroy` resources (in-place Lambda function code updates).

---

## 5. Guardrails & Compliance Check

*   **`ENTITLEMENT_ENFORCEMENT_ENABLED` remains `false`** in production.
*   Zero changes were made to entitlement gating behavior, pricing limits, tenant metadata, or system permissions. No Phase 2 gates were added.
*   Zero changes to frontend, mobile, App Store Connect, TestFlight, or EAS configuration occurred.
*   No database writes, Cognito modifications, Postmark emails, SMS, or Stripe operations took place.
