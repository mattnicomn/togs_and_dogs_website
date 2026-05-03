# Google Calendar Production Cutover Guide

This document outlines the steps to transition the Togs and Dogs Google Calendar integration from the **Test Integration (Matthew)** to the **Production Integration (Ryan)**.

## Overview
The current integration uses Matthew's Google Cloud Project and Google account. To cut over to Ryan's account, we must rotate the OAuth credentials and re-establish the refresh token.

---

## Step 1: Google Cloud Console Setup (Prod)
1.  **Project**: Create or select Ryan's production Google Cloud Project.
2.  **API**: Enable the **Google Calendar API**.
3.  **OAuth Consent Screen**:
    *   Set to `External`.
    *   Add `https://toganddogs.com` to Authorized Domains.
4.  **Credentials**: Create an **OAuth 2.0 Web Client ID**.
    *   **Authorized Redirect URIs**:
        *   `https://a022yxuiue.execute-api.us-east-1.amazonaws.com/prod/admin/auth/callback`
        *   `https://toganddogs.com/admin/auth/callback`
5.  **Record**: Copy the `Client ID` and `Client Secret`.

---

## Step 2: AWS Secret Rotation
We must replace the test credentials in AWS Secrets Manager.

1.  **Secret**: `togs-and-dogs-prod/google/client-creds`
    *   Update the value with the new production Client ID and Secret:
    ```json
    {
      "client_id": "RYAN_PROD_CLIENT_ID",
      "client_secret": "RYAN_PROD_CLIENT_SECRET"
    }
    ```
2.  **Secret**: `togs-and-dogs-prod/google/user-tokens`
    *   **CRITICAL**: Clear the existing value (set to `{}`) or delete the `refresh_token` field. This ensures the system knows a new authorization is required.

---

## Step 3: Production Re-Authorization
1.  Navigate to the **Admin Dashboard** (`/admin`).
2.  The status should now report **Not Connected** or **Credentials Missing** (if Step 2 was done correctly).
3.  Click **Connect Google Calendar**.
4.  Log in as **Ryan's Google Account**.
5.  Grant permissions.
6.  The browser will redirect back to the dashboard, and the status will update to **Connected**.

---

## Step 4: Verification
1.  Approve a test request in the dashboard.
2.  Verify that a `[TEST]` event (or real event post-cutover) appears on Ryan's production Google Calendar.
