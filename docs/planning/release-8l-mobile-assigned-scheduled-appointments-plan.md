# Release 8L Implementation Plan: Mobile Assigned/Scheduled Appointment Visibility

This plan outlines the read-only integration of assigned appointments, scheduled visits, and multi-day child job representation inside the React Native / Expo mobile app.

---

## 1. Goal Description
The mobile application currently integrates with the Intake Requests queue, but once a booking is approved and assigned a staff member (status becomes `ASSIGNED`), it is hidden from the mobile application. This is because:
1. The mobile filter list in `RequestListScreen` only lists `PENDING_REVIEW`, `APPROVED`, `COMPLETED`, and `CANCELLED`.
2. The `ScheduleScreen` (Visits tab) is a static placeholder and is not visible to admin/owner accounts.

This release will implement read-only assigned/scheduled data integration inside `/mobile` to allow Ryan and his sitters to view full active assignments, daily/weekly visit lists, multi-day calendar expansion, and details.

---

## 2. User Review Required

> [!IMPORTANT]
> **Read-Only Enforced:** No scheduling mutations, worker re-assignments, status updates, or other writes are permitted in this release.

> [!NOTE]
> **No Backend Modifications:** We will utilize the existing API Gateway endpoints:
> - `/admin/requests?status=ASSIGNED` (returns assigned parent requests)
> - `/admin/requests?status=ALL` (returns all active requests; automatically scoped to staff assignments when logged in as a sitter)

---

## 3. Open Questions
* *Are there any plans to expand the schedule view to include map routing for sitters in a future release?* (Not scoped for 8L, but helpful for UI structuring).

---

## 4. Proposed Changes

We will modify only files under the `/mobile` directory.

### Mobile Navigation

#### [MODIFY] [AppNavigator.tsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/navigation/AppNavigator.tsx)
- Add the `ScheduleScreen` (Visits list) to the `AdminTabs` tab bar so that owner/admin accounts (Ryan) can view the dispatch schedule.

---

### Mobile Screens

#### [MODIFY] [RequestListScreen.tsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/screens/RequestListScreen.tsx)
- Add a new `'ASSIGNED'` filter pill labeled **"Scheduled"**.
- This will query `/admin/requests?status=ASSIGNED` to display assigned parent bookings.

#### [MODIFY] [ScheduleScreen.tsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/screens/ScheduleScreen.tsx)
- Connect this screen to the live API using `getAdminRequests('ALL')`.
- If logged in as **owner/admin**, it shows all active scheduled assignments.
- If logged in as **staff**, the backend automatically scopes the query to only return their assigned visits.
- **Multi-Day Date Expansion:** Expand parent bookings with multiple `selected_dates` into individual daily list items chronologically.
- Show date, visit window, service type, client name, pet name, and assigned sitter.

---

### Mobile Components & Types

#### [MODIFY] [RequestCard.tsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/mobile/src/components/RequestCard.tsx)
- Update the layout to display the assigned sitter name (`worker_name`) inside the details panel when status is `ASSIGNED`.

---

## 5. Verification Plan

### Automated Validation
- Run TypeScript type checking from `/mobile`:
  ```bash
  npx tsc --noEmit
  ```
- Run Expo project doctor check:
  ```bash
  npx expo-doctor
  ```

### Manual Verification
- Launch Metro server:
  ```bash
  npx expo start --clear --lan
  ```
- Scan the QR code on the physical iPhone Expo Go app.
- Confirm the new "Scheduled" category pill renders and returns correct list of requests.
- Navigate to the "Schedule" tab on both Admin/Owner and Staff test credentials and verify visit cards, multi-day date breakdowns, and sitter names.

---

## 6. Rollback Plan
- Run `git restore mobile/` to revert changes to initial state.
- Keep dependency files locked to current SDK 54 baseline.

---

> [!WARNING]
> **DO NOT RUN IMPLEMENTATION UNTIL MATTHEW APPROVES.**
