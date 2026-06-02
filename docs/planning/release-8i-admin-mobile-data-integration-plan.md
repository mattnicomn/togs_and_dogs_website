# Release 8I: Admin Mobile Data Integration Plan

**Status:** Planning  
**Priority:** High  
**Implementation:** None until Matthew approves  
**Scope:** Admin requests list, API integration, data mapping, screen layout definitions, read-only focus

---

## 1. Recap of 8G/8H Baselines

The local workspace has established a robust, compile-clean mobile foundation:
* **Release 8G:** Initialized the `/mobile` Expo managed framework, configured core types, TypeScript settings, and excluded transient folders via `.gitignore`.
* **Release 8H:** Scaffolded the Cognito secure auth provider context (`AuthContext.tsx`), native encrypted storages (`storage.ts`), the fetching API client (`client.ts`), unauthenticated stack routers (`AuthNavigator.tsx`), role-based switches (`AppNavigator.tsx`), and placeholder stubs for all user roles.

---

## 2. Likely Files Affected

This data integration phase will be contained strictly inside the `/mobile` directory:

| File Path | Mode | Modification Detail |
|---|---|---|
| **[mobile/src/screens/RequestListScreen.tsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/screens/RequestListScreen.tsx)** | **MODIFY** | Overwrite the placeholder to render a live, scrollable FlatList of intake requests fetched from the API. |
| **[mobile/src/screens/DashboardScreen.tsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/screens/DashboardScreen.tsx)** | **MODIFY** | Connect status metrics (PENDING_REVIEW count, active assignments count) to live database tallies instead of placeholders. |
| **[mobile/src/components/RequestCard.tsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/components/RequestCard.tsx)** | **NEW** | Reusable card UI rendering client details, service types, date tags, and status chips with touch parameters. |
| **[mobile/src/components/StatusBadge.tsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/components/StatusBadge.tsx)** | **NEW** | Compact tag with high-contrast text and border styling tailored to booking states (PENDING_REVIEW, APPROVED, ASSIGNED). |

---

## 3. Deployed API Endpoint Inventory

The mobile app will consume the exact, production API endpoints mirroring the web dashboard:

| Target Path | Method | Auth Required | Purpose | Payload / Parameters |
|---|---|---|---|---|
| `/admin/requests` | `GET` | **Yes** (getIdToken) | Fetch current intake requests list. | `?status=PENDING_REVIEW` |
| `/admin/staff` | `GET` | **Yes** (getIdToken) | Fetch workers list for scheduling lookup. | None |
| `/admin/clients` | `GET` | **Yes** (getIdToken) | Fetch active client lookup lists. | None |

---

## 4. Request Record Data Model Mapping

The API returns raw DynamoDB request records. The mobile app will map these attributes onto cleaner UI card nodes:

```typescript
export interface PetRequest {
  request_id: string;      // maps to PK/SK indexes
  client_id: string;
  client_name: string;     // displayed at card header
  pet_name: string;        // displayed alongside service labels
  service_type: string;    // e.g. "dog_walking", "pet_sitting"
  selected_dates: string[];// array of ISO date strings
  status: string;          // e.g. "PENDING_REVIEW", "APPROVED"
  created_at: string;      // displayed as relative time tag
  special_instructions?: string; // collapsible notes details
}
```

### UI Color Tag Mapping (theme/colors.ts matchers)
* `PENDING_REVIEW` -> `#f3efe8` background, `#3c3c3b` text
* `APPROVED` -> `#edf2ee` background, `#2e4d38` text
* `ASSIGNED` -> `#fcf6e9` background, `#8c6412` text
* `CANCELLED` -> `#fdf2f0` background, `#9b2c1d` text

---

## 5. Screen Layout & Mobile UX

The **RequestListScreen** will adapt to a scrollable single-column card list specifically tailored for one-handed operation:

