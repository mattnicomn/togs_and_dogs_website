# Release Notes: RBAC Owner and Client Access Enhancement

## Release Status
**DEPLOYED / PARTIALLY VALIDATED**

## Overview
We have deployed the full Role-Based Access Control (RBAC) hierarchy.

## Final Status Section
Confirmed:
- Application logic commit: `6370944`
- Documentation closeout commit: `41d0225`
- CloudFront invalidation ID: `I29MMLLRUSFXORSR2YRJFE49M7`
- CloudFront invalidation status: Completed
- Production URL: https://toganddogs.usmissionhero.com/
- Cognito groups confirmed: Admin, Staff, owner, client
- admin@toganddogs.com group membership confirmed: Admin, owner
- Protected path validation: PASS

Pending:
- Owner live login validation
- Staff live role validation
- Client live role validation
- No-group user validation
- API-level note redaction validation using real tokens
- Real client “My Bookings” access validation
- Real staff Staff Portal validation without internal notes

Known limitation:
- owner and client groups were created manually in Cognito and are not yet Terraform-managed unless Terraform was explicitly updated.
- Future hardening should add Cognito group management to Terraform or a documented provisioning script.
