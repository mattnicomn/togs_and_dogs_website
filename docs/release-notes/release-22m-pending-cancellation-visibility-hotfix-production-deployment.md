# Release Notes — Release 22M: Pending Cancellation Visibility Hotfix Production Deployment

**Release Date:** 2026-07-10  
**Type:** Frontend Production Hotfix (Deploy-Only)  
**Status:** ✅ **PASS** — Deployed & Validated in Production

---

## 🌟 Overview

Release 22M completes the deployment of the pending cancellation request visibility hotfix to production. Because Release 22J (Profile Editor MVP) remains paused, current `main` (which contains 22J) could not be deployed directly. Instead, a temporary hotfix branch `hotfix/22m-cancellation-visibility-hotfix` was branched from the Release 22I baseline (`48874f0`). Only the minimal 22L changes were applied to `AdminDashboard.jsx`. 

This hotfix resolves a visibility gap in the Admin Portal where clients' pending booking cancellation requests (`CANCELLATION_REQUESTED`) were completely hidden. Administrators can now view, count, and act on these requests under the "Needs Action" queue.

---

## 🛠️ Changes Implemented (Hotfix Branch)

### A. Frontend Filter Logic (`web/src/components/AdminDashboard.jsx`)
* **Terminal Status Mapping:** Redefined `isCancelledRecord(item)` to only return `true` for final terminal cancellation statuses: `CANCELLED`, `DECLINED`, `REJECTED`, and `CANCELLATION_DENIED`. 
* **Pending Status Mapping:** Implemented `isCancellationPendingRecord(item)` for `CANCELLATION_REQUESTED`.
* **Active List Inclusion:** Updated `isActiveRecord(item)` to return `true` for pending cancellation records. As a result:
  * Pending cancellation requests are correctly listed in the **Needs Action** list and the **All Active** list.
  * Sidebar and header counts correctly include pending cancellations under the active category.
  * The **Cancelled** tab contains only final cancelled records.

### B. Row UI & Status Styling
* **Status Label:** Updated `getStatusLabel` to translate `CANCELLATION_REQUESTED` to `"Cancellation Requested"`.
* **Urgent Badge Styling:** Updated `getStatusClass` to assign the `"status-chip status-chip--urgent"` class to pending cancellations, rendering them as a highly visible red chip in the table row.
* **Dropdown Actions:** Mapped `CANCELLATION_REQUESTED` in `getWorkflowState` to expose `"Review Cancellation"`. Clicking this option triggers `handleProcessCancellation(item)` to launch the decision overlay (Approve/Deny review flow).

---

## 📦 Build & Deployment Summary

* **Hotfix Branch:** `hotfix/22m-cancellation-visibility-hotfix`
* **Baseline Commit Used:** `48874f0` (Release 22I baseline)
* **Code Modification Commit:** `1215700`
* **Vite Production Compilation:** Passed (`npm run build` completed in `363ms`).
* **S3 Sync Location:** `s3://togs-and-dogs-prod-toganddogs-hosting` (using `usmissionhero-website-prod` profile)
* **CloudFront Invalidation ID:** `I4ABCENFFCX5937IMJAH9LN89T` (distribution `E35L00QPA2IRCY` — `Completed`)
* **Production Bundle Reference:**
  * **JS Bundle:** `/assets/index-BU-WCL8y.js`
  * **CSS Bundle:** `/assets/index-fLn3j3dM.css`
* **Regression Check:** No Release 22J features (Profile Editor side drawer, card simplifications, security panel UI, or drawer CSS) were included in this build.

---

## 🔬 Production Validation Results

We performed validation in the live production environment (`toganddogs.usmissionhero.com`) using a browser subagent session (recording saved to artifacts):

* **Needs Action Queue:** 
  * Pending cancellation requests (e.g. `Joey Rockwell` and `TestPet_ScenarioB`) are now visible.
  * Their status is displayed as **"Cancellation Requested"** in a red warning chip.
  * Active/Needs Action sidebar counts are correctly computed.
* **Actions Menu:** 
  * The Actions dropdown for `CANCELLATION_REQUESTED` rows exposes **"Review Cancellation"**, which launches the existing Approve/Deny flow.
  * No cancellation action was actually approved or denied during validation.
* **Cancelled Tab:** 
  * Verified to have `0` records. Pending cancellations are not leaked into the final cancelled tab.
* **22J Profile Editor Regression:** 
  * Verified that **NO "Manage" button** exists on any staff cards.
  * Verified that clicking **"Edit"** on a staff card opens the inline form at the top (with a "Cancel Edit" button) instead of triggering a new Profile Editor drawer overlay.
* **Client Portal:** 
  * Confirmed that `/my-bookings` loads successfully.

---

## 🛡️ Guardrails Checked

* **Zero Backend Mutations:** No backend Lambdas or API Gateway configurations were deployed. No Terraform plan or apply was run.
* **Zero Database Mutations:** No DynamoDB writes were performed. No records were modified, deleted, or backfilled.
* **Zero Identity Mutations:** No Cognito users, groups, or login parameters were altered.
* **Zero Notification Side-Effects:** No invite or password emails were triggered.
