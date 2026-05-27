# Release 7C: Push Notification Backend Readiness

**Status:** Planning
**Priority:** High (Mobile App Prerequisite)
**Risk to Production:** Very Low (additive only, no changes to existing workflows)
**Terraform Required:** Yes (new API routes, Lambda env vars)

---

## 1. Objective

Prepare the backend infrastructure for mobile push notifications (Expo Push / FCM / APNs) so that the React Native mobile app can register devices, receive push notifications, and coexist with the existing Postmark email notification system — without disrupting Ryan's active production testing.

---

## 2. What Already Exists

| Component | Status | Notes |
|-----------|--------|-------|
| `notify_event()` orchestration | ✅ Production | Single entry point, provider factory pattern, non-blocking |
| Postmark email delivery | ✅ Production | Live sends, quota tracking, webhook feedback |
| Notification Ledger (DynamoDB) | ✅ Production | `NOTIF#<msg_id>` / `REQUEST#<req_id>` pattern |
| Suppression list | ✅ Production | `SUPPRESSION#<email>` / `METADATA` |
| Monthly quota tracking | ✅ Production | `QUOTA#tog_and_dogs` / `MONTH#YYYY-MM` atomic counters |
| Event-type routing | ✅ Production | `resolve_notification_recipients()` per event type |
| Per-event kill switches | ✅ Production | `NOTIFY_CLIENT_ON_APPROVAL`, etc. |
| Global kill switches | ✅ Production | `NOTIFICATION_DRY_RUN`, `NOTIFICATIONS_ENABLED` |
| Cognito RBAC | ✅ Production | owner > admin > staff > client hierarchy |
| Multi-tenant `company_id` | ✅ Production | `get_current_company_id()` with fallback |
| Single-table DynamoDB | ✅ Production | PK/SK composite keys, shared table |
| API Gateway + Cognito authorizer | ✅ Production | Protected routes use `COGNITO_USER_POOLS` |
| Notification operational runbook | ✅ Production | Kill switches, quota recovery, suppression management |

---

## 3. What Is Missing

| Component | Required For | Effort |
|-----------|-------------|--------|
| Device token storage (DynamoDB schema) | Mobile push registration | Medium |
| Device registration API (`POST /devices`) | Mobile app device onboarding | Medium |
| Device removal API (`DELETE /devices/{deviceId}`) | Token cleanup, logout | Low |
| Push notification provider client (`expo_push_client.py`) | Sending push messages | Medium |
| Push channel integration in `notify_event()` | Dual-dispatch (email + push) | Medium |
| Push-specific config flags | Per-event push enable/disable | Low |
| Push notification ledger entries | Audit trail for push sends | Low |
| Push dry-run / kill switch | Safety controls | Low |
| Device token cleanup on auth events | Stale token prevention | Low |
| API Gateway routes for device management | Terraform | Low |
| Backend tests for device registration + push dispatch | Validation | Medium |

---

## 4. DynamoDB Schema: Device Token Storage

### Design Decision: Same Table, New Entity Type

Use the existing single-table (`togs-and-dogs-prod-data`) with a new entity type. This avoids Terraform changes to create a new table and follows the established pattern.

### Record Structure

```
PK: DEVICE#<device_id>          (UUID generated on registration)
SK: USER#<cognito_sub>          (Links device to authenticated user)

Attributes:
  entity_type:    "PUSH_DEVICE"
  device_id:      "<uuid>"
  cognito_sub:    "<cognito_sub>"
  user_role:      "client" | "staff" | "admin" | "owner"
  profile_id:     "<client_id or staff_id>"
  company_id:     "tog_and_dogs"
  push_token:     "<expo_push_token>"       (e.g., "ExponentPushToken[xxx]")
  platform:       "ios" | "android"
  app_version:    "1.0.0"
  device_name:    "iPhone 15 Pro" (optional, for admin visibility)
  is_active:      true
  created_at:     "2026-05-27T..."
  updated_at:     "2026-05-27T..."
  last_used_at:   "2026-05-27T..."         (Updated on each push send)
```

