# Release Notes - Workflow Cleanup & Separation

## Overview
This update decouples the **New Customer Intake** process from the **Approved Client Visit Booking** workflow. This separation improves administrative clarity, enhances security by restricting public access to booking tools, and provides a more structured experience for both staff and clients.

## Key Changes

### 1. Workflow Model & Mapping
- **Contextual Categorization**: Introduced `WorkflowType` (`CUSTOMER_INTAKE` vs. `VISIT_BOOKING`).
- **Compatibility Mapping**: Implemented a non-destructive heuristic to classify existing records based on their status and metadata (e.g., service type, staff assignment).
- **Status Clarification**: UI labels now reflect the context (e.g., "Approved Client" for registrations vs. "Booked" for visits).

### 2. Guardrails & Security
- **Public Form Restriction**: The public intake form is now strictly for new customer registrations.
- **Portal Booking Check**: Only approved clients with enabled portal access can submit visit requests.
- **Onboarding Block**: Non-approved clients attempting to book visits will see a message indicating their profile is still under review.

### 3. Admin Dashboard Reorganization
- **New Customer Intake Queue**: A dedicated group for managing new registrations, profile creation, and Meet & Greets.
- **Visit Requests Queue**: A dedicated group for managing booking requests, quotes, and staff assignments.
- **Simplified Navigation**: Sidebar filters are now organized by business function rather than a raw list of statuses.

## Compatibility & Safety
- **No Data Migration**: No existing records in DynamoDB were modified or renamed.
- **Feature Preservation**: Staff assignment, calendar synchronization, and terminal states (Completed/Archive/Trash) remain fully functional.
- **Fail-Safe Notifications**: Notification hooks are implemented as non-blocking logging events to prevent workflow stalls during unconfigured delivery states.

## Known Risks
- **Legacy Classification**: Very old records with generic "PET_SITTING" services may appear in the Intake queue until they are processed or archived.
- **Admin Review**: Admins should monitor the "Needs Action" group for any misclassified legacy items.

## Rollout Plan
- **Verification**: Build and syntax validation complete.
- **Deployment**: Safe for deployment to staging/production via Lambda source updates.
