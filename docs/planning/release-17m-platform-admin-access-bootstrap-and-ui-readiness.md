# Release 17M: Platform Admin Access Bootstrap and Management UI Readiness Plan

**Status:** Planning
**Date:** 2026-06-21
**Priority:** High (enables platform admin workflow and UI development)
**Scope:** Define safe bootstrap for platform_admin access + prepare for UI MVP

---

## 1. Platform Admin Access Bootstrap — Method Evaluation

| Method | Safety | Reversibility | Ties to Infra? | Recommendation |
|--------|--------|---------------|----------------|----------------|
| **AWS Console (manual)** | ✅ High | ✅ Easy remove | ❌ No | ✅ **Recommended** |
| AWS CLI command | ✅ High | ✅ Easy remove | ❌ No | ✅ Acceptable alternative |
| Terraform-managed group membership | ⚠️ Medium | ⚠️ Couples user to infra state | ✅ Yes | ❌ Avoid |
| One-time script | ⚠️ Medium | ✅ Easy remove | ❌ No | ⚠️ Acceptable if documented |
| Admin bootstrap endpoint | ❌ Low | N/A | ❌ No | ❌ Not recommended (security risk) |

### Decision: Manual AWS Console or CLI (Matthew's Choice)

**Recommended approach:** Matthew manually adds his Cognito user to the `platform_admin` group via the AWS Console or a single CLI command.