### Access Patterns

| Pattern | Query |
|---------|-------|
| Get all devices for a user | `PK begins_with DEVICE#` + GSI on `cognito_sub` |
| Get specific device | `PK = DEVICE#<id>`, `SK = USER#<sub>` |
| Find devices by push token | Scan with filter (rare, for dedup) |
| List all devices (admin) | Query by entity_type via GSI or scan |

### GSI Recommendation: UserDeviceIndex

```
GSI PK: cognito_sub
GSI SK: created_at
```

This enables efficient lookup of "all devices for user X" without scanning. However, given the small scale (< 50 users), a filtered query on the main table using `begins_with` on SK may be sufficient initially. **Defer GSI creation until scale requires it.**

### Alternative Considered: Inline on User Profile

Storing device tokens as a list attribute on the CLIENT# or STAFF# profile record was considered but rejected because:
- A user may have multiple devices (phone + tablet)
- Device lifecycle (register/update/expire/remove) is independent of profile lifecycle
- Separate records enable cleaner audit and TTL-based cleanup
- Avoids write contention on frequently-read profile records

---

## 5. Push Notification Provider: Expo Push

### Recommendation: Use Expo Push Notifications Service

| Factor | Decision |
|--------|----------|
| Provider | Expo Push Notifications (wraps FCM + APNs) |
| Why | React Native + Expo stack; single API for both iOS and Android; no separate Firebase/APNs config needed initially |
| Token format | `ExponentPushToken[xxxxxxxxxxxxxxxxxxxxxx]` |
| API endpoint | `https://exp.host/--/api/v2/push/send` |
| Auth | No server-side auth needed (Expo Push is free and open) |
| Rate limits | 600 notifications/second (more than sufficient) |
| Receipts | Expo provides receipt IDs for delivery confirmation |

### Why Not Direct FCM/APNs?

- Expo Push abstracts both platforms behind one API
- No need to manage FCM server keys or APNs certificates initially
- If we outgrow Expo Push later, migration to direct FCM/APNs is straightforward
- Expo Push is free with no monthly limits

---

## 6. Device Registration API Flow

### `POST /client/devices` — Register or Update Device

**Auth:** Cognito (any authenticated role)
**Handler:** New `device_handler.py`

```json
// Request
{
  "push_token": "ExponentPushToken[abc123...]",
  "platform": "ios",
  "app_version": "1.0.0",
  "device_name": "iPhone 15 Pro"
}

// Response (201 Created or 200 Updated)
{
  "device_id": "uuid-here",
  "status": "registered"
}
```

**Logic:**
1. Extract `cognito_sub` from JWT claims
2. Resolve `user_role` and `profile_id` (client_id or staff_id)
3. Check if a device with this `push_token` already exists for this user
   - If yes: update `updated_at`, `app_version`, `platform`, `is_active = true`
   - If no: create new DEVICE# record
4. Deactivate any other devices with the same `push_token` but different user (token reassignment)
5. Return device_id

### `DELETE /client/devices/{deviceId}` — Remove Device

**Auth:** Cognito (owner of device OR admin)

```json
// Response (200)
{
  "status": "removed"
}
```

**Logic:**
1. Verify caller owns the device (`cognito_sub` matches SK) OR caller is admin/owner
2. Set `is_active = false` (soft delete) or hard delete the record
3. Return confirmation

### `GET /client/devices` — List My Devices (optional, Phase 2)

**Auth:** Cognito (any authenticated role)

Returns all active devices for the calling user. Useful for "manage notifications" screen.

---

## 7. Identity Linking

### How Device Tokens Link to Users

```
cognito_sub  ←→  DEVICE# record (SK = USER#<cognito_sub>)
     ↓
  profile_id  (client_id or staff_id, resolved at registration time)
     ↓
  user_role   (client, staff, admin, owner)
     ↓
  company_id  (tenant isolation)
```

### Resolution at Registration Time

