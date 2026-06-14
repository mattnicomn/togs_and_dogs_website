# Release 11C: Existing Tenant Profile Record Creation Plan

**Status:** Gate A Complete — Awaiting Gate B Approval
**Priority:** Medium (foundational for multi-tenancy)
**Risk to Production:** Very Low (one additive DynamoDB record)
**Terraform Required:** No
**Backend Code Changes:** None
**Scope:** Seed one tenant metadata record for the existing `tog_and_dogs` tenant

---

## 1A. Gate A Validation Results

**Validation commit:** `ed97200e28e25164fdfeaec2d2a14fb48fdd4486`

### Results

| Check | Result |
|-------|--------|
| No existing `TENANT#tog_and_dogs / METADATA` record | ✅ Confirmed — no record exists |
| Existing `COMPANY#tog_and_dogs` records present | ✅ Confirmed — staff/client profiles exist |
| No data mutation during validation | ✅ Confirmed — read-only commands only |

### Blocker Found and Resolved

**Issue:** The originally proposed `owner_cognito_sub` (`74b86488-1011-7029-bb6d-dad984e1463c`) belongs to `admin@toganddogs.com`, NOT to Matthew's actual admin account (`mattnicomn10@gmail.com`).

**Resolution:** Use Matthew Nico's real admin account as the tenant owner:
- `owner_email`: `mattnicomn10@gmail.com`
- `owner_cognito_sub`: `b4a89428-9071-7063-dcad-983d4305dd8c`

**Note:** `admin@toganddogs.com` / `74b86488-...` is treated as a protected root/platform admin account, not the business-tenant owner. It remains in `PROTECTED_ADMIN_SUBS` for guardrail purposes.

---

## 1. Purpose

Create a formal `TENANT#tog_and_dogs` metadata record in DynamoDB that represents the existing business tenant. This establishes the tenant profile model that future multi-tenant features will reference (billing, branding, provisioning, entitlements).

