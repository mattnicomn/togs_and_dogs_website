# Align Staff and Client User Management

Align the Staff and Client management experiences to support a consistent access management framework, including email-based invitations, Cognito linking, and account security actions.

## API Endpoint Contracts

### 1. User Onboarding (Invite by Email)
- **POST `/admin/staff/onboard`**
- **POST `/admin/clients/onboard`**
    - **Payload**:
        ```json
        {
          "display_name": "Required string",
          "email": "Required string (verified email)",
          "role": "Staff|Admin|owner (Staff only)",
          "phone": "Optional string",
          "is_assignable": "Boolean (Staff only)",
          "assignment_color": "String (Staff only)",
          "mode": "Optional ('create_or_link' to link if Cognito user exists)"
        }
        ```
    - **Behavior**:
        - Creates/locates Cognito user.
        - Assigns Cognito group (`Staff|Admin|owner` for staff, `client` for clients).
        - Creates/updates DynamoDB profile.
        - Triggers Cognito invitation email.
    - **Allowed Roles**: `owner`, `admin`.

### 2. Account Security Actions (One-off)
- **POST `/admin/{type}/{id}/resend-invite`**
- **POST `/admin/{type}/{id}/reset-password`**
- **POST `/admin/{type}/{id}/set-temp-password`**
    - **Payload (set-temp-password)**: `{"password": "new_temp_password"}`
    - **Behavior**: Direct Cognito Admin API calls (`admin_create_user(RESEND)`, `admin_reset_user_password`, `admin_set_user_password`).
    - **Allowed Roles**: `owner`, `admin`.

### 3. Lifecycle & Linking Actions (PATCH)
- **PATCH `/admin/{type}/{id}`**
    - **Payload**: `{"action": "disable" | "enable" | "unlink" | "delete_profile" | "delete_cognito"}`
    - **Behavior**:
        - `disable`: Sets `is_active=false` in DDB, disables user in Cognito.
        - `enable`: Sets `is_active=true` in DDB, enables user in Cognito.
        - `unlink`: Removes `cognito_sub` and related auth fields from DDB.
        - `delete_profile`: Deletes DDB record (only if `is_active=false`).
        - `delete_cognito`: Deletes Cognito user account.
    - **Guardrails**: Prevents self-disable or modification of protected admin accounts.

### 4. Link Existing User
- **POST `/admin/{type}/{id}/link-cognito`**
    - **Payload**: `{"username": "email_or_sub"}`
    - **Behavior**: Maps existing Cognito user to DynamoDB profile and adds to correct group.

## Access Status Logic
The UI will derive status using the following priority:
1.  **Disabled**: `is_active === false`
2.  **No Login**: `!cognito_sub`
3.  **Invited**: `cognito_status` IN (`FORCE_CHANGE_PASSWORD`, `UNCONFIRMED`)
4.  **Password Reset Required**: `cognito_status === 'RESET_REQUIRED'`
5.  **Active**: `cognito_status === 'CONFIRMED'`
6.  **Cognito Mismatch**: (Optional check) Email/Sub mismatch.

## User Review Required


> [!IMPORTANT]
> The "Invite by Email" feature will use Cognito's `admin_create_user` with `DesiredDeliveryMediums=['EMAIL']`. This sends an automated email from Cognito. We should verify if there are specific branding requirements for this email, although Cognito defaults are usually sufficient for this stage.

> [!NOTE]
> Client access will be restricted to the "client" Cognito group, which maps to the existing client portal permissions.

## Proposed Changes

### Backend: admin_handler.py

#### [MODIFY] [admin_handler.py](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/src/backend/handlers/admin_handler.py)
- **Generalize Account Security Routes**:
    - Update the `/reset-password`, `/set-temp-password`, and `/resend-invite` handlers to support both staff and client IDs by checking the SK prefix (`STAFF#` or `CLIENT#`).
    - Add a new `/link-cognito` handler for clients (similar to the staff one).
- **Implement Client Onboarding**:
    - Add `POST /admin/clients/onboard` to handle "Invite by Email" for clients.
    - Logic should include: Cognito user creation, group assignment (`client`), and DynamoDB profile creation/linking.
- **Guardrail Hardening**:
    - Ensure protected accounts (owners/admins) cannot have their roles downgraded via `PATCH /admin/staff`.
    - Prevent self-disable and unlinking of active protected admin accounts.
    - Ensure `is_protected_profile` remains robust.
- **Data Integrity**:
    - Ensure DynamoDB remains the authoritative source for profile fields (`display_name`, `phone`, etc.).
    - Cognito attributes should NOT overwrite DynamoDB fields.

### Frontend API: client.js

#### [MODIFY] [client.js](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/api/client.js)
- Add missing client access management API calls:
    - `onboardClient(data)`
    - `resendClientInvite(clientId)`
    - `resetClientPassword(clientId)`
    - `setClientTempPassword(clientId, password)`
    - `linkClientCognitoUser(clientId, data)`

### Frontend UI: AdminDashboard.jsx

#### [MODIFY] [AdminDashboard.jsx](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)
- **Align Client Management UI**:
    - Add `creation_mode` (Invite by Email vs Profile Only) to the Client creation form.
    - Change "Onboard New Cognito User" to "Invite by Email" for both forms.
- **Implement Access Status Indicators**:
    - Display the calculated access status in both Staff and Client cards.
- **Add Account Actions**:
    - Add a "Security" or "Access" section to Client cards with:
        - Resend Invite
        - Send Password Reset
        - Set Temp Password
        - Link/Unlink Cognito
        - Enable/Disable Access
- **Refactor Event Handlers**:
    - Update `executeClientAction` and `handleSaveClient` to support the new onboarding and security workflows.
    - Ensure frontend respects protected account guardrails (hide/disable destructive buttons).


## Verification Plan

### Automated Tests
- Run existing backend tests: `pytest tests/backend/test_protected_accounts.py` and `pytest tests/backend/test_rbac_and_purge_safety.py`.
- Add a new test script (or manual check) for client onboarding and security actions if possible.

### Manual Verification
- **Staff Management**:
    - Test "Invite by Email" (Onboard).
    - Test "Resend Invite".
    - Test "Send Reset".
    - Test "Disable/Enable Access".
    - Verify protected admin cannot be downgraded or disabled.
- **Client Management**:
    - Test "Invite by Email".
    - Test "Resend Invite".
    - Test "Send Reset".
    - Test "Disable/Enable Access".
    - Test "Link/Unlink Cognito".
- **Status Indicators**:
    - Verify all status labels display correctly based on state.

### Build
- Run `npm run build` in the `web` directory to ensure no regressions in the frontend bundle.