**Why:**
- No code changes needed
- No Terraform state coupling (personal user assignment shouldn't be infra-as-code)
- Instantly reversible (remove from group in Console)
- Matthew retains full control over who gets platform admin access
- No endpoint or script that could be exploited

### Exact Steps (For Matthew)

**Option A: AWS Console**
1. Open AWS Console → Cognito → User Pools → select the production pool
2. Find Matthew's user account
3. Go to Group memberships → Add to group → select `platform_admin`
4. Save

**Option B: AWS CLI**
```powershell
aws cognito-idp admin-add-user-to-group ^
  --user-pool-id us-east-1_counlsXGU ^
  --username [Matthew's Cognito username] ^
  --group-name platform_admin ^
  --profile usmissionhero-website-prod
```

**Both options require Matthew to execute manually.** AG should not add users during implementation — only document the steps and confirm the group exists.

---

## 2. Temporary CLI Script — Recommendation

### Decision: A Minimal Read-Only CLI Helper Is Acceptable

A small CLI script may be useful for initial smoke testing of platform APIs without requiring the full UI to be built. However, it must be:

| Requirement | Scope |
|-------------|-------|
| Read-only by default | List tenants, view detail, view audit |
| No mutation unless explicitly flagged | PATCH only with `--confirm` flag |
| No secrets logged | Do not print tokens, keys, or sensitive tenant data |
| Not a replacement for UI | Temporary bridge only |
| Documented as temporary | Mark as "development/testing tool" |
| Not required for production workflow | Matthew can use the API directly or wait for UI |

### Acceptable CLI Scope (If AG Builds One)

```
scripts/platform-admin-cli.py

Commands:
  list-tenants           GET /platform/tenants (read-only)
  get-tenant <id>        GET /platform/tenants/{company_id} (read-only)
  get-audit              GET /platform/audit (read-only)
  
  # Mutation (requires --confirm flag):
  update-tenant <id> --tier <tier> --confirm
  update-tenant <id> --status <status> --confirm
```

### What the CLI Must NOT Do

- ❌ Store or log Cognito tokens persistently
- ❌ Modify tier limits or global config
- ❌ Delete tenants
- ❌ Create tenants (separate provisioning flow)
- ❌ Access client/staff/pet private data
- ❌ Print full API responses with sensitive fields

### Whether CLI Is Required for 17N

**No.** The CLI is optional. AG can smoke test APIs using `curl` with a Cognito token. The CLI is a convenience, not a dependency.

---

## 3. Authorized Smoke Validation After Bootstrap

Once Matthew is in the `platform_admin` group, validate:

| # | Check | Method | Expected | Fail Action |
|---|-------|--------|----------|-------------|
| 1 | `GET /platform/tenants` returns tenant list | Authenticated request | 200 + array with tog_and_dogs | Investigate auth/role check |
| 2 | `GET /platform/tenants/tog_and_dogs` returns detail | Authenticated request | 200 + tenant metadata fields | Investigate handler logic |
| 3 | `GET /platform/audit` returns audit log | Authenticated request | 200 + empty array or recent entries | Investigate |
| 4 | Non-platform-admin user gets 403 | Authenticated as staff/client | 403 Forbidden | Auth check broken |
| 5 | Unauthenticated request gets 401 | No token | 401 Unauthorized | ✅ Already confirmed (17L) |
| 6 | No client/staff/pet private data exposed | Inspect response body | Only tenant metadata fields | Privacy violation if exposed |
| 7 | PATCH deferred or tested safely | If tested: change `admin_notes` only | 200 + audit record written | Investigate |

### PATCH Safety

For initial smoke, PATCH should be tested with a **non-disruptive field only**:
- ✅ Safe: `admin_notes` (internal-only, no enforcement impact)
- ⚠️ Careful: `subscription_tier` or `subscription_status` (affects entitlement enforcement)

**Recommendation:** First PATCH smoke updates `admin_notes` field only. Tier/status changes are tested later with proper confirmation and monitoring.

---

## 4. Platform Management UI Readiness (17O)

### UI MVP Should Include

| Page | Features |
|------|----------|
| **Tenant List** (`/platform-admin`) | Table: name, tier badge, status badge, staff/client counts, created date; search/filter |
| **Tenant Detail** (`/platform-admin/tenants/{id}`) | Profile card, entitlement panel, usage stats, subscription form, audit log |
| **Edit Form** | Tier dropdown, status dropdown, override date picker, notes textarea, confirmation modal |
| **Audit Log Panel** | Filterable table of platform admin actions for the selected tenant |

### UI Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Routing | `/platform-admin/*` | Separate from `/admin` business dashboard |
| Access check | Check Cognito groups includes `platform_admin` on load | Hide entire section from non-platform-admin |
| API calls | Use same `request()` helper with auth token | Existing pattern |
| State management | Local component state (no global store needed) | Small page count |
| Styling | Reuse existing design system + "Platform" header badge | Consistency |

### UI Files Likely to Create

| File | Purpose |
|------|---------|
| `web/src/components/PlatformAdmin.jsx` | Main layout + tenant list |
| `web/src/components/PlatformTenantDetail.jsx` | Detail + edit form |
| `web/src/api/platform.js` | API helpers: `getTenants()`, `getTenant(id)`, `updateTenant(id, data)`, `getAudit()` |
| `web/src/App.jsx` | Add `/platform-admin` route (Cognito-gated) |

---

## 5. Security Constraints

| Constraint | Enforcement |
|------------|-------------|
| Platform admin is separate from tenant admin | Cognito group `platform_admin` checked explicitly |
| No impersonation | Platform routes return metadata only, not session tokens |
| No tenant deletion | PATCH endpoint does not support `DELETE` action |
| No raw DynamoDB access | Structured API with validation |
| No Stripe key exposure | Keys never in API responses |
| No client/staff private data | GET tenant returns only tenant-level metadata |
| Audit every mutation | PATCH writes to PLATFORM_AUDIT before returning |
| Confirmation for risky changes | UI modal required; backend accepts change regardless (UI responsibility) |
| Role cannot be self-assigned | Group membership managed via AWS Console only |

---

## 6. Recommended Release Sequence

| Release | Scope | Owner | Effort |
|---------|-------|-------|--------|
| **17M** | Access bootstrap + UI readiness plan (this document) | ✅ Kiro (done) | — |
| **17N** | Matthew bootstraps platform_admin access + authorized API smoke | AG + Matthew | Low |
| **17O** | Platform Management UI MVP (tenant list, detail, edit, audit) | AG | Medium-High |
| **17P** | UI-backed tenant tier/status management smoke | AG + Matthew | Low |
| **17Q** | Second-tenant dry-run through Platform Admin flow | AG + Kiro | Medium |

---

## 7. What This Document Does NOT Authorize

- ❌ Adding any user to `platform_admin` group
- ❌ Code changes
- ❌ Cognito changes
- ❌ Terraform/AWS changes
- ❌ DynamoDB writes
- ❌ Frontend/mobile deployment
- ❌ Creating a second tenant
- ❌ Stripe/Postmark/payment changes
- ❌ Ryan/tester changes

This is a planning document. Bootstrap execution (17N) requires Matthew's explicit manual action.
