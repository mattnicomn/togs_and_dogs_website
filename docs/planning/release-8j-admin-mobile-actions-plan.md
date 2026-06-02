# Release 8J: Admin Mobile Actions Plan

**Status:** Planning  
**Priority:** High  
**Implementation:** None until Matthew approves  
**Scope:** Safe admin actions (Approve request, Details view expansion, Reloads), confirmation modals, guardrails, read-only transitions

---

## 1. Executive Summary

This planning document outlines the technical design for introducing **low-risk admin actions** to the Tog & Dogs React Native mobile application. Release 8I successfully connected the mobile client to the production API in a read-only state. Release 8J introduces safe state mutations (such as single-booking approvals) while ensuring zero risk of double notifications, calendar duplication, or unhandled database anomalies.

---

## 2. Review of Web Admin Action Flows

The active web application (`web/src/api/client.js`) supports several key admin actions. The mobile app evaluates these as follows for Release 8J:

| Web Admin Action | API Call Pattern | Release 8J Recommendation | Reasoning |
|---|---|---|---|
| **Approve Request** | `reviewRequest(reqId, clientId, 'APPROVED')` | **SUPPORTED** | High-utility for Ryan. Existing backend safely coordinates calendar locks, staff-alert flags, and client alerts. |
| **Reject/Decline** | `reviewRequest(reqId, clientId, 'REJECTED', reason)` | **DEFERRED** | Declines are rare and require detailed custom text inputs. Better suited for web interface. |
| **Assign Worker** | `assignWorker(jobId, reqId, clientId, workerId, workerName)` | **DEFERRED** | Involves complex staff schedules and multi-day routing overlays. Safer on desktop. |
| **Google Auth Sync** | `initiateGoogleAuth()`, `disconnectGoogle()` | **DEFERRED** | Involves browser redirect cookies. Keep on desktop. |
| **Bulk Purge / Purge** | `purgeRecordsBulk()`, `purgeRecord()` | **DEFERRED** | Destructive data removal. Defer to desktop to prevent accidental deletion. |
| **Data Export** | `getExportData()` | **DEFERRED** | Heavy Excel downloads. Desktop only. |

---

## 3. Safe Mutation Design (Owner/Admin Path)

For Release 8J, the mobile app will support **Approve Request** as the sole mutation action.

### 3.1 Reusing the Deployed API Endpoint

No backend code changes are needed. The API client implemented in Release 8H (`client.ts`) already has the necessary fetch structure, which maps directly to the production gateway:

```typescript
// mobile/src/api/client.ts (verified live endpoint reuse)
export const reviewRequest = (requestId: string, clientId: string, status: string, reason = "") => 
  request('/admin/review', 'POST', { 
    request_id: requestId, 
    client_id: clientId, 
    status, 
    reason 
  }, true);
```

---

## 4. UI Elements and Mobile-First Interaction Flow

To introduce the approval action safely in the mobile layout, we will build a dedicated, confirmation-locked workflow within `RequestCard.tsx`:

* **Collapsible Primary Actions:** Tapping a request card expands details. If the request status is `PENDING_REVIEW`, a clean, gold **"Approve Booking"** button is displayed at the bottom of the card.
* **Confirmation Overlay (Notch Safe):** Tapping the button opens a React Native modal dialog overlay:
  * **Header:** "Approve Pet Booking?"
  * **Text:** "This will update the status of [Pet Name]'s [Service] for [Client Name] to APPROVED and trigger system notification emails. Are you sure you want to proceed?"
  * **Action Row:** Left = "Cancel" (gray, cancels dialog), Right = "Confirm Approval" (solid brand-green, triggers API request).

---

## 5. Security & Operational Guardrails

To protect production workflows, the following strict guardrails are designed into this release:

1. **Anti-Double-Tap Controls:** The "Confirm Approval" button immediately disables and displays an ActivityIndicator spinner when pressed. This prevents multiple parallel HTTP requests from firing due to network latency, eliminating the risk of duplicate calendar locks or double-notification runs.
2. **Cognito Token Lifecycle:** If the active JWT token expires during the modal action, the API client catches the `401 Unauthorized` state, aborts the mutation cleanly, closes the modal, and safely logs the user out.
3. **No Destructive Controls:** Deletion, archiving, and bulk purges are completely hidden from the mobile viewport, ensuring that accidental pocket-taps cannot cause production data loss.

---

## 6. Pre-Commit Validation checklist

Staging and committing Release 8J is blocked until the following validation metrics compile successfully within the `/mobile` directory:
1. `npx tsc --noEmit` — confirms zero TypeScript compile errors.
2. `npm run start -- --help` — confirms Metro dev servers start cleanly.
3. `git status` — confirms zero changes under `web/`, lambda code `src/`, or Terraform configuration `infra/` are staged.

---

## 7. Risks and Rollback

| Risk | Impact | Mitigation |
|---|---|---|
| Physical tap slips / pocket clicks | Accidental approval email triggers | Double-action confirmation dialog overlays. |
| API call failure / timeout | Request stays in PENDING state | Error message is caught, loading state stops, and a notification banner advises the user to check their connection and retry. |

**Rollback Strategy:**  
If any runtime anomalies are detected on physical simulator screens:
- **Command:** `git checkout main && git clean -fd`
- **Effect:** Reverts 100% of the mobile files to the stable, compile-clean Release 8I baseline.

---

## 8. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8J: Admin Mobile Actions.

Please implement the safe read-write approval transitions in /mobile.
No modifications to web/, backend/, infra/, or AWS profiles are allowed.

=== 1. Add reviewRequest API Method ===
Ensure mobile/src/api/client.ts exports the exact reviewRequest endpoint mirror:
export const reviewRequest = (requestId: string, clientId: string, status: string, reason = "") => 
  request('/admin/review', 'POST', { 
    request_id: requestId, 
    client_id: clientId, 
    status, 
    reason 
  }, true);

=== 2. Create Confirmation Modal ===
Implement a reusable modal in mobile/src/components/ConfirmationModal.tsx:
  - Takes visible (boolean), title, message, onConfirm, and onCancel as props.
  - Highly styled, rounded cards using safe area parameters.
  - Spinner support on the confirm button when processing state is active.

=== 3. Integrate Approve Action in RequestCard ===
Modify mobile/src/components/RequestCard.tsx:
  - Add an "Approve Booking" button visible only when status is "PENDING_REVIEW".
  - Pressing triggers the ConfirmationModal.
  - Implement dynamic isLoading and error states inside the card context.
  - On confirm, trigger client reviewRequest API call.
  - If successful, fire local refresh callbacks to update FlatList queues.

=== 4. Connect Refresh Callbacks ===
Modify mobile/src/screens/RequestListScreen.tsx:
  - Pass down refresh callbacks to RequestCard nodes.
  - When approval resolves, trigger refresh controls.

=== 5. Validate TypeScript and Compilation ===
Verify npx tsc --noEmit compiles with 0 errors.
Verify npm run start -- --help executes cleanly.

Return: files modified/created, compilation results, and git status.
```
