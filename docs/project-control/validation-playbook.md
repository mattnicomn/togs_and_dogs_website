# Validation Playbook

## Purpose
Defines how Kiro hands off to AG for production validation, and how results flow back.

## Handoff Protocol

### 1. Kiro Prepares
- Implementation complete, local tests pass
- Provides AG with:
  - Exact test action to perform (e.g., "Approve request X", "Assign worker Y")
  - Expected outcome (e.g., "Email arrives with subject Z")
  - CloudWatch commands (CMD-compatible, copy-paste ready)
  - Error patterns to check for
  - Pass/fail criteria

### 2. AG Executes
- Performs the action in the Admin Dashboard or AWS Console
- Runs CloudWatch commands
- Checks email inboxes
- Reports back with:
  - Pass/fail for each check
  - CloudWatch output (raw JSON)
  - Rendering observations (screenshots if available)
  - Any unexpected behavior

### 3. Kiro Interprets
- Analyzes AG's output
- If passed: updates docs, prepares commit
- If failed: diagnoses root cause, proposes targeted fix
- Does NOT retry the same approach more than twice

## CloudWatch Command Template

**Get timestamp (last N minutes):**
```cmd
powershell -Command "$ts=[int64]((Get-Date).AddMinutes(-N).ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds; Write-Output $ts"
```

**Filter events:**
```cmd
powershell -Command "$ts=[int64]((Get-Date).AddMinutes(-N).ToUniversalTime() - [datetime]'1970-01-01').TotalMilliseconds; aws logs filter-log-events --log-group-name '/aws/lambda/LAMBDA_NAME' --start-time $ts --filter-pattern 'PATTERN' --profile usmissionhero-website-prod --region us-east-1 --no-cli-pager --max-items 10"
```

**Lambda log group names:**
| Lambda | Log Group |
|--------|-----------|
| Intake | `/aws/lambda/togs-and-dogs-prod-intake` |
| Admin | `/aws/lambda/togs-and-dogs-prod-admin` |
| Review | `/aws/lambda/togs-and-dogs-prod-review` |
| Assign | `/aws/lambda/togs-and-dogs-prod-assign` |
| Cancellation | `/aws/lambda/togs-and-dogs-prod-cancellation` |
| Pet | `/aws/lambda/togs-and-dogs-prod-pet` |
| Job | `/aws/lambda/togs-and-dogs-prod-job` |
| Google Auth | `/aws/lambda/togs-and-dogs-prod-google-auth` |

**Common filter patterns:**
- `NOTIFICATION` — all notification activity
- `NOTIFICATION_SUCCESS` — successful sends
- `CRITICAL_FAILURE` — template/service crashes
- `AttributeError` — missing methods/fields
- `NOTIFICATION_MISSING_TEMPLATE` — template returned None

## Notification Routing Reference

| Admin Action | Lambda | Notifications Fired |
|-------------|--------|-------------------|
| Submit intake (public form) | intake | REQUEST_RECEIVED (admin) |
| Approve request | review | CUSTOMER_APPROVED (client) |
| Assign worker (CareCard dropdown) | assign | STAFF_ASSIGNED (staff) + VISIT_SCHEDULED (client) |
| Cancel (Status & Lifecycle) | review | VISIT_CANCELLED (client + staff + admin) — VISIT_BOOKING only |
| Approve cancellation request | cancellation | VISIT_CANCELLED (client + staff + admin) |
| Bulk status change to CANCELLED | admin | VISIT_CANCELLED (client + staff + admin) |

## Validation Pass Criteria

### Notification Emails
- [ ] Email received at expected address
- [ ] Subject line correct
- [ ] Branded HTML renders (header, accent color, CTA button)
- [ ] All data fields populated correctly
- [ ] No literal "None" or "NoneType"
- [ ] No fake defaults ("Team Member") where real data should appear
- [ ] Conditional sections hidden when data is missing
- [ ] CloudWatch shows `NOTIFICATION_SUCCESS` with `provider: postmark`
- [ ] No `CRITICAL_FAILURE` in logs

### Status Transitions
- [ ] Record status updated correctly in DynamoDB
- [ ] Audit log entry appended
- [ ] Cascade to JOB record (if applicable)
- [ ] Google Calendar sync attempted (non-blocking)
- [ ] No unintended side effects on other records
