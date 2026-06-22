# Release 17V: Tenant Provisioning Runbook / Seed Tool Design

**Status:** Design Complete
**Date:** 2026-06-21
**Priority:** High (final design gate before second-tenant creation)
**Scope:** Define safe tenant creation process without executing it

---

## 1. Provisioning Approach Evaluation

| Approach | Safety | Repeatable | Auditable | Rollback | Effort | Recommendation |
|----------|--------|------------|-----------|----------|--------|----------------|
| Manual AWS Console / DynamoDB | ⚠️ Error-prone | ❌ | ❌ | ⚠️ | Low | ❌ Avoid |
| One-time AG seed script | ✅ | ✅ | ⚠️ Manual | ✅ | Low | ✅ **MVP recommended** |
| Platform Admin UI "Create Tenant" | ✅ | ✅ | ✅ Auto | ✅ | High | ⏳ Future (18+) |
| Terraform-managed tenant seed | ⚠️ Couples data to infra | ✅ | ✅ | ⚠️ | Medium | ❌ Avoid |
| Self-service signup flow | ✅ | ✅ | ✅ | ✅ | Very High | ⏳ Future (19+) |

### Decision: AG-Operated Seed Script (MVP)

A controlled Python script that:
1. Creates the `TENANT#{company_id} / METADATA` record in DynamoDB
2. Outputs the Cognito commands needed (but does NOT execute them without approval)
3. Writes a `PLATFORM_AUDIT` record documenting the creation
4. Is idempotent (checks if tenant already exists before creating)
5. Requires Matthew's explicit approval before each execution

**Future path:** After second-tenant dry run validates the script, the logic migrates into a Platform Admin UI "Create Tenant" workflow.

---

## 2. Tenant Metadata Seed Design

### Required Fields

```json
{
  "PK": "TENANT#<company_id>",
  "SK": "METADATA",
  "company_id": "<company_id>",
  "display_name": "<Business Display Name>",
  "subscription_tier": "starter",
  "subscription_status": "active",
  "limits": {
    "max_active_clients": 20,
    "max_staff": 1,
    "max_monthly_notifications": 100,
    "max_monthly_bookings": 50,
    "google_calendar_enabled": false,
    "export_enabled": false,
    "custom_branding_enabled": false,
    "video_evidence_enabled": false
  },
  "admin_override_until": null,
  "admin_notes": "Created via provisioning script. Dry-run test tenant.",
  "billing_provider": null,
  "stripe_customer_id": null,
  "stripe_subscription_id": null,
  "created_at": "<ISO timestamp>",
  "updated_at": "<ISO timestamp>",
  "created_by": "platform_admin:provisioning_script"
}
```

### Field Notes

| Field | Source | Notes |
|-------|--------|-------|
| `company_id` | Script input | Slug format, lowercase, no spaces (e.g., `test_tenant_alpha`) |
| `display_name` | Script input | Human-readable business name |
| `subscription_tier` | Default: `starter` | Safest starting tier (most restrictive) |
| `subscription_status` | Default: `active` | Makes tenant immediately usable |
| `limits` | Derived from TIER_LIMITS[tier] | Auto-populated from tier |
| `billing_provider` | null | No Stripe until live billing |
| `admin_notes` | Script sets default | Documents provisioning method |

### What Must NOT Be in Seed

- ❌ Secrets or API keys
- ❌ Stripe live credentials
- ❌ Google OAuth tokens
- ❌ Postmark secrets
- ❌ Client/staff personal data
- ❌ Passwords
- ❌ Real customer emails in code/docs

---

## 3. Cognito Setup for New Business Owner

### Required Steps (Manual or Script-Assisted)

| # | Step | Method | Notes |
|---|------|--------|-------|
| 1 | Create Cognito user for business owner | AWS CLI or Console | Use new owner's email as username |
| 2 | Set temporary password (require change) | `--permanent false` | Never document the password |
| 3 | Add user to `owner` group | `admin-add-user-to-group` | Grants business admin access |
| 4 | Set `custom:company_id` attribute (if implemented) | `admin-update-user-attributes` | Links user to tenant |
| 5 | Verify user can log in and sees only their tenant | Manual validation | Critical isolation check |

### Important Boundaries

