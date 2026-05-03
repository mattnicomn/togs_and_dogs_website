# Milestone 4 E2E Validation Evidence

Generated: 2026-04-19T15:38:48.326294+00:00
Status: SIMULATED (live AWS calls mocked; infrastructure not yet deployed to final DNS)

---

## Scenario A: >24h Approved

### API Calls Tested
| Step | Method | Path                    | Body (key fields)                              |
|------|--------|-------------------------|------------------------------------------------|
| 1    | POST   | /client/cancel          | request_id=TEST-A-123, reason=Going out of town |
| 2    | PUT    | /admin/cancel/decision  | decision=APPROVE, note=Approved per policy      |

### DynamoDB State
| Field                      | Before            | After       |
|----------------------------|-------------------|-------------|
| status                     | APPROVED          | CANCELLED   |
| cancellation_reason        | (none)            | Going out of town |
| cancellation_decision_by   | (none)            | ADMIN       |
| cancellation_decision_note | (none)            | Approved per policy |
| google_event_id            | g-event-a-999     | (cleared by cal delete) |

### Audit Log Entries
```
Entry 1:
  status    : CANCELLATION_REQUESTED
  by        : CLIENT#CLIENT-A
  reason    : Going out of town
  timestamp : <captured at request time>

Entry 2:
  status    : CANCELLED
  by        : ADMIN
  note      : Approved per policy
  timestamp : <captured at decision time>
```

### Google Calendar Result
- delete_event called with event_id: g-event-a-999  [PASS]
- GCal deletion: SIMULATED SUCCESS

### SNS Worker Notification
- Worker: Ryan
- SNS MessageId: sns-msg-a-001
- Result: SIMULATED DELIVERY CONFIRMED

### Validation Result: PASS

---

## Scenario B: <24h Denied

### API Calls Tested
| Step | Method | Path                    | Body (key fields)                              |
|------|--------|-------------------------|------------------------------------------------|
| 1    | POST   | /client/cancel          | request_id=TEST-B-456, reason=Woke up sick      |
| 2    | PUT    | /admin/cancel/decision  | decision=DENY, note=Too close to service        |

### 24-Hour Warning
- start_date: ~5 hours from test execution time
- urgent_warning returned by handler: True
- Expected: True  [PASS]

### DynamoDB State
| Field  | Before   | After                |
|--------|----------|----------------------|
| status | APPROVED | CANCELLATION_DENIED  |

### Audit Log Entry
```
Entry:
  status    : CANCELLATION_DENIED
  by        : ADMIN
  note      : Too close to service per 24h policy
  timestamp : <captured at decision time>
```

### Worker Notification
- SNS publish triggered on denial: False
- Expected: False  [PASS]

### Customer-Facing Status
- new_status in response: CANCELLATION_DENIED
- Expected: CANCELLATION_DENIED  [PASS]

### Validation Result: PASS

---

## Failure Handling

### Case 1: Google Calendar Deletion Fails After Approval
- Simulated: delete_event raises Exception('API Timeout')
- Handler catches exception: YES
- sync_failures DynamoDB attribute written: True
- API response still returns success (booking marked CANCELLED): YES
- Silent failure: NO - logged to CloudWatch + DynamoDB sync_failures list
- Result: PASS

### Case 2: SNS Worker Notification Fails After Approval
- Simulated: sns.publish raises Exception('Connection refused')
- Handler catches exception: YES
- sync_failures DynamoDB attribute written: True
- API response still returns success (booking is CANCELLED regardless): YES
- Silent failure: NO - logged to CloudWatch + DynamoDB sync_failures list
- Rollback risk: None (cancellation stands; Ryan must manually re-notify in this edge case)
- Result: PASS

---

## Gaps and Risks

| Gap | Severity | Notes |
|-----|----------|-------|
| Live AWS deployment not yet accessible (DNS pending) | HIGH | All scenarios SIMULATED. Re-run against live Lambda once app.toganddogs.com resolves. |
| SNS topic has no real phone subscriptions configured | MEDIUM | Topic ARN exists. Add worker phone numbers as subscriptions before go-live. |
| No customer email notification on decision | LOW | Accepted defer to post-M4. Manual workaround: Ryan calls client. |
| CANCELLATION_DENIED status not surfaced in UI booking list | LOW | ClientPortal renders status text; no special styling yet. |

---

## Rollback Notes

- Cancellation is APPROVED atomically in DynamoDB before external calls.
- If GCal or SNS fails, booking stays CANCELLED but sync_failures is populated.
- Recovery: Admin can manually delete GCal event or re-send SNS from AWS Console.
- No automated rollback of CANCELLED status on external failure (by design in v1).

---

## Milestone 4 Completion Sign-Off

MILESTONE 4 STATUS: FEATURE COMPLETE - VALIDATION SIMULATED
Live production re-validation required once app.toganddogs.com DNS resolves.
