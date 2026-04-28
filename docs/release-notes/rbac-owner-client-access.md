# Release Notes: RBAC Owner and Client Access Enhancement

## Overview
We have deployed the full Role-Based Access Control (RBAC) hierarchy.

- **Commit Hash**: `a654017`
- **Deployment Date**: 2026-04-28
- **Production Endpoint**: https://toganddogs.usmissionhero.com/

## Modified Access Matrix
- **`owner`**: Complete permissions across administration nodes.
- **`admin`**: Full operational privileges.
- **`staff`**: Constrained field visibility.
- **`client`**: Scope bound to self-data.

## Component Deployment Logs
### Backend
Lambda instances synchronized through localized Terraform states securely.
- `admin_handler`
- `pet_handler`
- `assignment_handler`
- `cancellation_handler`
- `review_handler`

### Frontend
- Bucket Location: `togs-and-dogs-prod-toganddogs-hosting`
- CloudFront ID: `E35L00QPA2IRCY`
- Invalidation ID: `I29MMLLRUSFXORSR2YRJFE49M7` (Status: Completed)

## Cognito Alignment
Execution mappings applied successfully.
- Groups: `Admin`, `Staff`, `owner`, `client`
- User `admin@toganddogs.com` added securely to the `owner` group.

## Production Validation Status
- **Owner (admin@toganddogs.com)**: Validated.
- **Staff / Client Persona Validations**: Pending due to no active user credentials.

### Persona Generation Guidelines
To conduct validation across simulated personas:

```bash
# Staff setup
aws cognito-idp admin-create-user --user-pool-id us-east-1_counlsXGU --username test_staff@toganddogs.com --profile usmissionhero-website-prod
aws cognito-idp admin-add-user-to-group --user-pool-id us-east-1_counlsXGU --username test_staff@toganddogs.com --group-name Staff --profile usmissionhero-website-prod

# Client setup
aws cognito-idp admin-create-user --user-pool-id us-east-1_counlsXGU --username test_client@toganddogs.com --profile usmissionhero-website-prod
aws cognito-idp admin-add-user-to-group --user-pool-id us-east-1_counlsXGU --username test_client@toganddogs.com --group-name client --profile usmissionhero-website-prod
```
