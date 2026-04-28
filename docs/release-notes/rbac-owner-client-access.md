# Release Notes: RBAC Owner and Client Access Enhancement

## Overview
We have deployed the full Role-Based Access Control (RBAC) hierarchy.

- **Commit Hash**: `6370944`
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
- Invalidation Path: `/*`

## Cognito Alignment
Execution mappings applied against:
`owner` group populated successfully.
