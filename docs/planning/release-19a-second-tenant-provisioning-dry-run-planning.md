# Release 19A: Second-Tenant Provisioning Dry-Run Planning

**Status:** Planning
**Date:** 2026-06-26
**Priority:** High (next milestone toward multi-business-owner SaaS)
**Scope:** Plan a safe dry-run of the provisioning script without creating any tenant

---

## 1. Existing Provisioning Capability

### Script Location

```
scripts/provision_tenant.py
```

### Modes

| Mode | Behavior | Safe? |
|------|----------|-------|
| `--mode=dry-run` (default) | Prints proposed tenant metadata + Cognito commands, writes nothing | ✅ Safe |
| `--mode=apply` | Creates TENANT metadata record in DynamoDB + writes audit record | ❌ Requires explicit approval |

### Expected TENANT Metadata Fields (from script)

```json
{
  "PK": "TENANT#<company_id>",
  "SK": "METADATA",
  "company_id": "<company_id>",
  "display_name": "<display_name>",
  "subscription_tier": "starter",
  "subscription_status": "active",
  "limits": { ... derived from TIER_LIMITS['starter'] ... },
  "admin_override_until": null,
  "admin_notes": "Created via provisioning script.",
  "billing_provider": null,
  "stripe_customer_id": null,
  "stripe_subscription_id": null,
  "created_at": "<ISO timestamp>",
  "updated_at": "<ISO timestamp>",
  "created_by": "platform_admin:provisioning_script"
}
```

### Audit Record (Created on Apply)

```json
{
  "PK": "PLATFORM_AUDIT",
  "SK": "ACTION#<timestamp>#<uuid>",
  "action": "tenant_created",
  "target_company_id": "<company_id>",
  "details": { "display_name": "...", "tier": "starter", "method": "provisioning_script" }
}
```

### Cognito Follow-Up (Manual, Not Automated by Script)

After apply, the script outputs CLI commands for Matthew to execute:
- Create Cognito user for new tenant owner
- Set `custom:company_id` on the new user
- Add user to `owner` group
- Script does NOT execute these commands

### Rollback/Cleanup

- Set `subscription_status = disabled` via Platform Admin UI (blocks login)
- Disable Cognito user if created
- Leave DynamoDB record in place (non-destructive)
- No tenant deletion mechanism in MVP

---

## 2. Dry-Run Strategy

### What Dry-Run Does

| Action | Dry-Run | Apply |
|--------|---------|-------|
| Print proposed metadata | ✅ | ✅ |
| Print Cognito CLI commands | ✅ | ✅ |
| Write to DynamoDB | ❌ | ✅ |
| Create Cognito user | ❌ | ❌ (manual) |
| Modify existing tenant | ❌ | ❌ |
| Create audit record | ❌ | ✅ |

### Safety Confirmation

A dry-run execution:
- Does NOT write to DynamoDB
- Does NOT create Cognito users
- Does NOT touch existing tenant metadata
- Does NOT affect production operations
- Does NOT create calendar/payment/notification resources
- Only prints output to the terminal

---

## 3. Proposed Test Tenant Data Pattern (For Future Approval)

| Field | Proposed Value | Notes |
|-------|----------------|-------|
| `company_id` | `test_tenant_alpha` | Clearly test; slug format |
| `display_name` | `Test Tenant Alpha` | Internal only |
| `subscription_tier` | `starter` | Most restrictive — validates denied paths |
| `subscription_status` | `active` | Usable immediately |
| Owner email | `[Matthew-controlled address — not in docs]` | Matthew provides at approval time |
| Google Calendar | Not connected | New tenant starts without calendar |
| Stripe | Not connected | Sandbox-only; no billing |
| Notes | "19D dry-run validation tenant — safe to disable/remove" | Self-documenting |

### Why Starter Tier

- Tests Phase 1 denial paths (export blocked, calendar blocked, 2nd staff blocked)
- Tests Phase 2 limits (20 clients, 50 bookings/month)
- Validates entitlement enforcement for a restricted tenant
- Professional tier (tog_and_dogs) continues working normally alongside

---

## 4. Approval Gates Before Actual Tenant Creation (19C)

