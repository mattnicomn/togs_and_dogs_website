# Release Notes — Release 14B — Admin Request Search and Payment Status Filters

## Implementation Summary

This release introduces comprehensive search capabilities and payment status filtering to the main Admin Request List. This allows administrators to quickly locate requests and view their payment statuses at a glance without having to drill down into each individual record.

All changes are frontend-only, with zero changes made to the backend APIs, DynamoDB schemas, or Cognito credentials/roles.

## Search Fields

A case-insensitive search input has been integrated into the controls bar. Search queries match the following fields (where available on the record):
* **Client Name** (`item.client_name`)
* **Pet Name(s)** (`item.pet_names` / `item.pet_name`)
* **Client Email** (`item.client_email`)
* **Request ID** (matches both `item.request_id` and raw suffix of `item.PK` after stripping the `REQ#` prefix)
* **Service Type** (matches raw code like `WALK_30MIN` and friendly label like `30-Minute Walk`)
* **Status** (matches raw status code like `PENDING_REVIEW` and friendly status label like `New Request`)
* **Payment Status** (matches status code like `paid`, `payment_link_sent`, `unpaid`, `waived`, `refunded`)

## Payment Filter Options

A dropdown menu allows filtering records based on their payment state:
* **All Payment Statuses**: Displays all records.
* **Unpaid / Not Set**: Displays records with payment status set to `unpaid` or where the status field is missing (`null`/`undefined`).
* **Payment Link Sent**: Displays records where the payment link has been sent (`payment_link_sent`).
* **Paid**: Displays paid records (`paid`).
* **Waived**: Displays waived records (`waived`).
* **Refunded**: Displays refunded records (`refunded`).

## Payment Chip Behavior

Row status cells render a standardized status chip representing the payment state:
* **Paid**: Green chip (Style: background `#ecfdf5`, text `#065f46`, border `#a7f3d0`).
* **Payment Link Sent**: Blue chip (Style: background `#eff6ff`, text `#1e40af`, border `#bfdbfe`).
* **Waived**: Amber/Orange chip (Style: background `#fffbeb`, text `#b45309`, border `#fde68a`).
* **Refunded**: Purple chip (Style: background `#faf5ff`, text `#6b21a8`, border `#e9d5ff`).
* **Unpaid**: Grey chip (Style: background `#f3f4f6`, text `#374151`, border `#e5e7eb`).
* Missing or null payment status fields default to **Unpaid** to prevent misleadingly displaying requests as paid.

## Empty State Behavior

When filtered results return empty:
* A contextual empty state message is shown: `"No requests match the current filters."`
* A clear link is provided: `"clear filters"`, which resets both the search query input and the payment status dropdown to their default states, restoring the unfiltered record view.

## Build Results

* The frontend production build (`npm run build` executed inside the `web` folder) compiles successfully using Vite:
  ```bash
  vite v8.0.8 building client environment for production...
  transforming...✓ 96 modules transformed.
  rendering chunks...
  computing gzip size...
  dist/index.html                         1.47 kB │ gzip:   0.68 kB
  dist/assets/usmh-logo-CrRnxp7-.png  2,583.40 kB
  dist/assets/index-Dhj_nyZO.css         59.93 kB │ gzip:  11.05 kB
  dist/assets/index-DdwsoXKE.js         892.40 kB │ gzip: 263.80 kB
  ✓ built in 325ms
  ```

## Frontend Deployment Details

* **Deployment Method**: S3 sync deployment
* **Target S3 Bucket**: `s3://togs-and-dogs-prod-toganddogs-hosting`
* **AWS CLI Sync Results**: Successfully synced the 4 final assets to S3 and deleted the old asset bundles using AWS profile `usmissionhero-website-prod`.
* **CloudFront Invalidation ID**: `I4IMEGUY1YB7KU5K3B1Y00S0U6` for distribution `E35L00QPA2IRCY`.

## Production Smoke Test Validation Results

A browser subagent completed a comprehensive verification directly on the live production URL `https://toganddogs.usmissionhero.com/admin` using the active authenticated admin portal session. All test targets passed:
1. **Admin Dashboard Loads**: Verified page reload and initial list population with no errors.
2. **List Controls Visibility**: Verified search input and payment status select dropdown are visible at the top of the request list.
3. **Sidebar Filter Composition**: Switched to various sidebar filters (e.g. *Scheduled with Staff*, *All Active*) and verified that they continue to compose correctly.
4. **Search Match Verification**:
   * Searching by pet name `'TestPet_ScenarioB'` correctly returned the paid test request.
   * Searching by request ID `'c1b11afe-3cda-45c1-9ada-af91b14234ad'` correctly returned the matching paid test request.
5. **Payment Filter Mappings**:
   * Filter **Paid** successfully showed paid requests (e.g., `TestPet_ScenarioB`).
   * Filter **Payment Link Sent** successfully showed payment-link-sent requests (e.g., `TestPet_ScenarioA`).
   * Filter **Unpaid / not set** successfully showed unpaid requests.
6. **Empty State & Clear Filters**:
   * Gibberish search text (`xyz123abc`) triggered the filter empty state with the message *"No requests match the current filters. Try adjusting your search query or payment status filter, or clear filters to see all requests."*
   * Clicking the **clear filters** action successfully reset the search input and dropdown selection, restoring all records.
7. **CareCard Row Expansion**: Clicking the row expand caret (`▶`) successfully opened and rendered the CareCard details inline.

## Final Git Status

The repository is clean and up to date with the remote tracking branch `origin/main`.

## Guardrails & Verification Confirmation

* No backend code, schemas, or API changes were made.
* No Terraform resource plans, configurations, or applies occurred.
* No Stripe Dashboard settings, API keys, or checkout sessions were modified or used.
* No Postmark email transmissions, SMS messages, DynamoDB writes, Cognito user pools/identities, mobile app/EAS packages, or second tenant configurations were changed.
