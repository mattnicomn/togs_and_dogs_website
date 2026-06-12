# Release 11B: Tenant Data Model & DynamoDB Key Audit

**Status:** Audit Complete
**Priority:** High (informs all multi-tenancy implementation)
**Risk to Production:** None (documentation-only)
**Terraform Required:** No
**Backend Changes:** None (audit only)
**Scope:** Analysis of current tenant isolation patterns, gaps, and recommendations

---

## 1. Current Tenant Model Summary

### How company_id Works Today

| Component | Implementation | Multi-Tenant Safe? |
|-----------|---------------|-------------------|
| `DEFAULT_COMPANY_ID` | Env var → `"tog_and_dogs"` | ✅ Configurable |
| `get_current_company_id(event)` | Reads `custom:company_id` JWT claim, falls back to `DEFAULT_COMPANY_ID` | ✅ Ready for multi-tenant |
| `validate_tenant_ownership(item, event)` | Compares item's `company_id` to caller's | ⚠️ **Defined but NEVER called** |
| Staff/Client profiles | Stored under `PK: COMPANY#{company_id}` | ✅ Tenant-scoped by key |
| REQ/JOB records | Store `company_id` as an attribute (not in PK) | ⚠️ Must filter after read |
| PET records | `PK: PET#{id}`, `SK: CLIENT#{client_id}` — no company_id in key | ⚠️ Indirect scoping via client |
| Notification quota | Hardcoded `"QUOTA#tog_and_dogs"` | ❌ Must parameterize |
| Notification ledger | Stores `company_id` from record (with `tog_and_dogs` fallback) | ⚠️ Partially scoped |

---

## 2. Safe Patterns Found (Already Multi-Tenant Ready)

### ✅ Staff & Client Profiles — Properly Scoped

```
PK: COMPANY#{company_id}
SK: STAFF#{staff_id} or CLIENT#{client_id}
```

All handler queries for staff/client profiles use `get_current_company_id(event)` to build the PK. A different tenant's staff/clients are naturally invisible. **No changes needed.**

### ✅ `get_current_company_id()` — Used Everywhere

Called in 30+ locations across all handlers. The function already supports a `custom:company_id` JWT claim as the primary resolution path, falling back to env var. **Ready for dynamic tenancy** once Cognito users have the custom attribute.

### ✅ Admin Booking Creation — Tenant-Isolated

`intake_handler.py` (`_handle_admin_created_booking`):
- Resolves `company_id` from JWT
- Verifies client belongs to admin's company (`get_item(f"COMPANY#{company_id}", f"CLIENT#{client_id}")`)
- Returns error if cross-tenant

### ✅ StatusIndex Query — Filtered by company_id

```python
"FilterExpression": "(company_id = :cid OR attribute_not_exists(company_id)) AND contains(PK, :req_tag)"
```

Both ALL-scan and status-query paths apply company_id filtering.

### ✅ Assignment Handler — Validates Staff Belongs to Company

Queries `COMPANY#{company_id}` + `STAFF#` prefix to find assignable staff. Can't assign cross-tenant workers.

---

## 3. Risky Patterns Found (Need Multi-Tenant Fixes)

### ❌ Risk 1: `validate_tenant_ownership()` — Dead Code

**Location:** `src/backend/common/auth.py` line 223

The function is defined but **never imported or called** from any handler. This means:
- `get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")` returns the record regardless of which tenant owns it
- If a user crafts a request with a known `request_id` + `client_id` from another tenant, the backend will process it

**Impact:** Low currently (single tenant), HIGH in multi-tenant.

**Fix needed:** Call `validate_tenant_ownership(item, event)` after every direct `get_item` of REQ/JOB/PET records in handlers that accept user-provided IDs.

### ❌ Risk 2: REQ/JOB Records — No company_id in PK

```
PK: REQ#{request_id}    ← UUID, globally unique
SK: CLIENT#{client_id}   ← UUID, globally unique
Attribute: company_id = "tog_and_dogs"
```

Direct `get_item` calls don't verify `company_id`. Any user who knows a `request_id` and `client_id` can access that record regardless of their tenant.

**Affected handlers:**
- `review_handler.py` — `get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")` (no tenant check after)
- `cancellation_handler.py` — same pattern
- `assignment_handler.py` — `get_item(f"REQ#{req_id}", f"CLIENT#{client_id}")`
- `admin_handler.py` single-request GET — `get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")`
- `job_handler.py` — `get_item(f"REQ#{request_id}", f"CLIENT#{client_id}")`

**Fix needed:** After every `get_item` for REQ/JOB records, verify `item.get('company_id') == get_current_company_id(event)`.