| Rule | Detail |
|------|--------|
| Do NOT add test tenant owner to `platform_admin` | Platform admin is usmissionhero-only |
| Do NOT reuse existing owner email for test | Create a clearly-test email/identity |
| Do NOT document real passwords | Use `--permanent false` and private communication |
| Company_id in JWT | Currently uses `DEFAULT_COMPANY_ID` env var fallback; custom attribute path is designed but may need implementation |

### Cognito Automation Decision

| Option | Recommendation |
|--------|----------------|
| Fully automate in provisioning script | ⚠️ Defer — Cognito user creation is sensitive |
| Script outputs CLI commands, Matthew executes | ✅ **MVP recommended** — Matthew retains control |
| Manual Console only | ⚠️ Acceptable but error-prone for repeated use |

---

## 4. Default Entitlement for Second-Tenant Dry Run

### Recommended Test Tenant Settings

| Field | Value | Rationale |
|-------|-------|-----------|
| `subscription_tier` | `starter` | Tests most restrictive limits (1 staff, no export, no calendar) |
| `subscription_status` | `active` | Tenant is usable immediately |
| `max_staff` | 1 | Tests Phase 1 staff limit gate |
| `export_enabled` | false | Tests Phase 1 export gate |
| `google_calendar_enabled` | false | Tests Phase 1 calendar gate |

### Phase 1 Entitlement Gates Apply Immediately

Because `ENTITLEMENT_ENFORCEMENT_ENABLED=true` is already deployed:
- New starter tenant will be blocked from export ✅
- New starter tenant will be blocked from calendar connect ✅
- New starter tenant will be blocked from creating 2nd staff ✅

This provides immediate denied-path validation without any additional code changes.

---

## 5. Tenant Isolation Validation Checklist

After second tenant is created:

| # | Check | Method | Expected |
|---|-------|--------|----------|
| 1 | New tenant owner only sees own data | Log in as new owner | Empty dashboard (no tog_and_dogs data) |
| 2 | tog_and_dogs owner does NOT see new tenant data | Log in as Matthew admin | Only tog_and_dogs requests/staff/clients |
| 3 | Platform admin sees BOTH tenants | Log in as platform_admin → /platform-admin | Both listed |
| 4 | New tenant export returns empty (or own data only) | GET /admin/export-data as new owner | 403 (starter) or empty |
| 5 | New tenant staff list is empty | GET /admin/staff as new owner | Empty list |
| 6 | New tenant cannot access tog_and_dogs requests | Attempt GET with known tog_and_dogs request ID | 404 or 403 |
| 7 | tog_and_dogs admin cannot access new tenant staff | Attempt cross-tenant staff query | 404 or 403 |
| 8 | Google Calendar is not auto-connected for new tenant | Check /admin/auth/status as new owner | CREDENTIALS_MISSING or not connected |
| 9 | Notifications for new tenant don't reach tog_and_dogs clients | Send test notification (if approved) | Only new tenant recipients |
| 10 | Mobile app shows role-appropriate view for new tenant | Log in via TestFlight (if applicable) | Correct tenant data only |

---

## 6. Rollback / Disable Plan

### If Second Tenant Needs to Be Removed