**This release does NOT:**
- Onboard a second tenant
- Enable billing
- Fix tenant enforcement gaps (that's Release 11D+)
- Change any handler behavior
- Modify any existing records

It is a single, additive DynamoDB `put_item` — placing one new record that no existing code reads yet.

---

## 2. Proposed Tenant Metadata Record

### DynamoDB Item Shape

```json
{
  "PK": "TENANT#tog_and_dogs",
  "SK": "METADATA",
  "entity_type": "TENANT",
  "company_id": "tog_and_dogs",
  "display_name": "Tog & Dogs Pet Sitting",
  "owner_email": "mattnicomn10@gmail.com",
  "owner_cognito_sub": "b4a89428-9071-7063-dcad-983d4305dd8c",
  "subscription_tier": "professional",
  "subscription_status": "active",
  "stripe_customer_id": null,
  "stripe_subscription_id": null,
  "trial_ends_at": null,
  "logo_url": null,
  "primary_color": "#c28b1e",
  "secondary_color": "#faf7f2",
  "timezone": "America/New_York",
  "notification_email_from": "support@usmissionhero.com",
  "notification_reply_to": "support@usmissionhero.com",
  "portal_url": "https://toganddogs.usmissionhero.com",
  "google_calendar_connected": true,
  "max_staff": 10,
  "max_clients": 100,
  "max_monthly_bookings": null,
  "max_monthly_notifications": 100,
  "is_active": true,
  "created_at": "2026-01-01T00:00:00Z",
  "updated_at": "2026-06-12T00:00:00Z",
  "created_by": "system_seed",
  "notes": "Initial tenant record seeded during Release 11C multi-tenant foundation."
}
```

### Key Design

| Field | Value | Purpose |
|-------|-------|---------|
| `PK` | `TENANT#tog_and_dogs` | Unique tenant identifier — matches `company_id` used everywhere |
| `SK` | `METADATA` | Standard metadata sort key pattern |
| `entity_type` | `TENANT` | Enables entity-type filtering if needed |
| `company_id` | `tog_and_dogs` | Redundant but consistent with other record types |
| `owner_email` | `mattnicomn10@gmail.com` | Ryan/Matthew's admin account |
| `owner_cognito_sub` | `b4a89428-...` | Matthew's actual admin Cognito sub |
| `subscription_tier` | `"professional"` | Placeholder — all features currently available |
| `subscription_status` | `"active"` | Placeholder — no billing enforcement yet |
| Stripe fields | `null` | Placeholders for future Stripe integration |
| Branding fields | Default brand colors | Current design system values |
| Limit fields | Current production limits | From `locals.tf` notification config |

---

## 3. Read-Before-Write Validation Steps

Before writing the tenant record, AG must verify:

### Step 1: Confirm No Existing Tenant Record

```bash
aws dynamodb get-item \
  --table-name togs-and-dogs-prod-data \
  --key '{"PK": {"S": "TENANT#tog_and_dogs"}, "SK": {"S": "METADATA"}}' \
  --profile usmissionhero-website-prod
```

**Expected:** Empty response (no `Item` field). If a record already exists, STOP and report.

### Step 2: Confirm Existing Records Use `tog_and_dogs`

```bash
aws dynamodb scan \
  --table-name togs-and-dogs-prod-data \
  --filter-expression "begins_with(PK, :prefix)" \
  --expression-attribute-values '{":prefix": {"S": "COMPANY#tog_and_dogs"}}' \
  --select COUNT \
  --profile usmissionhero-website-prod
```

**Expected:** Count > 0 (staff and client profiles exist under this company_id).

### Step 3: Confirm No Data Mutation During Validation

Both commands above are **read-only** (`get-item` and `scan` with `--select COUNT`). No data is modified.

---

## 4. Implementation Gates

| Gate | Action | Who | Produces |
|------|--------|-----|---------|
| **Gate A** | Run read-only validation (Steps 1-2 above) | AG | Confirmation no existing tenant record; existing data uses `tog_and_dogs` |
| **Gate B** | Write exactly one tenant metadata record | AG (with Matthew approval) | Single `put_item` to DynamoDB |
| **Gate C** | Read-back verification | AG | Confirm written record matches expected shape |
| **Gate D** | Documentation closeout | AG/Kiro | Closeout note committed |

**Gate B requires Matthew's explicit approval.** Gates A and C are read-only.

---

## 5. AG Execution Prompt (Gate B — Write)

**⚠️ DO NOT RUN UNTIL MATTHEW EXPLICITLY APPROVES GATE B**

```bash
aws dynamodb put-item \
  --table-name togs-and-dogs-prod-data \
  --item '{
    "PK": {"S": "TENANT#tog_and_dogs"},
    "SK": {"S": "METADATA"},
    "entity_type": {"S": "TENANT"},
    "company_id": {"S": "tog_and_dogs"},
    "display_name": {"S": "Tog & Dogs Pet Sitting"},
    "owner_email": {"S": "mattnicomn10@gmail.com"},
    "owner_cognito_sub": {"S": "b4a89428-9071-7063-dcad-983d4305dd8c"},
    "subscription_tier": {"S": "professional"},
    "subscription_status": {"S": "active"},
    "stripe_customer_id": {"NULL": true},
    "stripe_subscription_id": {"NULL": true},
    "trial_ends_at": {"NULL": true},
    "logo_url": {"NULL": true},
    "primary_color": {"S": "#c28b1e"},
    "secondary_color": {"S": "#faf7f2"},
    "timezone": {"S": "America/New_York"},
    "notification_email_from": {"S": "support@usmissionhero.com"},
    "notification_reply_to": {"S": "support@usmissionhero.com"},
    "portal_url": {"S": "https://toganddogs.usmissionhero.com"},
    "google_calendar_connected": {"BOOL": true},
    "max_staff": {"N": "10"},
    "max_clients": {"N": "100"},
    "max_monthly_notifications": {"N": "100"},
    "is_active": {"BOOL": true},
    "created_at": {"S": "2026-01-01T00:00:00Z"},
    "updated_at": {"S": "2026-06-12T00:00:00Z"},
    "created_by": {"S": "system_seed"},
    "notes": {"S": "Initial tenant record seeded during Release 11C multi-tenant foundation."}
  }' \
  --condition-expression "attribute_not_exists(PK)" \
  --profile usmissionhero-website-prod
```

**Notes:**
- `--condition-expression "attribute_not_exists(PK)"` prevents accidental overwrite if the record already exists
- This is a single atomic write — no partial state possible
- No other records are touched

---

## 6. Read-Back Verification (Gate C)

After Gate B succeeds:

```bash
aws dynamodb get-item \
  --table-name togs-and-dogs-prod-data \
  --key '{"PK": {"S": "TENANT#tog_and_dogs"}, "SK": {"S": "METADATA"}}' \
  --profile usmissionhero-website-prod
```

**Verify:** All fields match the expected shape from Section 2.

---

## 7. Rollback

If the record needs to be removed for any reason:

```bash
aws dynamodb delete-item \
  --table-name togs-and-dogs-prod-data \
  --key '{"PK": {"S": "TENANT#tog_and_dogs"}, "SK": {"S": "METADATA"}}' \
  --profile usmissionhero-website-prod
```

**Impact of rollback:** Zero. No existing code reads this record. Deleting it has no effect on any handler, notification, calendar, or mobile app behavior.

---

## 8. What This Release Does NOT Do

| ❌ Does NOT | Reason |
|-------------|--------|
| Onboard a second tenant | Only seeds the existing tenant's profile |
| Enable billing/payment | Stripe fields are null placeholders |
| Fix tenant enforcement gaps | That's Release 11D+ |
| Change handler behavior | No code references this record yet |
| Modify existing records | Only creates one new record |
| Affect Ryan's workflow | Record is invisible to the app |
| Require Terraform | No infrastructure changes |
| Require code deployment | No Lambda/frontend changes |

---

## 9. Relationship to Future Releases

| Release | What It Uses From This Record |
|---------|-------------------------------|
| **11D** | Tenant enforcement — handlers validate `company_id` against tenant record |
| **11E** | Cognito `custom:company_id` — resolves to this tenant |
| **12C** | Stripe billing — writes `stripe_customer_id` and `subscription_status` to this record |
| **13A** | Branding — reads `logo_url`, `primary_color`, `display_name` from this record |
| **Future** | New tenant provisioning — creates additional TENANT# records with same shape |

---

## 10. Acceptance Criteria

- [ ] Gate A: Read-only validation confirms no existing TENANT# record
- [ ] Gate A: Existing COMPANY#tog_and_dogs records exist (staff/client profiles)
- [ ] Gate B: Single `put_item` succeeds with condition check
- [ ] Gate C: Read-back matches expected shape exactly
- [ ] No existing records modified
- [ ] No handler behavior changed
- [ ] No app/mobile/web behavior changed
- [ ] Rollback command documented and tested (optional)

---

## 11. What This Document Does NOT Authorize

- ❌ Writing to DynamoDB (requires Gate B approval)
- ❌ Modifying any existing records
- ❌ Running any code deployments
- ❌ Modifying Terraform/AWS resources
- ❌ Modifying Cognito
- ❌ Creating a second tenant
- ❌ Enabling billing features

This is a planning document. Gate B execution requires separate explicit approval from Matthew.
