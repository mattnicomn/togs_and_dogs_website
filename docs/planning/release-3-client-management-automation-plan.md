# Release 3: Client Management Automation — Refined Implementation Plan

**Date:** 2026-05-12  
**Status:** Plan Only — No Implementation Yet  
**Prerequisite:** Release 2 deployed and validated  
**Objective:** Auto-create client profiles on CUSTOMER_INTAKE approval and improve client search/filter.

---

## 1. Current Client Profile Data Model

### DynamoDB Structure

```
PK: COMPANY#<company_id>     (e.g., COMPANY#tog_and_dogs)
SK: CLIENT#<client_id>        (e.g., CLIENT#client_a1b2c3d4)
```

### Required Fields

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `PK` | String | System | `COMPANY#<company_id>` |
| `SK` | String | System | `CLIENT#<client_id>` |
| `company_id` | String | System | Tenant scoping |
| `client_id` | String | System | `client_<8-char-uuid>` |
| `display_name` | String | Admin input | Required on creation |
| `email` | String | Admin input | Required, unique per active client |
| `is_active` | Boolean | System | Default `true` |
| `created_at` | String (ISO) | System | |
| `updated_at` | String (ISO) | System | |

### Optional Fields

| Field | Type | Source | Notes |
|-------|------|--------|-------|
| `phone` | String | Admin input | |
| `address` | String | Admin input | |
| `emergency_contact` | String | Admin input | Single text field |
| `notes` | String | Admin input | Internal admin notes |
| `portal_enabled` | Boolean | Admin action | Gates client portal access. Default `false` for profile-only, `true` for onboarded |
| `cognito_sub` | String | Cognito link | `null` until Cognito user is created/linked |
| `cognito_status` | String | Cognito sync | `not_linked`, `FORCE_CHANGE_PASSWORD`, `CONFIRMED`, `deleted` |
| `cognito_username` | String | Cognito sync | Usually the email |
| `is_virtual` | Boolean | System | `true` for Cognito-only users without DynamoDB profile |

### Active/Inactive/Disabled Flags

| State | `is_active` | `portal_enabled` | `cognito_status` | Meaning |
|-------|-------------|-------------------|-------------------|---------|
| Active + Portal | `true` | `true` | `CONFIRMED` | Full access |
| Active + No Portal | `true` | `false` | `not_linked` | Profile exists, no login |
| Disabled | `false` | `false` | varies | Admin disabled, cannot log in |
| Invited | `true` | `true` | `FORCE_CHANGE_PASSWORD` | Awaiting first login |

### Relationships

