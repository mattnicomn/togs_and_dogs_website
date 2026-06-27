# Release 19J: Second-Tenant Owner Login Isolation Remediation Plan

**Status:** Planning
**Date:** 2026-06-27
**Priority:** High (isolation defects block 19H revalidation)
**Scope:** Classify defects, design tactical fixes, defer long-term enhancements

---

## 1. Defect Classification

### From Release 19H/19I Findings

| # | Issue | Category | Severity |
|---|-------|----------|----------|
| 1 | Google Calendar status shows tog_and_dogs "Connected" for test_tenant_alpha | **Security/Isolation Blocker** | High |
| 2 | Staff quick view / sidebar shows tog_and_dogs users | **Security/Isolation Blocker** | High |
| 3 | Staff Management page shows tog_and_dogs staff | **Security/Isolation Blocker** | High |
| 4 | Client Management may show tog_and_dogs clients | **Security/Isolation Blocker** | High |
| 5 | Profile/company label shows "Togs & Dogs" for test_tenant_alpha | **Product/Branding Issue** | Medium |
| 6 | Header/app title shows "Togs & Dogs" globally | **Product/Branding Issue** | Low |

### Classification Key

| Category | Meaning | Action Timeline |
|----------|---------|-----------------|
| Security/Isolation Blocker | Cross-tenant data exposure — must fix before revalidation | Immediate (19K) |
| Product/Branding Issue | UX confusion but no data leak — fix before external users | Soon (19L) |
| Future SaaS Enhancement | Full white-label/multi-brand capabilities | Deferred |

---

## 2. Minimum Remediation for 19H Revalidation (PASS)

ALL of these must be true before 19H can be re-validated as PASS:

| # | Requirement | Current | Target |
|---|-------------|---------|--------|
| 1 | Google Calendar status returns "not configured" for non-tog_and_dogs tenants | ❌ Shows "Connected" | Must show "Not Configured" |
| 2 | GET /admin/staff filters by caller's company_id | ❌ Shows all staff | Must show only tenant's staff |
| 3 | GET /admin/clients filters by caller's company_id | ❌ May show all clients | Must show only tenant's clients |
| 4 | Staff sidebar/quick view filters by company_id | ❌ Shows cross-tenant | Must show only tenant's |
| 5 | Profile/company label reflects current tenant | ❌ Shows "Togs & Dogs" | Must show tenant display_name or generic |
| 6 | No tog_and_dogs data visible to test_tenant_alpha admin | ❌ Partial leaks | Zero cross-tenant data |

---

## 3. Tactical Google Calendar Fix

### Problem

The `/admin/auth/status` endpoint reads Google OAuth tokens from a global Secrets Manager key (`togs-and-dogs-prod/google/user-tokens`). Any authenticated admin user gets the connection status regardless of their `company_id`.

### Proposed Fix

```python
# In google_auth_handler.py — status endpoint:
company_id = get_current_company_id(event)

# Tactical: only tog_and_dogs has a configured calendar connection
if company_id != 'tog_and_dogs':
    return success({"status": "NOT_CONFIGURED", "message": "Google Calendar is not set up for this business."}, event)

# Existing logic for tog_and_dogs continues unchanged...
```

### Why This Is Safe

- Only affects the status response — does not modify tokens or connections
- tog_and_dogs behavior is completely unchanged
- New tenants see "Not Configured" (correct — they have no Google connection)
- No token data is exposed or modified
- Calendar sync operations already check tenant context before creating events

### Apply Same Pattern to `/admin/auth/google` (Connect)

Even though entitlement enforcement (Phase 1) blocks calendar connect for starter tier, add a defensive company_id check:

```python
# If per-tenant token storage doesn't exist for this company, block connect
if company_id != 'tog_and_dogs':
    return error(400, "Google Calendar connection is not available for your business yet.", event)
```

### What This Does NOT Do

- Does not implement per-tenant token storage (deferred)
- Does not modify the existing tog_and_dogs OAuth connection
- Does not change Secrets Manager structure
- Does not affect calendar sync for tog_and_dogs bookings

---

## 4. Long-Term Google Calendar Design (Deferred)

For future per-tenant calendar support:

| Component | Current (Single-Tenant) | Future (Per-Tenant) |
|-----------|------------------------|---------------------|
| Token storage | `{prefix}/google/user-tokens` (one global secret) | `{prefix}/google/user-tokens/{company_id}` |
| OAuth initiation | Starts flow for global secret | Starts flow scoped to company_id |
| OAuth callback | Stores in global secret | Stores in tenant-specific secret |
| Calendar sync | Reads global secret | Reads `{company_id}` secret |
| Status check | Reads global secret | Reads `{company_id}` secret |
| Health check | One daily check | Per-tenant health checks |

**Not needed for 19K tactical fix.** Implement when a second real business owner needs their own Google Calendar.

---

## 5. Cognito/Staff/Client Filtering Fix

### Problem

Staff and client list endpoints query by `COMPANY#{company_id}` key prefix — this SHOULD already isolate data. However, certain paths may also query Cognito `ListUsers` or use sidebar data that is not company-filtered.

