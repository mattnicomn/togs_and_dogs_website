# Planning Guide: AWS SES Deprecation

As part of Release 6J, the AWS SES client (`SESClient`) has been officially **deprecated** and is preserved purely as a legacy fallback. All active transactional email delivery is routed through Postmark.

---

## 📅 Deprecation Timeline

* **Release 6A-6I:** Postmark established as the live production provider. SES sandbox restricted.
* **Release 6J:** `SESClient` officially marked as deprecated in comments, logs, and runtime warnings.
* **Future Release (Target: Release 7+):** Complete code cleanup, removal of `ses_client.py`, and stripping of SES-specific Terraform IAM permissions.

---

## 🛠️ Code Changes & Warnings

1. **`ses_client.py`:** Docstring updated to clearly show deprecation. Instantiation of `SESClient` triggers:
   `DEPRECATION_WARNING: SESClient is deprecated and should only be used as a legacy fallback. Please migrate to PostmarkClient.`
2. **`config.py`:** The environment variable `SES_SANDBOX_ALLOWED_RECIPIENTS` is retained only for fallback compatibility.

---

## 🗑️ Cleanup Instructions for Future Developers

When the time arrives to completely remove SES, follow this roadmap:

### 1. Codebase Cleanup
* Delete the file `src/backend/common/notifications/ses_client.py`.
* In `src/backend/common/notifications/service.py`:
  * Remove `from .ses_client import SESClient`.
  * Simplify `get_notification_client(config)` to only return `PostmarkClient`. Remove the SES routing branch.
* In `src/backend/common/notifications/config.py`:
  * Delete `SES_PRODUCTION_MODE` property.
  * Delete `_sandbox_allowed` and `SES_SANDBOX_ALLOWED_RECIPIENTS` properties.

### 2. Infrastructure (Terraform) Cleanup
* In `modules/iam/main.tf` (or related Lambda roles):
  * Remove the IAM policy statement allowing `ses:SendEmail` and `ses:SendRawEmail` actions.
* In `infra/prod/locals.tf`:
  * Strip SES-specific configuration values from `notification_env_vars`.
* Run `terraform plan` and `terraform apply` locally to apply the stripped policies.