### ❌ Risk 3: Notification Quota — Hardcoded Tenant

```python
# In service.py:
get_item("QUOTA#tog_and_dogs", f"MONTH#{month_key}")
table.update_item(Key={"PK": "QUOTA#tog_and_dogs", "SK": f"MONTH#{month_key}"}, ...)
```

Notification quota tracking uses hardcoded `"tog_and_dogs"` instead of the record's `company_id`. In multi-tenant mode, all tenants would share one quota counter.

**Fix needed:** Use `company_id` from the notification record to scope quota.

### ❌ Risk 4: Export Endpoint — Full Table Scan Without Tenant Filtering

```python
# admin_handler.py export:
response = _table.scan(**scan_kwargs)  # No filter!
items = response.get('Items', [])
# Then categorizes by entity_type — but includes ALL tenants
```

The export returns every record in DynamoDB regardless of the caller's company.

**Fix needed:** Add `company_id` filter to export scan. Or post-filter results by caller's company.

### ⚠️ Risk 5: PET Records — Indirect Tenant Scoping

```
PK: PET#{pet_id}
SK: CLIENT#{client_id}
```

No `company_id` in the key. Pets are only indirectly scoped (owned by a client who belongs to a company). If someone guesses a `pet_id` + `client_id`, they can access it cross-tenant.

**Impact:** Low (pet IDs are UUIDs, hard to guess). But a proper multi-tenant system should verify the client belongs to the caller's company before serving pet data.

### ⚠️ Risk 6: `OR attribute_not_exists(company_id)` Fallback

```python
"(company_id = :cid OR attribute_not_exists(company_id))"
```

This is used in ALL/scan queries to handle legacy records without `company_id`. In multi-tenant mode, orphan records (no `company_id`) would be visible to ALL tenants.

**Fix needed:** Migrate all records to have `company_id`. Then remove the `attribute_not_exists` fallback.

---

## 4. Endpoints Needing Tenant Enforcement Audit

| Handler | Endpoint | Current Scoping | Risk Level |
|---------|----------|----------------|-----------|
| `review_handler` | POST /admin/review | ❌ No tenant check after get_item | Medium |
| `cancellation_handler` | POST /client/cancel, PUT /admin/cancel/decision | ❌ No tenant check | Medium |
| `assignment_handler` | POST /admin/assign | Partial — verifies staff belongs to company | Low |
| `admin_handler` GET single request | GET /admin/requests?requestId&clientId | ❌ No tenant check | Medium |
| `admin_handler` job/complete | POST /admin/job/complete | ❌ No tenant check on JOB | Medium |
| `admin_handler` export | GET /admin/export-data | ❌ Full table scan, no tenant filter | High |
| `pet_handler` | GET/PUT /admin/pets/{petId} | ❌ No tenant check on PET | Low |
| `job_handler` | Internal Lambda trigger | Uses request's company_id | Low |

---

## 5. Proposed Tenant Provisioning Record Model

### New Record: Tenant/Company Profile

```
PK: TENANT#{company_id}
SK: METADATA

Attributes:
  company_id:       "tog_and_dogs"
  display_name:     "Tog & Dogs Pet Sitting"
  owner_email:      "mattnicomn10@gmail.com"
  owner_cognito_sub: "74b86488-..."
  
  # Subscription (future)
  subscription_tier: "professional"  (starter|professional|premium|enterprise)
  subscription_status: "active"      (active|trial|past_due|cancelled|suspended)
  stripe_customer_id: "cus_xxx"      (future)
  stripe_subscription_id: "sub_xxx"  (future)
  trial_ends_at: "2026-07-15"        (future)
  
  # Branding (future)
  logo_url:         null             (S3 URL, future)
  primary_color:    "#c28b1e"        (default brand gold)
  secondary_color:  "#faf7f2"        (default cream)
  
  # Settings
  timezone:         "America/New_York"
  notification_email_from: "support@usmissionhero.com"
  google_calendar_connected: true
  
  # Limits
  max_staff:        5
  max_clients:      100
  max_monthly_bookings: null  (unlimited for professional)
  max_monthly_notifications: 100
  
  # Metadata
  is_active:        true
  created_at:       "2026-01-15T..."
  updated_at:       "2026-06-10T..."
  entity_type:      "TENANT"
```

### Migration Plan for Existing Data

1. Create a `TENANT#tog_and_dogs` / `METADATA` record for the existing tenant
2. All existing records already have `company_id: "tog_and_dogs"` (or should)
3. No data migration needed for existing records — just add the tenant profile record
4. Future tenants get a new `TENANT#{company_id}` record on provisioning

