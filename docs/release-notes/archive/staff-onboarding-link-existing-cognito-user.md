# Release Notes: Staff Onboarding Existing Cognito User

## Issue
Onboarding staff with an email that already existed in Cognito resulted in a dead-end error without actionable workflow steps.

## Root Cause
The backend correctly blocked duplicate user creation but offered no path forward.

## Resolution
The onboarding flow has been upgraded:
1. **Dynamic Cognito Linking**: The backend now checks for existing sub values.
2. **Interactive Selection**: Admins map target identities smoothly.

## Technical Scope
- **Backend API**: [admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py)
- **Frontend Dashboard**: [AdminDashboard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)

## Verification
1. Fresh emails instantiate unique accounts securely.
2. Previously active aliases bypass conflicts.

**Commit Snapshot:** `ef36db2`