### Likely Root Causes

| Area | Likely Issue |
|------|-------------|
| Staff list API | May query Cognito ListUsers without company_id filter |
| Staff sidebar | Frontend may fetch a global staff list for assignment dropdown |
| Client list | Should be isolated via `COMPANY#{company_id}` query — verify |
| Cognito ListUsers | Returns ALL pool users regardless of custom:company_id |

### Proposed Fix

**Backend (admin_handler.py):**
- Verify `GET /admin/staff` queries `COMPANY#{company_id}` (DynamoDB) — likely already correct
- If a Cognito `ListUsers` call is used for staff data, add `Filter` on `custom:company_id` attribute
- OR: rely solely on DynamoDB STAFF# records (which are already company-scoped)

**Frontend:**
- Verify staff dropdown/sidebar uses the same `/admin/staff` endpoint (should be filtered)
- If sidebar calls a different data source, fix to use the filtered endpoint

**Client list:**
- Verify `GET /admin/clients` queries `COMPANY#{company_id}` — likely already correct
- If showing Cognito users directly, apply same filter

### Expected Outcome

- test_tenant_alpha owner sees empty staff list (only their own owner profile, or truly empty)
- test_tenant_alpha owner sees empty client list
- tog_and_dogs admin sees only their staff/clients (unchanged)

---

## 6. Tenant Profile/Company Display Fix

### Problem

The UI header/profile area shows "Togs & Dogs" for all users regardless of tenant.

### Proposed Tactical Fix

**Option A: Derive from tenant metadata (recommended)**

Add a frontend call to fetch tenant display_name on login:
```
GET /admin/tenant-info  → returns { display_name, company_id, tier, ... }
```

Or reuse existing Platform Admin endpoint if the user is also checking their own tenant:
```
GET /platform/tenants/{company_id}  → but this is platform_admin-only
```

Better: add a lightweight authenticated endpoint that returns the caller's own tenant display_name:
```python
# In admin_handler.py:
if path == '/admin/tenant-info' and http_method == 'GET':
    company_id = get_current_company_id(event)
    tenant = get_item(f"TENANT#{company_id}", "METADATA")
    return success({"display_name": tenant.get('display_name', company_id), "company_id": company_id})
```

**Option B: Use company_id directly as display (simplest)**

If no `GET /admin/tenant-info` endpoint exists, the frontend could display the resolved `company_id` from the JWT claim as the business label until proper metadata fetching is added.

**Header/App Shell Branding:**
- The overall app shell (logo, "powered by" footer) can remain generic or show the platform brand
- The tenant-specific display_name should appear in the profile/business area
- For test_tenant_alpha: show "Test Tenant Alpha" or the company_id slug

---

## 7. Validation Checklist (After 19K/19L Fixes)

| # | Check | Expected |
|---|-------|----------|
| 1 | Log in as tog_and_dogs admin | Existing admin works normally |
| 2 | tog_and_dogs Google Calendar status | "Connected" (unchanged) |
| 3 | tog_and_dogs staff list | Shows only tog_and_dogs staff |
| 4 | tog_and_dogs client list | Shows only tog_and_dogs clients |
| 5 | Log in as test_tenant_alpha owner | Admin loads |
| 6 | test_tenant_alpha Google Calendar | "Not Configured" (not "Connected") |
| 7 | test_tenant_alpha staff list | Empty or owner only |
| 8 | test_tenant_alpha client list | Empty |
| 9 | test_tenant_alpha profile/company label | "Test Tenant Alpha" or approved placeholder |
| 10 | No tog_and_dogs bookings/requests/jobs/pets visible to test_tenant_alpha | Zero cross-tenant data |
| 11 | Platform Admin shows both tenants | Correct for Matthew |
| 12 | Tenant-resolution alarms remain OK | Zero fallback/failed |
| 13 | Entitlement denial for starter features (export, calendar) | 403 as expected |

---

## 8. Recommended Release Sequence

| Release | Scope | Owner |
|---------|-------|-------|
| **19J** | Isolation remediation plan (this document) | ✅ Kiro (done) |
| **19K** | Backend: Google Calendar tenant gate + staff/client Cognito filter fix | AG |
| **19L** | Frontend: tenant display_name in profile/header + sidebar scoping | AG |
| **19M** | Manual revalidation of test_tenant_alpha isolation (re-attempt 19H) | Matthew |
| **19N** | Per-tenant Google OAuth/token storage design (deferred unless needed) | Kiro |

---

## 9. What This Document Does NOT Authorize

- ❌ Code changes
- ❌ Deployment
- ❌ Terraform/AWS changes
- ❌ Cognito user/group modifications
- ❌ Tenant metadata changes
- ❌ Google Calendar token/OAuth changes
- ❌ DynamoDB writes
- ❌ Stripe/Postmark/payment changes
- ❌ Mobile/EAS/TestFlight changes
- ❌ Ryan/tester changes
- ❌ Changing TENANT_RESOLUTION_MODE
- ❌ Disabling the test tenant owner

This is a planning document. Implementation (19K/19L) requires separate approval.