---

## 6. Cognito / company_id Recommendations

### Current State

- Cognito users do NOT have `custom:company_id` attribute
- `get_current_company_id()` always falls through to `DEFAULT_COMPANY_ID` env var
- This means ALL users are treated as belonging to `tog_and_dogs`

### Multi-Tenant Path

1. Add `custom:company_id` as a custom attribute in the Cognito User Pool (one-time setting change)
2. Set `custom:company_id = "tog_and_dogs"` on all existing users
3. New users provisioned with their tenant's `company_id`
4. `get_current_company_id()` already reads this claim — no code change needed for resolution

### Risk

If a user modifies their own `custom:company_id` claim, they could access another tenant. Mitigation: make it an admin-only attribute (not user-modifiable) via Cognito schema settings.

---

## 7. Tenant Isolation Acceptance Criteria (For Future Releases)

Before declaring multi-tenancy safe:

- [ ] Every `get_item` for REQ/JOB/PET followed by `validate_tenant_ownership(item, event)`
- [ ] Export endpoint filters by caller's company_id
- [ ] Notification quota uses per-tenant counter key
- [ ] All list/scan queries include `company_id` filter (no `attribute_not_exists` fallback)
- [ ] Cognito users have `custom:company_id` attribute
- [ ] New tenant provisioning creates TENANT# record
- [ ] Cross-tenant access returns 403 (not 404)
- [ ] Audit log captures tenant context
- [ ] Stress test: create 2 tenants, verify complete data isolation

---

## 8. Migration Considerations

| Step | Risk | Order |
|------|------|-------|
| Create TENANT# record for tog_and_dogs | None | First |
| Add `custom:company_id` to Cognito pool schema | Low (additive) | Second |
| Set `custom:company_id` on existing Cognito users | Low | Third |
| Add `validate_tenant_ownership` calls in handlers | Medium (behavior change) | Fourth — with thorough testing |
| Remove `attribute_not_exists` fallback | Medium | After all records have company_id |
| Parameterize notification quota key | Low | Anytime |
| Add export tenant filtering | Low | Anytime |

---

## 9. Risks / Open Questions

| Question | Impact | Resolution |
|---------|--------|-----------|
| Can Cognito custom attributes be added without pool recreation? | Blocking if no | Yes — custom attributes can be added to existing pools |
| Will adding tenant validation break existing workflows for Ryan? | Medium | Test thoroughly; Ryan's requests all have `company_id: "tog_and_dogs"` |
| Should REQ/JOB keys be redesigned to include company_id? | Architecture | ❌ No — UUIDs are globally unique; filter after read is sufficient |
| How do we handle records with null/missing company_id? | Migration | Backfill with `"tog_and_dogs"` before removing the fallback |
| Will multiple tenants share the same Google Calendar? | Must separate | Each tenant needs their own Google OAuth tokens |
| Will multiple tenants share the same Postmark account? | OK for MVP | Single Postmark server with different `from` addresses per tenant (or separate streams) |

---

## 10. Proposed Implementation Sequence

| Release | Scope | Risk |
|---------|-------|------|
| **11C** | Create TENANT# record for tog_and_dogs (additive DynamoDB write) | Very Low |
| **11D** | Add Cognito `custom:company_id` attribute to user pool | Low |
| **11E** | Set `custom:company_id` on all existing Cognito users | Low |
| **11F** | Add `validate_tenant_ownership` to all direct-get handlers | Medium |
| **11G** | Parameterize notification quota key | Low |
| **11H** | Add company_id filter to export endpoint | Low |
| **11I** | Remove `attribute_not_exists` fallback (after backfill confirmed) | Medium |
| **11J** | Billing/Stripe integration planning | — |

---

## 11. Summary

### Safe (No Action Needed)
- Staff/Client profile storage (`COMPANY#` PK) ✅
- `get_current_company_id()` usage ✅
- Admin booking tenant verification ✅
- Assignment handler staff validation ✅
- Request list queries with company_id filter ✅

### Risky (Needs Multi-Tenant Fixes)
- `validate_tenant_ownership()` never called ❌
- REQ/JOB/PET direct-gets have no post-read tenant check ❌
- Notification quota is hardcoded single-tenant ❌
- Export endpoint scans entire table ❌
- `attribute_not_exists(company_id)` fallback leaks data in multi-tenant ❌

### Key Insight
The **architecture is designed for multi-tenancy** (company_id exists everywhere, resolution function is correct, profiles are scoped). The **implementation has gaps** where enforcement isn't applied. These are fixable with targeted handler updates — no data model redesign needed.