| Step | Action | Risk |
|------|--------|------|
| 1 | Set `subscription_status = disabled` via Platform Admin UI | ✅ Safe — blocks login |
| 2 | Disable Cognito user(s) for that tenant | ✅ Safe — blocks auth |
| 3 | Leave DynamoDB records in place (don't delete) | ✅ Safe — data is harmless if disabled |
| 4 | Document in audit log | ✅ |

### Do NOT

- ❌ Delete TENANT metadata record (could leave orphan references)
- ❌ Delete Cognito user pool or groups (affects all tenants)
- ❌ Remove company_id filter from handlers (breaks isolation for all)

### Reversibility

- Disabling is fully reversible (re-enable status = active)
- No data is lost
- No other tenant affected

---

## 7. Audit Requirements

### Provisioning Script Must Create

```json
{
  "PK": "PLATFORM_AUDIT",
  "SK": "ACTION#<timestamp>#<uuid>",
  "action": "tenant_created",
  "actor": "platform_admin:provisioning_script",
  "target_company_id": "<new_company_id>",
  "details": {
    "display_name": "<name>",
    "subscription_tier": "starter",
    "subscription_status": "active",
    "method": "provisioning_script_v1"
  },
  "timestamp": "<ISO>"
}
```

### If Manual Seed Cannot Auto-Audit

Document a manual audit note requirement: after manual DynamoDB put, immediately create a PLATFORM_AUDIT record documenting the creation. The Platform Admin UI will show this in the audit log.

---

## 8. Risk Matrix

| # | Risk | Likelihood | Impact | Mitigation | Owner | Release |
|---|------|-----------|--------|------------|-------|---------|
| 1 | New tenant sees tog_and_dogs data | Low | Critical | company_id enforcement in all handlers (11E) | AG | Already mitigated |
| 2 | Provisioning script creates invalid metadata | Low | Medium | Validate against TIER_LIMITS keys + schema | AG | 17W |
| 3 | Cognito user linked to wrong company_id | Medium | High | Script outputs commands for review; Matthew executes | Matthew | 17W |
| 4 | Second tenant breaks existing tenant operations | Low | Critical | Shared-table isolation; disable new tenant if issues | AG | 17Y validation |
| 5 | Test tenant data left in production permanently | Low | Low | Document as test; disable when done | Matthew | 17Z |
| 6 | Provisioning script committed with real user data | Low | Medium | Use placeholders; review before commit | AG | 17W |
| 7 | DEFAULT_COMPANY_ID fallback leaks data to new tenant | Low | High | New tenant user must have explicit company_id (attribute or mapping) | AG | 17W |
| 8 | Google Calendar auto-connects for new tenant | Low | Medium | Calendar is per-tenant secrets; new tenant starts disconnected | AG | Already isolated |

---

## 9. Go/No-Go Checklist for Second-Tenant Creation

| # | Gate | Status | Required? |
|---|------|--------|-----------|
| G1 | Provisioning script/tool implemented and tested | ❌ Pending 17W | **Yes** |
| G2 | Cognito user creation documented with safe steps | ❌ Pending 17W | **Yes** |
| G3 | Credential security cleanup complete | ✅ Done (17U) | Yes |
| G4 | Platform Admin can view/manage multiple tenants | ✅ Done (17P) | Yes |
| G5 | Phase 1 entitlement enforcement active | ✅ Done (17I) | Yes |
| G6 | Rollback/disable plan documented | ✅ Done (this doc) | Yes |
| G7 | Tenant isolation validation checklist ready | ✅ Done (this doc) | Yes |
| G8 | company_id resolution for new user works | ⚠️ Needs verification (custom attr or mapping) | **Yes** |
| G9 | Matthew explicitly approves creation | ❌ Pending | **Yes** |
| G10 | Test tenant name/ID confirmed by Matthew | ❌ Pending | **Yes** |

**Minimum required:** G1 + G2 + G8 + G9 + G10

---

## 10. Recommended Release Sequence After 17V

| Release | Scope | Owner |
|---------|-------|-------|
| **17V** | Tenant provisioning design (this document) | ✅ Kiro (done) |
| **17W** | Provisioning script implementation + company_id resolution verification | AG |
| **17X** | Second-tenant creation approval gate (Matthew approves specific test tenant) | Matthew |
| **17Y** | Second-tenant backend dry run (create tenant, run isolation checklist) | AG + Matthew |
| **17Z** | Second-tenant UI/mobile isolation validation | AG + Matthew |
| **18A** | External tester / Ryan re-entry readiness review | Kiro |

---

## 11. Is Second-Tenant Creation Approved Now?

**No.** This is a design document only. Actual creation requires:
1. AG implements provisioning script (17W)
2. company_id resolution is verified for new users (17W)
3. Matthew explicitly approves the specific test tenant (17X)

---

## 12. What This Document Does NOT Authorize

- ❌ Creating a second tenant
- ❌ Writing to DynamoDB
- ❌ Creating Cognito users
- ❌ Running provisioning scripts
- ❌ Code changes
- ❌ Terraform/AWS changes
- ❌ Stripe/Postmark changes
- ❌ Frontend/mobile changes
- ❌ Ryan/tester changes

This is a design document. Implementation (17W) requires separate approval.
