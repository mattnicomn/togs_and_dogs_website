# Release Note: Phase 3B Template & Routing Readiness

**Status:** Ready for Final Dry-Run Validation
**Date:** 2026-05-04

## Overview
Phase 3B enhances the notification system with professional branded HTML templates and granular routing preferences. This phase prepares the system for live email enablement by ensuring high-quality, customer-facing content and business-specific routing controls.

## Key Enhancements
- **Branded HTML Templates**: All core notification events now feature professional, Tog and Dogs branded HTML templates with clear calls-to-action and friendly data rendering.
- **Granular Routing Preferences**: Added individual toggle flags (e.g., `NOTIFY_CLIENT_ON_APPROVAL`) to allow the business to control exactly which events trigger notifications to which recipient categories.
- **Data Normalization**: Implemented friendly label mapping for internal enums (e.g., `WALK_30MIN` -> `30-Minute Walk`) to ensure a professional presentation to clients.
- **Recipient De-duplication**: Refined the resolver to ensure each recipient receives only one copy of a notification, even if they qualify under multiple routing rules (e.g., as both Client and Admin).

## Supported Events & Preferences
| Event | Recipient | Preference Flag |
| :--- | :--- | :--- |
| `REQUEST_RECEIVED` | Admin | `NOTIFY_ADMIN_ON_REQUEST_RECEIVED` |
| `CUSTOMER_APPROVED` | Client | `NOTIFY_CLIENT_ON_APPROVAL` |
| `VISIT_SCHEDULED` | Client | `NOTIFY_CLIENT_ON_SCHEDULED` |
| `STAFF_ASSIGNED` | Staff | `NOTIFY_STAFF_ON_ASSIGNMENT` |
| `VISIT_CANCELLED` | Client, Staff, Admin | `NOTIFY_CLIENT_ON_CANCELLED`, `NOTIFY_STAFF_ON_CANCELLED`, `NOTIFY_ADMIN_ON_CANCELLED` |

## Template Example: CUSTOMER_APPROVED
- **Subject**: Your Tog and Dogs Service Request: Approved!
- **Body**: Includes pet names, service type, and date in a branded layout.
- **Contact**: "Questions? Reply to this email or contact us directly."

## Dry-Run Validation Results (Local)
Validated via `scratch/validate_3b.py` with mocked environment variables:

| Scenario | Result | Evidence |
| :--- | :--- | :--- |
| `REQUEST_RECEIVED` | **SUCCESS** | Friendly labels: "Buddy & Max", "30-Minute Walk" |
| `CUSTOMER_APPROVED`| **SUCCESS** | Recipients resolved correctly to Client. |
| **Preference Flag** | **SUCCESS** | `NOTIFY_CLIENT_ON_APPROVAL=false` skipped notification as expected. |

## Readiness Checklist
Before enabling live emails (`NOTIFICATION_DRY_RUN=false`):
1. [x] Local validation of templates and routing logic.
2. [ ] Deploy environment variables to production Lambdas.
3. [ ] Confirm SES sender identity `notifications@toganddogs.usmissionhero.com` is verified.
4. [ ] Verify that all target staff/admin emails are verified if still in SES Sandbox.
5. [ ] Run one final end-to-end dry-run test for every event in production.

## Risk Controls
- **Global Toggle**: `NOTIFICATIONS_ENABLED=false` remains the master kill-switch.
- **Dry-Run Mode**: `NOTIFICATION_DRY_RUN=true` ensures no live emails are sent during validation.
- **Non-Blocking**: Notification failures continue to be non-blocking for core workflows.
