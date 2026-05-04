# Release Notes: Production Feedback (Intake, Calendar, & Modal UX)

**Date**: 2026-04-30
**Environment**: Production (`usmissionhero-website-prod`)
**Commit**: `62c240beae329eef406c2227d1013473d84da23b`
**CloudFront Invalidation**: `ICGNCCAR7U6O0KCGGSVNYJDCDM`

## Ryan's Feedback Addressed

### 1. Intake Form Optimization
- **Change**: Removed the "Specific Time Requests" field from the public intake form (`IntakeForm.jsx`).
- **Data Preservation**: Historical `preferred_time` data remains in the database. It is now displayed as "Legacy Information" in the Admin Modal's "Visit Details" tab only if the field is not empty.

### 2. Cognito Admin Invitation Fix
- **Issue**: Admin-created user invitations were failing due to missing SMS configuration in the production environment.
- **Fix**: Updated `admin_handler.py` to enforce `DesiredDeliveryMediums=["EMAIL"]`.
- **Security**: Stripped `phone_number` attributes from Cognito creation to avoid triggering SMS requirements. Staff phone numbers remain stored in the application's staff profiles for internal use.

### 3. Google Calendar Trigger Investigation
- **Findings**: Calendar sync is triggered **exclusively** during the staff assignment phase (`assignment_handler.py`). It is not triggered on intake submission or initial approval.
- **Behavior**: If a job is re-assigned, the existing calendar event is updated or a new one is created.

### 4. Exact Calendar Timing
- **Feature**: Added `scheduled_time` and `scheduled_duration` fields to the record schema.
- **Behavior**: 
    - If a `scheduled_time` is set by the admin before assignment, the Google Calendar event will be created with precise `start.dateTime` and `end.dateTime`.
    - Defaults to a **1-hour duration** if not specified.
    - Timezone is hardcoded to `America/New_York`.
    - If no time is set, it falls back to an all-day event on the `start_date`.

### 5. Admin Record Modal Tabbed UX
- **Refactor**: Replaced the long, sectioned `CareCard.jsx` with a modern tabbed interface.
- **Tabs Structure**:
    1. **Overview**: Key identity, health summary, and status.
    2. **Visit Details**: Service type, requested window, and legacy timing notes.
    3. **Pet Care**: Detailed behavior and care instructions.
    4. **Vet & Emergency**: Contact info for vets and emergency contacts.
    5. **Meet & Greet / Quote**: M&G status and pricing details.
    6. **Scheduling / Staff**: Exact timing controls and worker assignment.
    7. **Admin Notes / History**: Internal notes and audit logs.
- **UX Improvement**: Lifecycle actions (Status update, Approve, Complete, etc.) are pinned to the bottom of the modal, ensuring they are always accessible regardless of the active tab.

## Scope & Non-Scope
- **In Scope**: Targeted fixes for intake, Cognito, Calendar, and Modal navigation.
- **Non-Scope**: Database schema migration (DynamoDB remains schemaless; new fields are added organically). No changes to the public site homepage or customer login flow.

## Test Results
- **Frontend Build**: `npm run build` - SUCCESS.
- **Backend Tests**: `pytest tests/backend/test_intake_validation.py` - 6 PASSED.
- **Manual Verification**: 
    - Verified `preferred_time` is gone from intake.
    - Verified tabs in `CareCard` load correctly.
    - Verified Cognito resend invite includes `EMAIL` delivery medium.

## Deployment Details
- **Backend**: 8 Lambda functions updated via AWS CLI using a direct zip upload from `src/backend`.
- **Frontend**: Vite build synced to `togs-and-dogs-prod-toganddogs-hosting` S3 bucket.
- **Invalidation**: `/*` path invalidated on distribution `E35L00QPA2IRCY`.

## Final Closeout Verification (2026-05-01)

### 1. Repository & Deployment
- **Latest Commit**: `60720cf`
- **CloudFront Invalidation (`ICGNCCAR7U6O0KCGGSVNYJDCDM`)**: **COMPLETED**. Verification performed via production URL, confirming the propagation of the new tabbed UI and intake form changes.
- **Git Status**: Working tree clean; pushed to `origin/main`.

### 2. Production Smoke Test Results
- **Public Intake**: "Specific Time Requests" successfully removed. Form submission validated with test record "Buddy (Verification Test)".
- **Admin Record Modal**: Tabbed interface (7 sections) verified on live production environment.
- **UX**: Status actions and profile creation buttons are consistently visible and functional across all tabs.

### 3. Cognito & Security Verification
- **Invitation Logic**: `admin_handler.py` updated to set `DesiredDeliveryMediums=["EMAIL"]`.
- **SMS Requirements**: Stripped all phone-related attributes from Cognito creation to prevent errors in non-SMS configured environments. Invitations now deliver reliably via email only.

### 4. Google Calendar Sync Test
- **Test Case**: Buddy (Verification Test).
- **Configuration**: Scheduled for 2026-05-05 at 14:00 (2:00 PM) for 60 minutes.
- **Payload Logic**: Confirmed `google_calendar.py` uses `start.dateTime` and `end.dateTime` with `America/New_York` timezone.
- **Trigger**: Confirmed sync triggers correctly upon staff assignment.

## Remaining Risks & Blockers
- **None**: All targeted production feedback items are resolved and verified in the live environment.

---
*For questions regarding this deployment, contact the dev team or refer to the DECISIONS_LOG.md.*
