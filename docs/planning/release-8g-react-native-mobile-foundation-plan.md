# Release 8G: React Native / Expo Mobile Foundation Setup Plan

**Status:** Planning  
**Priority:** High  
**Implementation:** None until Matthew approves  
**Scope:** Foundation setup, package selection, role-based navigation stubs, API/Auth integration strategy

---

## 1. Release Goals & Guardrails

The goal of Release 8G is to establish a solid native mobile foundation in a new `mobile/` directory. This setup enables building fully integrated, native screens in future releases.

### ⚡ Strict Guardrails

- **NO** changes to backend lambda handler code, dependencies, or packaging.
- **NO** modifications to Terraform infrastructure templates or configurations.
- **NO** direct AWS operations or data model changes.
- **NO** modifications to Cognito pools, attributes, or policies.
- **NO** Google Calendar scheduling sync script edits.
- **NO** Postmark email delivery template or logic updates.
- **NO** changes to the existing production `web/` application (remains untouched).

---

## 2. Directory Structure

The new native application will be placed under the `/mobile` root folder to maintain symmetry with `/web`:

```
togs_and_dogs_website/
├── web/                          ← Existing React/Vite web application (unchanged)
├── mobile/                       ← NEW: React Native / Expo application
│   ├── app.json                  ← Expo app config (slug, orientation, platforms)
│   ├── package.json              ← App dependencies
│   ├── tsconfig.json             ← TS compilation settings
│   ├── babel.config.js           ← Metro/Babel setup
│   ├── App.tsx                   ← Application entry point (renders navigation container)
│   ├── assets/                   ← App icons, splash screens
│   └── src/
│       ├── api/
│       │   ├── client.ts        ← API client (mirrors web/src/api/client.js)
│       │   └── config.ts        ← API URLs & Cognito configuration properties
│       ├── auth/
│       │   ├── cognito.ts       ← direct Cognito Pool interaction logic
│       │   ├── AuthContext.tsx  ← Auth state manager provider
│       │   └── useAuth.ts       ← Auth context hook
│       ├── navigation/
│       │   ├── AppNavigator.tsx ← Routing controller (evaluates JWT roles)
│       │   └── AuthNavigator.tsx← Unauthenticated login stack
│       ├── screens/
│       │   ├── LoginScreen.tsx  ← Authenticated credential collector
│       │   ├── DashboardScreen.tsx ← Admin Dashboard (stub)
│       │   ├── RequestListScreen.tsx ← Admin Request List (stub)
│       │   ├── ScheduleScreen.tsx ← Staff Schedule (stub)
│       │   └── BookingsScreen.tsx ← Client Bookings (stub)
│       └── theme/
│           └── colors.ts        ← Shared UI palette
```

---

## 3. Package Selection Matrix

The mobile foundation will use official, light, and stable standard packages:

| Package | Purpose | Category | Rationale |
|---|---|---|---|
| **`expo`** | Managed App engine | Framework | Managed build environments, automatic native updates. |
| **`typescript`** | Type safety | Compiler | Parallel with modern web best practices. |
| **`amazon-cognito-identity-js`** | Cognito interaction | Auth | Direct Cognito Pool support, fully matches the web implementation. |
| **`expo-secure-store`** | Encrypted keychain | Storage | Securely holds auth tokens on-device, replacing browser `localStorage`. |
| **`react-native-safe-area-context`**| Screen notches | UI | Essential to prevent overlap with hardware notches and indicators. |
| **`@react-navigation/native`** | Base navigation | Routing | Standard routing framework for React Native. |
| **`@react-navigation/native-stack`**| Screen transitions | Routing | Native animations and push/pop navigation transitions. |
| **`@react-navigation/bottom-tabs`** | Main navigation | Routing | Tab bar configuration matching user roles. |

---

## 4. Auth & API Client Patterns

### 4.1 Encrypted Storage Auth Client

Instead of insecure standard storing, React Native uses operating system keychains (`expo-secure-store`):

```typescript
// mobile/src/auth/storage.ts
import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'usr_session_token';

export const saveToken = async (token: string) => {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
};

export const getToken = async (): Promise<string | null> => {
  return await SecureStore.getItemAsync(TOKEN_KEY);
};

export const clearToken = async () => {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
};
```

### 4.2 Reusable API Layer

The mobile client mirrors the web application's REST structures, sending standard authorization headers with every payload:

