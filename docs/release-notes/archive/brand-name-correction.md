# Release Notes: Brand Name Correction

**Date:** 2026-04-26  
**Status:** Deployed to Production  
**Production URL:** [https://toganddogs.usmissionhero.com/](https://toganddogs.usmissionhero.com/)

## Summary
Corrected the company branding across the production platform to align with the primary business identity "Tog and Dogs".

### Issue
The production website incorrectly displayed the pluralized company name "Togs and Dogs" in several locations, including the browser tab title, logo headers, and welcome text.

### Correction
Updated all user-facing visible text to use the singular form:
- **Normal Text:** "Tog and Dogs"
- **Stylized Logo/Headers:** "Tog&Dogs"

### Scope & Constraints
- **Display Branding Only:** This fix was strictly limited to visible text and UI elements.
- **Infrastructure Integrity:** No changes were made to technical identifiers, including:
  - S3 bucket names
  - CloudFront distribution configurations
  - DynamoDB table names
  - API routes and backend logic
  - Authentication (Cognito) resources
  - Domain names and Route 53 records
  - Terraform resource identifiers
  - Repository and folder names

## Deployment Details
- **Commit Hash:** `0aaf8ed`
- **Build Tool:** Vite (Production Build)
- **Deployment Target:** S3 Bucket `togs-and-dogs-prod-toganddogs-hosting`
- **CloudFront Invalidation:**
  - **Distribution ID:** `E35L00QPA2IRCY`
  - **Invalidation ID:** `I50F8GPMUWOWLGXNTA8GO2J3OT`
  - **Status:** Completed
