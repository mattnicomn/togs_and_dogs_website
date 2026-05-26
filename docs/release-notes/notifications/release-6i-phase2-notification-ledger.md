# Walkthrough: Release 6I Phase 2 - Notification Ledger

I have completed the implementation of Phase 2: Notification Ledger. All core features, safety guarantees, idempotency preservation, webhook integrations, and automated tests are fully complete and validated.

---

## 🛠️ Changes Made

### 1. Backend Orchestration Point
* **[service.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/common/notifications/service.py)**:
  * Added non-blocking DynamoDB helper `_write_ledger_entry` that captures UUIDs, company references (defaulting to `"tog_and_dogs"`), event type, recipient domain/email, provider-specific metadata, and attempt statuses.
  * Added `_resolve_potential_recipients_with_reasons` to analyze the exact path of each potential recipient (suppressed, skipped via preference, active).
  * Injected **pre-dispatch logging** to immediately record skips (`suppressed`, `skipped_disabled`) and duplicate preventions (`skipped_duplicate`).
  * Injected **post-dispatch logging** to record successes (`sent` with `provider_message_id`), dry-run/log-only writes (`skipped_disabled`), and failures (`failed` with error messages).

### 2. Webhook Callback Integration
* **[postmark_webhook_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/postmark_webhook_handler.py)**:
  * Added `_update_ledger_status` which safely queries the partition key `NOTIF#<message_id>` to find matching attempts and updates their status.
  * Integrated status updates on:
    * `Delivery` -> Marks attempt status as `delivered`.
    * `Bounce` (HardBounce) -> Marks attempt status as `bounced` and triggers auto-suppression.
    * `SpamComplaint` -> Marks attempt status as `spam_complaint` and triggers auto-suppression.
    * Unknown/Soft event types -> Safely logs and ignores or records.

### 3. Automated Test Suite
* **[test_r6i_notification_ledger.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/tests/backend/test_r6i_notification_ledger.py)** [NEW]:
  * Written a highly comprehensive integration and unit test suite comprising 8 new backend tests validating:
    1. Successful sends (`sent`).
    2. Globally disabled notifications (`skipped_disabled`).
    3. Duplicate skips (`skipped_duplicate`).
    4. Suppressed skips (`suppressed`).
    5. Provider API failures (`failed`).
    6. Non-blocking DynamoDB failures.
    7. Webhook delivery updates (`delivered`).
    8. Webhook bounce suppression updates (`bounced`).

---

## 🧪 Validation Results

All 149 backend tests pass perfectly, including the 8 new notification ledger tests:
```text
tests\backend\test_r6i_notification_ledger.py ........                   [100%]
============================== 149 passed in 1.04s ==============================
```

---

## 🚀 Deployment Operations & Commands

To preserve the production `POSTMARK_WEBHOOK_SECRET` environment variable and push the newly package backend codes, please run the following commands from your **local shell** (where your AWS credentials and `TF_VAR_postmark_webhook_secret` are loaded):

```powershell
# 1. Navigate to the Terraform production infra directory
cd infra/prod

# 2. Run terraform plan to verify code changes only (no infrastructure destructions)
terraform plan

# 3. Apply the package deployment
terraform apply -auto-approve
```

---

## 🔍 How to Inspect Ledger Records

Ledger items can be easily queried using the AWS CLI or DynamoDB console:

### 1. Inspect Attempt Details by Postmark MessageID
```bash
aws dynamodb query \
  --table-name togs-and-dogs-prod-data \
  --key-condition-expression "PK = :pk" \
  --expression-attribute-values '{":pk": {"S": "NOTIF#<postmark_message_id>"}}'
```

### 2. Inspect Attempts by Request ID (using a Table Scan or secondary indexes for filtering)
```bash
aws dynamodb scan \
  --table-name togs-and-dogs-prod-data \
  --filter-expression "request_id = :req" \
  --expression-attribute-values '{":req": {"S": "<request_id>"}}'
```