| Related Entity | Relationship | Current Linkage |
|----------------|-------------|-----------------|
| Intake Request (REQ#) | One client → many requests | REQ has `client_id` (UUID generated at submission, NOT the profile client_id) |
| Pet Record (PET#) | One client → many pets | PET SK = `CLIENT#<client_id>` |
| Cognito User | One client → one login | `cognito_sub` on profile |
| Staff Record | No direct relationship | Staff are separate entities |

### Critical Gap

The `client_id` on a REQ record is a UUID generated at intake submission time. It is **NOT** the same as the `client_id` on a Client Management profile. There is currently **no link** between an intake request and a client profile unless:
- The client is authenticated (portal path resolves `client_id` from Cognito)
- Admin manually creates a profile and the system happens to use the same ID (it doesn't)

This is the core problem Release 3 solves.

---

## 2. Auto-Create / Auto-Link Logic

### Trigger Condition

Auto-profile logic runs ONLY when:
- Status transitions to `APPROVED`
- AND `workflow_type == CUSTOMER_INTAKE`
- AND the request does NOT already have a `linked_client_profile_id`

It does NOT run for:
- `VISIT_BOOKING` workflow (client already has a profile)
- Re-approvals (request already linked)
- Any other status transition

### Exact Logic

```
1. Normalize email:
   email = request_item['client_email'].lower().strip()

2. If email is empty/missing:
   → Set link_status = 'SKIPPED_NO_EMAIL'
   → Log warning
   → Return (approval continues)

3. Query all client profiles for this company:
   COMPANY#<company_id> / CLIENT#*

4. Search for exact email match (case-insensitive):
   matches = [p for p in profiles if p['email'].lower() == email]

5. If len(matches) > 1:
   → Multiple profiles with same email (data integrity issue)
   → Set link_status = 'NEEDS_REVIEW_MULTIPLE_MATCHES'
   → Log warning with match details
   → Do NOT auto-link
   → Return (approval continues)

6. If len(matches) == 1:
   existing = matches[0]
   
   6a. If existing['is_active'] == True:
       → Link request to existing profile
       → Set link_status = 'LINKED_EXISTING'
       → Update profile: append to intake_request_ids, update latest_request_id
       → Return
   
   6b. If existing['is_active'] == False:
       → Check if manually disabled (cognito_status == 'deleted' or admin_disabled flag)
       → If manually disabled: Set link_status = 'SKIPPED_MANUALLY_DISABLED'
       → If auto-deactivated or just inactive:
         → Reactivate: is_active = True (but NOT portal_enabled)
         → Link request to profile
         → Set link_status = 'REACTIVATED_AND_LINKED'
         → Return

7. If len(matches) == 0:
   → Create new client profile:
     - client_id: client_<8-char-uuid>
     - display_name: request_item['client_name']
     - email: normalized email
     - phone: None (not collected on intake currently)
     - is_active: True
     - portal_enabled: False
     - cognito_sub: None
     - cognito_status: 'not_linked'
     - auto_created: True
     - auto_created_at: now
     - auto_created_from: request_id
   → Link request to new profile
   → Set link_status = 'CREATED_NEW'
   → Return
```

### Phone/Name Secondary Matching (Informational Only)

After the primary email match resolves (or creates), optionally log if:
- A different profile has the same phone number → `INFO: Phone match detected`
- A different profile has the same display_name → No action (names aren't unique)

These are logged for admin awareness but do NOT affect the auto-link decision.

---

## 3. Duplicate Handling

### Scenario Matrix

| Scenario | Email Match | Action | link_status |
|----------|-------------|--------|-------------|
| New email, no match | None | Create new profile | `CREATED_NEW` |
| Exact email match, active | 1 active | Link to existing | `LINKED_EXISTING` |
| Exact email match, inactive (auto) | 1 inactive | Reactivate + link | `REACTIVATED_AND_LINKED` |
| Exact email match, inactive (manual) | 1 disabled | Skip link | `SKIPPED_MANUALLY_DISABLED` |
| Multiple email matches | 2+ | Flag for review | `NEEDS_REVIEW_MULTIPLE_MATCHES` |
| Phone match, different email | 0 email | Create new profile | `CREATED_NEW` (phone match logged) |
| Name match, different email | 0 email | Create new profile | `CREATED_NEW` |
| Email missing on request | N/A | Skip entirely | `SKIPPED_NO_EMAIL` |
| Client changed email | 0 email match | Create new profile | `CREATED_NEW` (admin merges later) |

### How Duplicate Warnings Are Surfaced to Ryan

1. **In the approval response message:** If `link_status` is anything other than `CREATED_NEW` or `LINKED_EXISTING`, include a note in the API response message (e.g., "Approved. Note: Multiple client profiles found for this email — please review Client Management.")

2. **In the admin notification:** If the notification system is active, include the link_status in the notification context.

3. **In the request record:** The `client_profile_link_status` field is visible in the CareCard or request detail view, so Ryan can see if something needs attention.

4. **NOT as a blocking modal** — Approval always succeeds. Warnings are informational.

---

## 4. Request/Profile Linkage

### Fields on the REQ Record

| Field | Type | Set By | Notes |
|-------|------|--------|-------|
| `linked_client_profile_id` | String | Auto-profile logic | The `client_id` of the linked Client Management profile |
| `client_profile_linked_at` | String (ISO) | Auto-profile logic | When the link was established |
| `client_profile_link_status` | String (enum) | Auto-profile logic | See status values below |
| `client_profile_link_method` | String | Auto-profile logic | `auto_email_match`, `auto_created`, `auto_reactivated`, `manual` |

### Link Status Values

| Value | Meaning |
|-------|---------|
| `CREATED_NEW` | New profile auto-created from this request |
| `LINKED_EXISTING` | Linked to pre-existing active profile |
| `REACTIVATED_AND_LINKED` | Inactive profile reactivated and linked |
| `SKIPPED_NO_EMAIL` | No email on request, could not match |
| `SKIPPED_MANUALLY_DISABLED` | Matched profile was manually disabled |
| `NEEDS_REVIEW_MULTIPLE_MATCHES` | Multiple profiles match, admin must resolve |
| `FAILED` | Auto-profile logic threw an exception |
| `null` / absent | Not yet processed (pre-Release 3 records) |

### Fields on the Client Profile

| Field | Type | Set By | Notes |
|-------|------|--------|-------|
| `source_request_id` | String | Auto-profile (on creation only) | The request_id that triggered profile creation |
| `first_request_id` | String | Auto-profile (on creation only) | Same as source_request_id |
| `latest_request_id` | String | Auto-profile (on each link) | Updated each time a new request is linked |
| `intake_request_ids` | List[String] | Auto-profile (append) | All linked request_ids |
| `request_count` | Number | Auto-profile (increment) | Count of linked requests |
| `last_request_date` | String (ISO) | Auto-profile | Date of most recent linked request |
| `auto_created` | Boolean | Auto-profile | `true` if created by automation |
| `auto_created_at` | String (ISO) | Auto-profile | When auto-created |
| `auto_created_from` | String | Auto-profile | request_id that triggered creation |
| `became_client_at` | String (ISO) | Auto-profile | When first request was approved (≈ client relationship start) |

---

## 5. Audit and Notes

### Events That Generate Audit Entries

| Event | Where Logged | Content |
|-------|-------------|---------|
| New client profile auto-created | REQ audit_log + CloudWatch | `{action: "CLIENT_PROFILE_AUTO_CREATED", client_profile_id, email}` |
| Request linked to existing profile | REQ audit_log + CloudWatch | `{action: "CLIENT_PROFILE_LINKED", client_profile_id, email, method}` |
| Inactive profile reactivated | REQ audit_log + CloudWatch | `{action: "CLIENT_PROFILE_REACTIVATED", client_profile_id}` |
| Possible duplicate detected | CloudWatch only | `WARNING: [Req:X] Phone match detected for different profile` |
| Multiple email matches | REQ audit_log + CloudWatch | `{action: "CLIENT_PROFILE_MULTIPLE_MATCHES", matches: [...]}` |
| Auto-profile creation failed | REQ audit_log + CloudWatch | `{action: "CLIENT_PROFILE_FAILED", error: "..."}` |

### Audit Entry Format (appended to REQ record's audit_log)

```python
{
    "action": "CLIENT_PROFILE_AUTO_CREATED",
    "timestamp": "2026-05-12T...",
    "client_profile_id": "client_abc12345",
    "email": "client@example.com",
    "link_status": "CREATED_NEW",
    "updated_by": "system_auto_profile"
}
```

---

## 6. Failure Handling

### Principle: Approval NEVER fails because of profile automation.

### Implementation

```python
# In review_handler.py, after successful APPROVED transition:
if new_status == 'APPROVED' and workflow_type == WorkflowType.CUSTOMER_INTAKE:
    try:
        from common.client_profile import auto_create_or_link_client_profile
        profile_result = auto_create_or_link_client_profile(
            request_item=request_item,
            request_id=request_id,
            client_id=client_id,
            company_id=company_id,
            updated_by=updated_by
        )
        # Append result to response message if noteworthy
        if profile_result.get('link_status') not in ['CREATED_NEW', 'LINKED_EXISTING']:
            # Include warning in response
            final_msg += f" (Client profile: {profile_result.get('message', 'needs review')})"
    except Exception as profile_err:
        # FAIL-SAFE: Log but do not block approval
        print(f"WARNING: [Req:{request_id}] Client profile automation failed: {profile_err}")
        # Mark the request so admin knows it needs attention
        try:
            table.update_item(
                Key={'PK': f"REQ#{request_id}", 'SK': f"CLIENT#{client_id}"},
                UpdateExpression="SET client_profile_link_status = :s",
                ExpressionAttributeValues={":s": "FAILED"}
            )
        except:
            pass  # Even this failure shouldn't block
```

### Failure Recovery

If `client_profile_link_status == 'FAILED'`:
- Admin sees a subtle indicator in the request detail
- Admin can manually create the profile via Client Management
- Admin can re-trigger auto-profile by moving the request back to PENDING_REVIEW and re-approving (not ideal but works)
- Future enhancement: "Retry Profile Link" button in CareCard

---

## 7. Client Management UI Updates

### Search Bar (MVP — Client-Side)

Add a search input above the client list:

```jsx
<input
  type="text"
  placeholder="Search by name, email, phone, or notes..."
  value={clientSearch}
  onChange={(e) => setClientSearch(e.target.value)}
/>
```

Filter logic:
```javascript
const filteredClients = clientList.filter(c => {
  if (!clientSearch) return true;
  const term = clientSearch.toLowerCase();
  return (
    (c.display_name || '').toLowerCase().includes(term) ||
    (c.email || '').toLowerCase().includes(term) ||
    (c.phone || '').toLowerCase().includes(term) ||
    (c.notes || '').toLowerCase().includes(term)
  );
});
```

### Source Request Indicator

On each client card, if `auto_created` is true:
```jsx
{c.auto_created && (
  <span className="badge-auto" style={{ fontSize: '0.75rem', opacity: 0.7 }}>
    Auto-created from intake
  </span>
)}
```

### Linked Request Count

```jsx
{c.request_count > 0 && (
  <span className="badge-light">{c.request_count} request{c.request_count > 1 ? 's' : ''}</span>
)}
```

### Link Status Warning (in CareCard or Request Detail)

If `client_profile_link_status` is `NEEDS_REVIEW_MULTIPLE_MATCHES` or `FAILED`:
```jsx
{item.client_profile_link_status === 'NEEDS_REVIEW_MULTIPLE_MATCHES' && (
  <div className="warning-banner">⚠️ Multiple client profiles match this email. Please review Client Management.</div>
)}
{item.client_profile_link_status === 'FAILED' && (
  <div className="warning-banner">⚠️ Client profile could not be auto-created. Please create manually.</div>
)}
```

### What NOT to Change

- Do not redesign the card layout
- Do not add a spreadsheet/table view
- Do not add inline editing of client fields from the request list
- Do not add bulk client operations
- Keep the existing "Add New Client Profile" / "Onboard" form as-is

---

## 8. Security / RBAC

### Confirmed Safeguards

| Check | Status | Notes |
|-------|--------|-------|
| Only owner/admin can approve CUSTOMER_INTAKE | ✅ | `review_handler.py` enforces `role not in ['owner', 'admin']` for APPROVED |
| Staff cannot trigger profile automation directly | ✅ | Staff cannot approve intake requests |
| No Cognito users created by automation | ✅ | `cognito_sub: None`, `cognito_status: 'not_linked'` |
| No portal access granted by automation | ✅ | `portal_enabled: False` |
| Protected admin/staff records not modified | ✅ | Auto-profile only creates/modifies CLIENT# records |
| Public intake cannot create profiles directly | ✅ | Profile creation only triggers on APPROVED transition (admin action) |
| Auto-profile cannot overwrite existing profile data | ✅ | If profile exists, only `intake_request_ids` and `latest_request_id` are updated |
| Auto-profile cannot escalate permissions | ✅ | New profiles have no Cognito link, no portal access |

### What Auto-Profile Does NOT Do

- Does NOT create Cognito users
- Does NOT send welcome emails
- Does NOT enable portal access
- Does NOT modify staff records
- Does NOT modify protected accounts
- Does NOT grant any permissions
- Does NOT expose client data publicly
- Does NOT run on public intake submission (only on admin approval)

---

## 9. Validation Plan

### TC-01: Approve New Customer — New Email

| Step | Action | Expected |
|------|--------|----------|
| 1 | Submit public intake (newclient@test.com) | REQ created, PENDING_REVIEW |
| 2 | Admin approves | REQ → APPROVED |
| 3 | Check Client Management | New profile: display_name from intake, email, is_active=true, portal_enabled=false |
| 4 | Check profile fields | `auto_created: true`, `source_request_id` set, `cognito_sub: null` |
| 5 | Check REQ record | `linked_client_profile_id` set, `client_profile_link_status: CREATED_NEW` |
| 6 | Check Cognito | No new user created |

### TC-02: Approve New Customer — Existing Client Email

| Step | Action | Expected |
|------|--------|----------|
| 1 | Client profile exists (existing@test.com, is_active=true) | |
| 2 | Submit intake with same email | REQ created |
| 3 | Admin approves | REQ → APPROVED |
| 4 | Check Client Management | No new profile created |
| 5 | Check existing profile | `intake_request_ids` updated, `latest_request_id` set |
| 6 | Check REQ record | `linked_client_profile_id` = existing profile's client_id, `link_status: LINKED_EXISTING` |

### TC-03: Approve New Customer — Same Phone, Different Email

| Step | Action | Expected |
|------|--------|----------|
| 1 | Profile exists: email=a@test.com, phone=555-1234 | |
| 2 | Submit intake: email=b@test.com (phone not collected on intake) | |
| 3 | Admin approves | REQ → APPROVED |
| 4 | Check Client Management | New profile created (b@test.com) |
| 5 | Check logs | No phone match warning (phone not on intake form currently) |
| 6 | Check REQ record | `link_status: CREATED_NEW` |

### TC-04: Approve New Customer — Same Name, Different Email

| Step | Action | Expected |
|------|--------|----------|
| 1 | Profile exists: display_name="John Smith", email=john1@test.com | |
| 2 | Submit intake: client_name="John Smith", email=john2@test.com | |
| 3 | Admin approves | REQ → APPROVED |
| 4 | Check Client Management | New profile created (john2@test.com) |
| 5 | Two "John Smith" profiles exist | Expected — names aren't unique |

### TC-05: Approve New Customer — Missing Email

| Step | Action | Expected |
|------|--------|----------|
| 1 | This scenario shouldn't occur (email is required on intake) | |
| 2 | If somehow email is empty/null | |
| 3 | Admin approves | REQ → APPROVED (approval succeeds) |
| 4 | Auto-profile | Skipped, `link_status: SKIPPED_NO_EMAIL` |
| 5 | No profile created | Correct — can't match without email |

### TC-06: Profile Creation Fails (Simulated)

| Step | Action | Expected |
|------|--------|----------|
| 1 | Submit intake normally | REQ created |
| 2 | Admin approves (simulate DynamoDB write failure) | REQ → APPROVED (approval succeeds!) |
| 3 | Check REQ record | `client_profile_link_status: FAILED` |
| 4 | Check Client Management | No profile created |
| 5 | Admin can manually create profile | Normal manual flow works |

### TC-07: Cognito Unchanged

| Step | Action | Expected |
|------|--------|----------|
| 1 | Approve new customer intake | Profile auto-created |
| 2 | Check Cognito user pool | No new user |
| 3 | Check profile | `cognito_sub: null`, `portal_enabled: false` |
| 4 | Admin manually onboards later | Cognito user created (separate action) |

### TC-08: Client Management Search

| Step | Action | Expected |
|------|--------|----------|
| 1 | Open Client Management | Full list visible |
| 2 | Type partial name | Filters to matching clients |
| 3 | Type email fragment | Filters by email |
| 4 | Type phone number | Filters by phone |
| 5 | Clear search | Full list restored |
| 6 | Search for non-existent term | Empty result, no error |

### TC-09: VISIT_BOOKING — No Auto-Profile

| Step | Action | Expected |
|------|--------|----------|
| 1 | Existing client submits via portal (VISIT_BOOKING) | REQ created |
| 2 | Admin approves | REQ → APPROVED |
| 3 | Auto-profile check | Skipped (only runs for CUSTOMER_INTAKE) |
| 4 | No new profile created | Correct |

### TC-10: Existing Clients Not Duplicated

| Step | Action | Expected |
|------|--------|----------|
| 1 | Client profile exists (client@test.com) | |
| 2 | Same client submits new intake (same email) | REQ created |
| 3 | Admin approves | REQ → APPROVED |
| 4 | Auto-profile links to existing | No duplicate |
| 5 | Approve again (different request, same email) | Links again, no duplicate |
| 6 | Check Client Management | Still only 1 profile for this email |

---

## 10. Implementation Order

### Step 1: Backend — Client Profile Utility

Create `src/backend/common/client_profile.py`:
- `auto_create_or_link_client_profile()` function
- Email normalization and matching
- Profile creation with auto_created fields
- Request linking (update REQ with linked_client_profile_id)
- Profile updating (append to intake_request_ids)
- Fail-safe error handling

### Step 2: Backend — Review Handler Integration

In `review_handler.py`, after the APPROVED transition for CUSTOMER_INTAKE:
- Call `auto_create_or_link_client_profile()`
- Include link_status in response message if noteworthy
- Wrap in try/except (fail-safe)

### Step 3: Frontend — Client Search

In `AdminDashboard.jsx` `renderClientManagement()`:
- Add search input
- Add client-side filter logic
- Show result count

### Step 4: Frontend — Profile Indicators

In `AdminDashboard.jsx` client cards:
- Show "Auto-created from intake" badge
- Show linked request count
- Show link_status warning if NEEDS_REVIEW or FAILED

### Step 5: Validation

- npm build
- Python compile check
- Manual test all 10 test case groups
- Verify no duplicate profiles
- Verify Cognito unchanged
- Verify VISIT_BOOKING unaffected

---

## 11. Files to Change

| File | Changes |
|------|---------|
| `src/backend/common/client_profile.py` | **NEW** — Auto-creation/linking utility |
| `src/backend/handlers/review_handler.py` | Call auto-profile on CUSTOMER_INTAKE approval |
| `web/src/components/AdminDashboard.jsx` | Client search + profile indicators |

**Total:** 2 modified + 1 new file  
**Estimated effort:** ~120 lines backend, ~50 lines frontend  
**Risk level:** Low (additive, fail-safe, no Cognito changes, no lifecycle changes)

---

## 12. Rollback Strategy

| Action | Effect | Reversible |
|--------|--------|------------|
| Remove auto-profile call from review_handler | Stops auto-creation | ✅ Yes |
| Auto-created profiles remain in DynamoDB | Harmless — they're valid profiles | ✅ No cleanup needed |
| `linked_client_profile_id` on REQ records | Harmless if not displayed | ✅ No cleanup needed |
| Client search UI | Revert JSX changes | ✅ Yes |

**No data cleanup required on rollback.** Auto-created profiles are valid client profiles that Ryan can use, edit, or disable normally.

---

## Note on Future Cleanup Approach

Per AG feedback on Release 2 validation: For future test record cleanup, prefer using the actual admin API (`performAdminAction` or `reviewRequest`) rather than direct DynamoDB updates. This ensures cascade logic, audit trails, transition validation, and side effects are properly exercised.