When a device registers:
1. `cognito_sub` comes from the JWT (guaranteed by Cognito authorizer)
2. `user_role` = `get_effective_role(event)`
3. `profile_id` = resolved via existing patterns:
   - For clients: `resolve_client_identity(event)` → `client_id`
   - For staff/admin: query `COMPANY#tog_and_dogs` + `STAFF#*` where `cognito_sub` matches
4. `company_id` = `get_current_company_id(event)`

### At Notification Dispatch Time

When `notify_event()` needs to send push:
1. Resolve recipient identity (email → profile → cognito_sub)
2. Query DEVICE# records for that `cognito_sub` where `is_active = true`
3. Send to all active device tokens for that user

---

## 8. Integration with `notify_event()` Orchestration

### Dual-Dispatch Architecture

```
notify_event("CUSTOMER_APPROVED", record)
    │
    ├── Email Channel (existing)
    │   └── PostmarkClient.send_email() → Ledger entry
    │
    └── Push Channel (new)
        └── ExpoPushClient.send_push() → Ledger entry
```

### Implementation Approach

**Option A (Recommended): Sequential dispatch within `notify_event()`**

After the existing email dispatch block (step 6 in current code), add a push dispatch block:

```python
# 6.5 Push Notification Dispatch (Release 7C)
if push_config.PUSH_ENABLED and not push_config.PUSH_DRY_RUN:
    push_recipients = resolve_push_recipients(event_type, record, config)
    if push_recipients:
        push_result = push_client.send_push(push_recipients, title, body, data)
        _write_ledger_entry(..., provider="expo_push", ...)
```