* **Top Bar:** Screen title ("Intake Requests") alongside a fresh reload trigger icon and a status category selector (horizontal scrolling pill filters: *Pending*, *Approved*, *All*).
* **FlatList Feed:** Scrollable cards listing active requests, using `onRefresh` hooks for pull-to-refresh.
* **Collapsible Details:** Tapping a request card expands details inline to reveal specials, instructions, or booking dates without switching context.
* **Responsive Tablet Layout:** For iPad viewports (detected via `useWindowDimensions()`), a two-column split-pane opens (left = scroll list, right = request detail inspector) to maximize screen efficiency.

---

## 6. Read-Only Recommendation First

To ensure zero risk to active production operations and verify auth/connection stability, **we recommend a strictly read-only scope for Phase 1 of Release 8I**:
1. Implement requests fetching, scrolling, and filtering.
2. Implement staff and client lookup directories.
3. **Defer all status mutations** (approvals, staff assignments, or cancellations) to a subsequent release package (Release 8J). This verifies the mobile foundation's retrieval performance and JWT token lifecycle before authorizing state modification.

---

## 7. Risks and Rollback

| Risk | Impact | Severity | Mitigation |
|---|---|---|---|
| JWT Session Expires | Fetch fails with `401 Unauthorized`. | Low | `AuthContext` detects expiry and prompts redirect back to `LoginScreen`. |
| Unhandled payload structure | App crash on render. | Medium | Strict TypeScript interface mapping and custom error boundaries in screen lists. |
| Network latency | Infinite spinner states. | Low | Pull-to-refresh and clear timeout handlers. |

**Rollback Command:** `git checkout main && git clean -fd`  
**Rollback Impact:** Zero risk. No backend, web, or AWS resources are modified.

---

## 8. Pre-Commit Validation Checklist

Before staging and committing this integration package, the following validation sweeps must pass cleanly from within the `/mobile` directory:
1. `npx tsc --noEmit` — confirm TypeScript builds with zero typing errors.
2. `npm run start -- --help` — confirm Metro bundler scripts launch safely.
3. `git status` — confirm no web, backend, or AWS files are staged.

---

## 9. Explicit Guardrails

- **NO** changes are permitted under `web/` directory runtime files.
- **NO** production static assets will be synchronized to S3.
- **NO** CloudFront CDN invalidations will be created.
- **NO** AWS backend code, Python Lambda packages, Terraform files, Cognito parameters, or database instances will be touched.
- **NO** AWS CLI profile commands will be executed against live profiles in these validation passes.

---

## 10. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8I: Admin Mobile Data Integration.

Please implement the read-only intake requests data list inside the mobile/ folder.
No modifications to web/, backend/, infra/, or AWS profiles are allowed.

=== 1. Create RequestCard Component ===
Create mobile/src/components/RequestCard.tsx:
  - Takes a PetRequest object as prop.
  - Renders a clean card containing client_name, pet_name, service_type (styled text), status badge, and date tags.
  - Implement a collapsible section for special_instructions.
  - Render high-contrast role badges based on colors.ts mapping.

=== 2. Create StatusBadge Component ===
Create mobile/src/components/StatusBadge.tsx:
  - Takes a status string.
  - Returns a rounded, borders-matched chip styling according to the plan status color mapping.

=== 3. Overwrite RequestListScreen ===
Modify mobile/src/screens/RequestListScreen.tsx:
  - Call getAdminRequests('PENDING_REVIEW') on load.
  - Render results using a FlatList.
  - Add pull-to-refresh support using RefreshControl.
  - Add horizontal scrolling category filters at top (Pill buttons: Pending, Approved, Completed, Cancelled).
  - Add loading spinners and error states.

=== 4. Overwrite DashboardScreen ===
Modify mobile/src/screens/DashboardScreen.tsx:
  - Fetch active request queue list.
  - Renders stats cards showing live count of pending requests.
  - Keep logout option functional.

=== 5. Validate TypeScript and Compilation ===
Verify npx tsc --noEmit compiles with 0 errors.
Verify npm run start -- --help executes cleanly.

Return: files created, TypeScript compilation status, list of endpoints connected, and git status.
```