Matthew must explicitly approve ALL of the following before `--mode=apply` is run:

| # | Gate | Matthew Confirms |
|---|------|------------------|
| G1 | Exact `company_id` value | "Use `test_tenant_alpha`" or alternative |
| G2 | Exact `display_name` | "Use `Test Tenant Alpha`" or alternative |
| G3 | Subscription tier | "Start on `starter`" or alternative |
| G4 | Whether Cognito user should be created | "Yes, output commands" or "Defer" |
| G5 | Owner email for Cognito user | Provided privately (not in docs/chat) |
| G6 | Whether tenant should be retained or cleaned up after testing | "Retain" or "Disable after validation" |
| G7 | Rollback plan reviewed | "Understood — disable via Platform Admin" |
| G8 | Explicit "Approved: proceed with apply" | Final go-ahead |

---

## 5. Risk Review

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | Accidental tenant creation in dry-run | Very low | Medium | Script default is dry-run; apply requires explicit flag |
| 2 | Cognito user created without company_id | Low | High | Strict mode rejects missing company_id; script outputs correct commands |
| 3 | Cross-tenant data leakage | Low | Critical | Tenant isolation enforced (11E); strict mode active (18T) |
| 4 | Google Calendar token isolation | N/A | N/A | New tenant starts disconnected; per-tenant isolation is future work |
| 5 | Stripe/payment isolation | N/A | N/A | New tenant has no Stripe connection; sandbox-only |
| 6 | Platform Admin doesn't show new tenant | Low | Low | Platform Admin queries all TENANT# records; should auto-display |
| 7 | Entitlement enforcement incorrect for starter | Low | Medium | Phase 1+2 gates validated (18N); starter limits are in TIER_LIMITS |
| 8 | Cleanup complexity | Low | Low | Disable via Platform Admin; leave record; non-destructive |
| 9 | Audit trail missing for creation | Low | Low | Script creates PLATFORM_AUDIT record on apply |
| 10 | Test tenant confuses Ryan or future users | Low | Low | Clearly named; disabled before external access |

---

## 6. AG Dry-Run Validation Checklist (Release 19B)

| # | Check | Expected |
|---|-------|----------|
| 1 | Script runs with `--mode=dry-run` without error | Clean execution, no tracebacks |
| 2 | Proposed tenant metadata JSON is printed correctly | All required fields present |
| 3 | Cognito CLI commands are generated as safe placeholders | Correct structure, placeholder username |
| 4 | No DynamoDB writes occur | Verify via read-only query: no `TENANT#test_tenant_alpha` exists |
| 5 | No Cognito changes occur | No new users in pool |
| 6 | No production data affected | tog_and_dogs unchanged |
| 7 | No calendar/payment/notification actions | Zero side effects |
| 8 | Script output does not contain secrets/tokens/passwords | Output is safe to summarize |
| 9 | Audit record NOT created (dry-run only) | No `PLATFORM_AUDIT` for test_tenant_alpha |
| 10 | Full backend test suite still passes | All 533+ tests green |

---

## 7. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **19A** | Dry-run planning (this document) | ✅ Kiro (done) |
| **19B** | AG executes provisioning script in dry-run mode, reports output | AG |
| **19C** | Matthew approval checkpoint (reviews output, approves exact values) | Matthew |
| **19D** | Controlled second-tenant creation (`--mode=apply`) + Cognito setup | AG + Matthew |
| **19E** | Platform Admin second-tenant visibility validation | AG + Matthew |
| **19F** | Tenant isolation smoke (new tenant cannot see tog_and_dogs data) | AG + Matthew |

---

## 8. What This Document Does NOT Authorize

- ❌ Running provisioning script in apply mode
- ❌ Creating a second tenant
- ❌ Creating Cognito users
- ❌ DynamoDB writes
- ❌ Terraform/AWS changes
- ❌ Stripe/Postmark/payment changes
- ❌ Google Calendar changes
- ❌ Frontend/mobile deployment
- ❌ Ryan/tester changes
- ❌ App Store Connect changes
- ❌ Changing TENANT_RESOLUTION_MODE

This is a planning document. Dry-run execution (19B) and tenant creation (19D) require separate approval.