**Why not a separate Lambda or async dispatch?**
- The existing `notify_event()` is already non-blocking (failures don't block workflows)
- Adding push dispatch inline keeps the code simple and auditable
- Expo Push API responds in < 100ms for small batches
- A separate Lambda adds complexity without meaningful benefit at this scale

### Push Recipient Resolution

New function: `resolve_push_recipients(event_type, record, config)`

Returns a list of `{ cognito_sub, push_tokens: [...], role }` for the event type, using the same routing logic as email but resolving to device tokens instead of email addresses.

---

## 9. Events That Support Push (Phase 1)

### Priority 1: Admin/Owner Notifications (Ryan's daily use)

| Event | Push Recipient | Email Too? | Priority |
|-------|---------------|------------|----------|
| `REQUEST_RECEIVED` | Admin/Owner devices | ✅ | High |
| `VISIT_CANCELLED` | Admin + Staff + Client devices | ✅ | High |

### Priority 2: Staff Notifications

| Event | Push Recipient | Email Too? | Priority |
|-------|---------------|------------|----------|
| `STAFF_ASSIGNED` | Assigned staff devices | ✅ | High |

### Priority 3: Client Notifications

| Event | Push Recipient | Email Too? | Priority |
|-------|---------------|------------|----------|
| `CUSTOMER_APPROVED` | Client devices | ✅ | Medium |
| `VISIT_SCHEDULED` | Client devices | ✅ | Medium |

### Deferred (Phase 2+)

| Event | Notes |
|-------|-------|
| `VISIT_REMINDER` (1 day before) | New event type, push-only |
| `VISIT_COMPLETED` | New event type, push-only |
| `STAFF_SCHEDULE_CHANGE` | New event type |

---

## 10. Configuration & Kill Switches

### New Environment Variables

```python
# Push Notification Controls
PUSH_ENABLED = os.environ.get('PUSH_ENABLED', 'false').lower() == 'true'
PUSH_DRY_RUN = os.environ.get('PUSH_DRY_RUN', 'true').lower() == 'true'
PUSH_PROVIDER = os.environ.get('PUSH_PROVIDER', 'expo')  # expo | log_only

# Per-event push toggles (mirror email pattern)
PUSH_ADMIN_ON_REQUEST_RECEIVED = os.environ.get('PUSH_ADMIN_ON_REQUEST_RECEIVED', 'true').lower() == 'true'
PUSH_CLIENT_ON_APPROVAL = os.environ.get('PUSH_CLIENT_ON_APPROVAL', 'true').lower() == 'true'
PUSH_CLIENT_ON_SCHEDULED = os.environ.get('PUSH_CLIENT_ON_SCHEDULED', 'true').lower() == 'true'
PUSH_STAFF_ON_ASSIGNMENT = os.environ.get('PUSH_STAFF_ON_ASSIGNMENT', 'true').lower() == 'true'
PUSH_CLIENT_ON_CANCELLED = os.environ.get('PUSH_CLIENT_ON_CANCELLED', 'true').lower() == 'true'
PUSH_STAFF_ON_CANCELLED = os.environ.get('PUSH_STAFF_ON_CANCELLED', 'true').lower() == 'true'
PUSH_ADMIN_ON_CANCELLED = os.environ.get('PUSH_ADMIN_ON_CANCELLED', 'true').lower() == 'true'
```

### Kill Switch Behavior

| Switch | Effect |
|--------|--------|
| `PUSH_ENABLED=false` | All push dispatch skipped, ledger writes `skipped_disabled` |
| `PUSH_DRY_RUN=true` | Push logic runs but no API call made, ledger writes `dry_run` |
| `PUSH_PROVIDER=log_only` | Logs push payload without sending |
| Individual event flags | Disable push for specific event types |

### Safe Defaults for Initial Deploy

```
PUSH_ENABLED = false          ← Off until mobile app is ready
PUSH_DRY_RUN = true           ← Double safety
PUSH_PROVIDER = expo
```

Push will be enabled only after the mobile app registers its first device token.

---

## 11. Ledger & Logging Behavior

### Push Notification Ledger Entries

Same pattern as email, new provider value:

```
PK: NOTIF#<push_receipt_id_or_uuid>
SK: REQUEST#<request_id>

Attributes:
  entity_type:        "NOTIFICATION_LEDGER"
  event_type:         "CUSTOMER_APPROVED"
  recipient_email:    "client@example.com"     (for cross-reference)
  recipient_sub:      "<cognito_sub>"          (NEW: push-specific)
  device_count:       2                        (NEW: how many devices received)
  status:             "sent" | "failed" | "skipped_disabled" | "dry_run"
  provider:           "expo_push"
  provider_message_id: "<expo_receipt_id>"
  company_id:         "tog_and_dogs"
  created_at:         "2026-05-27T..."
```

### CloudWatch Log Patterns

```
PUSH_NOTIFICATION_SENT: event=STAFF_ASSIGNED, recipient_sub=xxx, devices=2
PUSH_NOTIFICATION_FAILED: event=REQUEST_RECEIVED, error=DeviceNotRegistered
PUSH_NOTIFICATION_DRY_RUN: event=CUSTOMER_APPROVED, would_send_to=2_devices
PUSH_NOTIFICATION_SKIPPED: event=VISIT_CANCELLED, reason=no_active_devices
```

---

## 12. Security Controls

### Device Registration Security

| Control | Implementation |
|---------|---------------|
| Only authenticated users can register | Cognito authorizer on `/client/devices` |
| Users can only register their own devices | `cognito_sub` from JWT, not from request body |
| Users can only remove their own devices | Verify SK matches caller's `cognito_sub` |
| Admin can remove any device | Role check: owner/admin bypass ownership check |
| Token reassignment protection | If token already registered to another user, deactivate old record |
| Rate limiting | API Gateway throttling (existing) |
| No token exposure in responses | Device list returns device_id + metadata, never raw push_token |

### Push Payload Security

| Control | Implementation |
|---------|---------------|
| No sensitive data in push body | Push contains title + summary only, not full booking details |
| Deep link to authenticated screen | Push `data` field contains `{ screen, recordId }` — app must authenticate before showing |
| No PII in push notification text | Use "You have a new booking" not "John Doe booked for Buddy" |

---

## 13. Tests Required Before Implementation

### Unit Tests (`tests/backend/test_r7c_device_registration.py`)

| Test | Description |
|------|-------------|
| `test_register_device_success` | Valid token + auth → 201 with device_id |
| `test_register_device_unauthenticated` | No JWT → 401 |
| `test_register_device_duplicate_token_same_user` | Updates existing record |
| `test_register_device_duplicate_token_different_user` | Deactivates old, creates new |
| `test_remove_device_own` | Owner of device can remove |
| `test_remove_device_other_user_denied` | Non-owner non-admin → 403 |
| `test_remove_device_admin_allowed` | Admin can remove any device |
| `test_register_device_invalid_token_format` | Rejects non-Expo tokens |

### Unit Tests (`tests/backend/test_r7c_push_dispatch.py`)

| Test | Description |
|------|-------------|
| `test_push_dispatch_enabled` | Push sends when enabled + devices exist |
| `test_push_dispatch_disabled` | Push skipped when `PUSH_ENABLED=false` |
| `test_push_dispatch_dry_run` | Push logged but not sent when dry run |
| `test_push_dispatch_no_devices` | Gracefully skips when user has no devices |
| `test_push_dispatch_does_not_break_email` | Email still sends regardless of push result |
| `test_push_dispatch_failure_non_blocking` | Push API error doesn't block workflow |
| `test_push_ledger_entry_written` | Ledger records push send/skip/fail |
| `test_push_recipient_resolution` | Correct devices resolved per event type |

---

## 14. Terraform Requirements

### New Resources Required

| Resource | Purpose | Risk |
|----------|---------|------|
| API Gateway route: `POST /client/devices` | Device registration | None (additive) |
| API Gateway route: `DELETE /client/devices/{deviceId}` | Device removal | None (additive) |
| API Gateway route: `GET /client/devices` | List devices (optional) | None (additive) |
| Lambda function: `device_handler` | Device management | None (new function) |
| Lambda env vars: push config | Push configuration | None (additive to existing Lambdas) |
| CORS for new routes | Browser/mobile access | None (follows existing pattern) |

### No New DynamoDB Table Required

Device tokens use the existing single table. No GSI needed at current scale.

### No New Secrets Required

Expo Push API does not require server-side authentication tokens.

---

## 15. Implementation Phases

### Phase 1: Device Token Storage & Registration API (~1 day)

- Create `src/backend/handlers/device_handler.py`
- Implement `POST /client/devices` (register/update)
- Implement `DELETE /client/devices/{deviceId}` (remove)
- Add Terraform route + Lambda + permissions
- Add `PUSH_ENABLED=false` and `PUSH_DRY_RUN=true` to `locals.tf`
- Write device registration tests
- **Zero risk to production** — new handler, new routes, push disabled by default

### Phase 2: Expo Push Client & Dispatch Integration (~1 day)

- Create `src/backend/common/notifications/expo_push_client.py`
- Add `resolve_push_recipients()` to resolver
- Integrate push dispatch into `notify_event()` (after email block)
- Add push ledger entries
- Write push dispatch tests
- **Zero risk to production** — `PUSH_ENABLED=false` means no push code executes

### Phase 3: Configuration & Operational Docs (~0.5 day)

- Add all push env vars to `locals.tf` (disabled defaults)
- Update notification system runbook with push kill switches
- Update data model docs with DEVICE# schema
- Document push notification troubleshooting

### Phase 4: Smoke Test with Real Device (~0.5 day, after mobile Phase 1)

- Enable `PUSH_ENABLED=true` + `PUSH_DRY_RUN=false` in a test config
- Register a real Expo push token from a development build
- Trigger a `REQUEST_RECEIVED` event and verify push delivery
- Verify email still sends alongside push
- Verify ledger records both channels

---

## 16. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Push code breaks existing email flow | Very Low | High | Push dispatch is in a separate try/except block; `PUSH_ENABLED=false` by default |
| Stale device tokens accumulate | Low | Low | Expo Push returns `DeviceNotRegistered` errors; auto-deactivate on receipt |
| Push notification spam | Very Low | Medium | Per-event flags + global kill switch + dry-run mode |
| Terraform apply disrupts production | Low | Medium | Only additive changes (new routes, new Lambda); no modifications to existing resources |
| Device registration endpoint abused | Very Low | Low | Cognito auth required; rate limiting via API Gateway |
| Ryan's production testing disrupted | Very Low | None | Push is completely disabled until mobile app exists |

---

## 17. Non-Goals (Explicitly Deferred)

| Item | Reason |
|------|--------|
| Push notification preferences UI | Mobile app feature (Phase 2+) |
| Per-device notification type preferences | Complexity; start with all-or-nothing |
| Badge count management | iOS-specific, handle in mobile app |
| Rich push (images, actions) | Start with basic text push |
| Push analytics dashboard | Use CloudWatch logs initially |
| Direct FCM/APNs integration | Expo Push abstracts this; revisit if needed |
| Offline push queuing | Expo handles retry/queuing |

---

## 18. File Changes Summary

### New Files

| File | Purpose |
|------|---------|
| `src/backend/handlers/device_handler.py` | Device registration/removal API |
| `src/backend/common/notifications/expo_push_client.py` | Expo Push API client |
| `src/backend/common/notifications/push_resolver.py` | Resolve cognito_sub → device tokens |
| `tests/backend/test_r7c_device_registration.py` | Device API tests |
| `tests/backend/test_r7c_push_dispatch.py` | Push dispatch tests |

### Modified Files

| File | Change |
|------|--------|
| `src/backend/common/notifications/config.py` | Add push config flags |
| `src/backend/common/notifications/service.py` | Add push dispatch block after email |
| `infra/prod/main.tf` | Add device_handler Lambda + permissions |
| `infra/prod/locals.tf` | Add push env vars (disabled defaults) |
| `modules/api/main.tf` | Add `/client/devices` routes |
| `modules/api/variables.tf` | Add `device_handler_invoke_arn` variable |
| `docs/datamodel.md` | Add DEVICE# schema |
| `docs/operations/notification-system-runbook.md` | Add push kill switches |

---

## 19. AG Implementation Prompt (Phase 1)

```
AG — implement Release 7C Phase 1: Device Token Storage & Registration API.

1. Create src/backend/handlers/device_handler.py:
   - POST handler: register/update device token
   - DELETE handler: remove device (ownership check)
   - Extract cognito_sub from JWT claims
   - Resolve user_role and profile_id
   - Dedup: if push_token exists for same user, update; if different user, deactivate old
   - DynamoDB pattern: PK=DEVICE#<uuid>, SK=USER#<cognito_sub>

2. Add Terraform resources:
   - Lambda function: device_handler (same pattern as pet_handler)
   - API Gateway routes: POST /client/devices, DELETE /client/devices/{deviceId}
   - Cognito authorizer on both routes
   - CORS OPTIONS for new routes
   - Lambda permission for API Gateway

3. Add to infra/prod/locals.tf notification_env_vars:
   - PUSH_ENABLED = "false"
   - PUSH_DRY_RUN = "true"
   - PUSH_PROVIDER = "expo"

4. Write tests: tests/backend/test_r7c_device_registration.py
   - test_register_device_success
   - test_register_device_unauthenticated
   - test_register_device_duplicate_token_same_user
   - test_register_device_duplicate_token_different_user
   - test_remove_device_own
   - test_remove_device_other_user_denied
   - test_remove_device_admin_allowed

5. Run: python -m pytest tests/backend/test_r7c_device_registration.py -v
6. Run: terraform fmt && terraform validate (in infra/prod/)
7. Do NOT set PUSH_ENABLED=true. Do NOT deploy.

Return: files changed, test results, terraform validate output.
```

---

## 20. Commit Command

After planning document is approved:

```bash
git add docs/planning/release-7c-push-notification-backend-readiness-plan.md
git commit -m "docs: Release 7C push notification backend readiness plan"
```
