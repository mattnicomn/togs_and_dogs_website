# Release 7T: Matthew Production Monitoring Checklist - Validation Closeout

**Date:** May 29, 2026  
**Release Phase:** 7T  
**Status:** PASSED  
**Implementation Commit:** `480050f`  
**Release Type:** Documentation-only (No code changes, no frontend build, no production deployment, no CloudFront invalidation required)  

---

## 🔍 Validation Status Summary

The Release 7T documentation has been reviewed and validated. The monitoring checklist was created accurately using only verified, locally-sourced resource names. No assumptions or unsupported claims were introduced.

### 1. Document Created

**`docs/operations/matthew-monitoring-checklist.md`** — Matthew's Production Monitoring Checklist

The document provides a complete, copy/paste-ready monitoring routine covering:

* **Purpose & Scope:** Read-only monitoring support while Ryan is unavailable and before broader rollout.
* **Key Reference table:** Exact portal URL, AWS profile, DynamoDB table name, CloudWatch log group pattern, Postmark dashboard URL, admin and support email addresses — all verified from local repo files.
* **Confirmed Lambda Function Names:** All 10 Lambda function names verified directly from `infra/prod/main.tf` (pattern: `togs-and-dogs-prod-*`): `intake`, `admin`, `review`, `assign`, `job`, `cancellation`, `google-auth`, `postmark-webhook`, `device`, `ses-feedback`.
* **Calendar Health Check:** EventBridge rule `togs-and-dogs-prod-calendar-health-check` and its daily schedule verified from Terraform.
* **What Normal Looks Like:** 8-point healthy-state baseline covering CloudWatch, Lambda errors, Postmark delivery, quota, failed notifications, suppression, calendar health, and portal availability.
* **Daily Quick Check (4 checks, ~5–10 min):** CloudWatch Lambda errors, Google Calendar health check log review, Postmark delivery dashboard, portal availability.
* **Weekly Check (5 checks, ~20–30 min):** Postmark monthly quota (DynamoDB `QUOTA#tog_and_dogs`), failed notification record scan, suppression record check, Lambda 7-day error trend, Google Calendar weekly auth confirmation.
* **When to Act table:** 10 signal/threshold/action rows covering alarms, Lambda errors, Postmark bounces, quota thresholds (80%/90%/100%), calendar auth failures, failed notification records, repeated handler errors, and portal 5xx responses.
* **Notification Kill Switches:** All 5 emergency environment variables verified from `infra/prod/locals.tf` — with exact variable names.
* **Do Not Do During Monitoring:** 5 explicit safety guardrails.
* **Related Documents:** 5 cross-links to existing operational docs, all verified to exist in the repo.

### 2. Accuracy Verification

All resource names and values were verified from local repository files before writing — no AWS Console access or runtime commands were used:

| Source File | Data Verified |
|---|---|
| `infra/prod/main.tf` | All Lambda function names, EventBridge rule name, calendar health check schedule |
| `infra/prod/locals.tf` | Notification env var names, admin email, portal URL, AWS profile, Postmark stream |
| `docs/operations/notification-system-runbook.md` | DynamoDB key schema (`QUOTA#`, `NOTIF#`, `SUPPRESSION#`), kill switches, quota warning log pattern |
| `docs/operations/emergency-response-checklist.md` | Cross-link accuracy |
| `docs/operations/admin-quick-reference.md` | Portal URL, business context |
| `docs/operations/ryan-production-trial-handoff.md` | Monitoring scope Matthew was already expected to cover |

> **No CloudWatch alarm names were invented.** The Terraform `observability` module is referenced by ARN only with no alarm names exposed in local files — this section was correctly omitted rather than guessed.

---

## 🛠️ Files Created in Implementation

- **[matthew-monitoring-checklist.md](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/docs/operations/matthew-monitoring-checklist.md)** (New) — 283 lines, documentation-only.

---

## ⚡ Guardrails Checked & Confirmed

- **NO** changes made to frontend components or stylesheet layers.
- **NO** changes made to Python backend handler code or Lambda functions.
- **NO** changes made to test files.
- **NO** changes made to Terraform infrastructure modules.
- **NO** changes made to database schemas or production DynamoDB records.
- **NO** changes made to Google Calendar synchronization handlers or API integration code.
- **NO** changes made to Postmark transactional email delivery logic.
- **NO** changes made to Cognito user pool configurations or Secrets Manager keys.
- **NO** AWS CLI commands were executed against production.
- **NO** production deployments, S3 syncs, or CloudFront invalidations were run.
- The `.kiro/specs/terms-and-privacy-policy/` folder remains gitignored and was not committed.

---

Release 7T is **ACCEPTED** and **CLOSED**.