```typescript
// mobile/src/api/client.ts
import { getToken } from '../auth/storage';
import { API_CONFIG } from './config';

export const apiClient = async (path: string, method = 'GET', body?: any) => {
  const token = await getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_CONFIG.BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Request failed with status ${response.status}`);
  }

  return response.json();
};
```

---

## 5. Role-Based Navigation Routing

User groups are extracted from Cognito JWT claims. When authentication completes, the navigation layout dynamically changes:

```typescript
// mobile/src/navigation/AppNavigator.tsx
import React from 'react';
import { useAuth } from '../auth/useAuth';
import { AuthNavigator } from './AuthNavigator';
import { AdminTabs } from './AdminTabs';
import { StaffTabs } from './StaffTabs';
import { ClientTabs } from './ClientTabs';

export const AppNavigator = () => {
  const { isAuthenticated, role, isLoading } = useAuth();

  if (isLoading) return <LoadingScreen />;
  if (!isAuthenticated) return <AuthNavigator />;

  switch (role) {
    case 'owner':
      return <AdminTabs />;
    case 'staff':
      return <StaffTabs />;
    default:
      return <ClientTabs />;
  }
};
```

### Screen Mappings by User Role

* **Unauthenticated:** `LoginScreen` (Email/Password entry)
* **Owner (Admin):**
  * **Dashboard tab** (Stat card summaries placeholder)
  * **Requests tab** (Admin request queue placeholder)
* **Staff:**
  * **Schedule tab** (Assigned active schedule listings placeholder)
* **Client:**
  * **Bookings tab** (Personal bookings list placeholder)

---

## 6. Placeholder Screens & Layout Definitions

Every screen placeholder will present a neat, styled view containing:
1. Clear screen identification text.
2. The user's active role.
3. Functional navigation/logout controls to verify routing loop stability.

---

## 7. Verification and Rollback Matrix

### 7.1 Verification Checklist
* Run standard TypeScript checks: `npx tsc --noEmit` from the `mobile/` directory to confirm zero typing issues.
* Verify dependency integrity: Ensure `package.json` contains no conflicting versions.
* Local compilation check: Run `npx expo export --platform web` to check if bundles compile without warnings.
* Run Metro bundler: Run `npx expo start --dry-run` to confirm Expo settings load correctly.

### 7.2 Rollback Strategy
Since this deployment strictly contains static, non-interfering native project configurations:
- **Command:** `git clean -fd && git checkout main`
- **Impact:** 100% immediate rollback with zero risk to the active production Web PWA.

---

## 8. AG Implementation Prompt — DO NOT RUN UNTIL MATTHEW APPROVES

```
AG — implement Release 8G: React Native / Expo Mobile Foundation Setup.

Please initialize the mobile codebase foundation under the /mobile folder. 
No backend modifications, web modifications, or AWS resource configurations are permitted.

=== 1. Initialize Expo Project ===
In the workspace root directory, run:
  npx -y create-expo-app@latest mobile --template blank-typescript --no-install

=== 2. Configure app.json ===
Update mobile/app.json to reflect the core system config:
{
  "expo": {
    "name": "Tog & Dogs Mobile Operations",
    "slug": "tog-and-dogs-mobile",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "userInterfaceStyle": "light",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#faf7f2"
    },
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.usmissionhero.toganddogs.mobile"
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#faf7f2"
      },
      "package": "com.usmissionhero.toganddogs.mobile"
    }
  }
}

=== 3. Install Pin-Locked Packages ===
Navigate to the mobile directory and run:
  npm install amazon-cognito-identity-js expo-secure-store @react-navigation/native @react-navigation/native-stack @react-navigation/bottom-tabs react-native-screens react-native-safe-area-context

=== 4. Configure TypeScript & Path Mappings ===
Verify mobile/tsconfig.json matches strict TypeScript rules.

=== 5. Implement API & Auth Layers ===
- Create mobile/src/api/config.ts containing API endpoint URLs (mirroring web configs).
- Create mobile/src/api/client.ts mirroring the REST payload request and header structures.
- Create mobile/src/auth/storage.ts implementing the secure store keychains.
- Create mobile/src/auth/cognito.ts for direct user pool authentication.
- Create mobile/src/auth/AuthContext.tsx managing active login states, JWT decoding, and active roles.

=== 6. Create Navigation Routes & Placeholder Screen Stubs ===
- Implement login screen components in mobile/src/screens/LoginScreen.tsx.
- Implement screen placeholders (Dashboard, RequestList, Schedule, Bookings).
- Implement role-based navigation logic in mobile/src/navigation/AppNavigator.tsx.
- Register navigation routers inside mobile/App.tsx.

=== 7. Validate Setup ===
Verify that compilation runs cleanly with zero TypeScript errors or bundler errors.

Return: Manifest of files created, npm dependency list, and compilation verification status.
```
