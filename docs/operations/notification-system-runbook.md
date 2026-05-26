# Operational Runbook: Postmark Notification System

This document outlines standard operating and troubleshooting procedures for the Tog & Dogs transactional email notification system.

---

## 🔍 Operational Inspection

### 1. Check Monthly Send Count & Quota Usage
All monthly attempts are tracked in DynamoDB under the key:
* **PK:** `QUOTA#tog_and_dogs`
* **SK:** `MONTH#YYYY-MM` (e.g. `MONTH#2026-05`)

To fetch the current month's send count:
```bash
aws dynamodb get-item \
  --table-name togs-and-dogs-prod-data \
  --key '{"PK": {"S": "QUOTA#tog_and_dogs"}, "SK": {"S": "MONTH#2026-05"}}'
```

### 2. Inspect Quota Warnings in CloudWatch Logs
Threshold crossings (at 80%, 90%, and 100%) will output standard queryable logs:
`NOTIFICATION_QUOTA_WARNING: Month YYYY-MM quota usage is at X%`

Search CloudWatch logs for the term:
`NOTIFICATION_QUOTA_WARNING`

### 3. Query the Notification Attempt Ledger
Ledger attempts are written to DynamoDB:
* **PK:** `NOTIF#<message_id_or_uuid>`
* **SK:** `REQUEST#<request_id_or_UNKNOWN>`

To query standard status (`sent`, `delivered`, `bounced`, `spam_complaint`, `suppressed`, `skipped_disabled`, `skipped_quota_exceeded`, `failed`):
```bash
aws dynamodb query \
  --table-name togs-and-dogs-prod-data \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk": {"S": "NOTIF#<message_id>"}}'
```

---

## 🛠️ Common Operations & Procedures

### 1. Reading & Managing the Suppression List
When hard bounces or spam complaints occur, the webhook automatically records the email in the suppression list:
* **PK:** `SUPPRESSION#<recipient_email>`
* **SK:** `METADATA`

#### Check if an Email is Suppressed
```bash
aws dynamodb get-item \
  --table-name togs-and-dogs-prod-data \
  --key '{"PK": {"S": "SUPPRESSION#test@example.com"}, "SK": {"S": "METADATA"}}'
```

#### Manually Remove an Email from the Suppression List (Restore Client)
If a client has resolved their email delivery issues and requests to receive notifications again, remove their suppression record:
```bash
aws dynamodb delete-item \
  --table-name togs-and-dogs-prod-data \
  --key '{"PK": {"S": "SUPPRESSION#test@example.com"}, "SK": {"S": "METADATA"}}'
```

### 2. Quota Overage & Hard Stop Recovery
If the hard stop is active and `POSTMARK_MONTHLY_LIMIT` is reached, all sends will be blocked and recorded as `skipped_quota_exceeded`.

#### Actionable Steps:
1. **Temporarily increase the limit:**
   Set the env var `POSTMARK_MONTHLY_LIMIT` to a higher value (e.g. `200`) and deploy via Terraform.
2. **Disable the hard stop:**
   Set `POSTMARK_QUOTA_HARD_STOP=false` in the env vars and deploy. Purely informational threshold warning logs will still be emitted, but sending will **never** be blocked.
3. **Upgrade Postmark Plan:**
   Upgrade your Postmark transactional stream to a paid plan.

---

## 🚨 Rollback & Emergency Kill Switches

| Emergency Switch | Command / Action | Result |
|---|---|---|
| **Stop all sends immediately** | Set `NOTIFICATION_DRY_RUN=true` in production environment variables. | Simulates success, records entries, but completely bypasses the Postmark API. |
| **Kill all notification processing** | Set `NOTIFICATIONS_ENABLED=false` in environment variables. | Skips all resolution, sending, and logging. |
| **Disable a specific event type** | Set `NOTIFY_CLIENT_ON_APPROVAL=false` (or other config flags) to `false`. | Bypasses that specific event type. |
| **Redirect all sends to test email** | Set `NOTIFICATION_TEST_RECIPIENT_OVERRIDE=admin@example.com`. | All emails route only to the override address for sandbox validation. |
| **Switch back to Log-Only** | Set `NOTIFICATION_PROVIDER=log_only`. | Completely blocks external API dispatching. |
