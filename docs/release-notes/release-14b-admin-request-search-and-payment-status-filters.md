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
  ✓ built in 418ms
  ```

## Browser/Manual Smoke Test Deferral

Manual browser/smoke tests have been **deferred to post-deployment / manual smoke testing**.
* **Reason**: Strict credential-safety guardrails prohibit the extraction, search, or transfer of Cognito credentials, passwords, session tokens, or browser cookies from the production portal (`toganddogs.usmissionhero.com`) to the localhost dev server (`localhost:5173`). Without active credentials or local mock tokens, the local portal remains at the login challenge.
* **Testing Scope to Perform Manually Post-Deploy**:
  1. Load the updated Admin Dashboard.
  2. Verify existing sidebar filters (such as Pending Review) compose correctly with the search/filter controls.
  3. Verify searching for `TestPet_ScenarioB` returns the paid request.
  4. Verify searching for ID `c1b11afe-3cda-45c1-9ada-af91b14234ad` finds the paid request.
  5. Select payment filters (Paid, Payment Link Sent, Unpaid / Not Set) and verify the list matches correctly.
  6. Click "Reset Filters" / "clear filters" to ensure the main record view is restored.
  7. Verify expanding rows and opening CareCards function normally.

## Deployment Recommendation

Production deployment is recommended as the frontend code is fully integrated, compile-verified, and meets all release requirements. No backend modifications are required.
