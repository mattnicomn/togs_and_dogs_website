# Mobile App Strategy: Tog & Dogs React Native

## Overview
Build a React Native mobile app (iOS + Android) that serves ALL user roles — clients, staff, and admin/owner. The mobile app will be the primary interface for daily operations, with the web app retained as a secondary/desktop admin tool.

## Key Decision: Full-Featured Mobile App

**All roles use mobile as primary:**
| Role | Mobile Use Case |
|------|----------------|
| Owner (Ryan) | Manage bookings, assign staff, approve requests, view schedule — on the go |
| Admin/Staff | View assignments, check care instructions, log visit notes, manage schedule |
| Client | Request visits, view bookings, update pet info, cancel visits |

**Web app remains as:**
- Desktop fallback for complex admin tasks (bulk operations, data export, Terraform/infra)
- Full-screen scheduling view (MasterScheduler)
- Detailed reporting/analytics (future)

## Architecture

### Monorepo Structure
```
togs_and_dogs_website/
├── web/                    ← React web app (desktop admin, scheduling)
├── mobile/                 ← React Native app (primary for all roles)
│   ├── src/
│   │   ├── screens/       ← Role-based screens
│   │   ├── components/    ← Shared UI components
│   │   ├── api/           ← API client (mirrors web/src/api/)
│   │   ├── auth/          ← Cognito auth (same user pool)
│   │   └── navigation/    ← Role-based navigation
│   ├── ios/
│   ├── android/
│   └── app.json           ← Expo config
├── src/backend/            ← Shared Lambda backend (serves both)
├── infra/                  ← Shared Terraform infrastructure
├── docs/                   ← Shared documentation
└── tests/                  ← Shared backend tests
```

### Shared Backend
- Same API Gateway endpoints
- Same Cognito user pool (same groups: owner, admin, staff, client)
- Same DynamoDB tables
- Same notification system (add push notifications alongside email)
- No backend changes needed for mobile — API is already role-aware

### Technology Stack
| Component | Choice | Reason |
|-----------|--------|--------|
| Framework | React Native + Expo | Fastest path to App Store + Play Store |
| Auth | AWS Amplify / amazon-cognito-identity-js | Same library as web, same user pool |
| Navigation | React Navigation | Standard for RN, supports role-based routing |
| State | React Context or Zustand | Lightweight, sufficient for this scale |
| Push Notifications | Expo Notifications + Firebase/APNs | Complement email notifications |
| Build/Deploy | EAS Build (Expo Application Services) | Handles iOS/Android builds without local Xcode/Android Studio |

## Mobile App Screens by Role

### Client Screens
| Screen | Features |
|--------|----------|
| My Bookings | View upcoming/past visits, status, assigned sitter |
| Request Care | Service type, date, pet selection, notes |
| My Pets | View/edit pet profiles, care instructions |
| Profile | Contact info, notification preferences |
| Cancel Visit | Request cancellation with reason |

### Staff Screens
| Screen | Features |
|--------|----------|
| My Schedule | Today's visits, upcoming assignments |
| Visit Details | Client info, pet care instructions, access codes, notes |
| Visit Notes | Log visit completion notes, photos |
| Availability | Set available/unavailable days (future) |

### Admin/Owner Screens
| Screen | Features |
|--------|----------|
| Dashboard | Stats cards (intake queue, needs assignment, scheduled, alerts) |
| Request List | All requests with status filters, quick actions |
| Approve/Decline | Swipe or tap to approve/decline requests |
| Assign Staff | Select worker for approved bookings |
| Client Management | View/create/edit client profiles |
| Staff Management | View/manage staff, assignments |
| New Visit | Create booking for offline client (same as web modal) |
| Notifications | Push notification history |
| Google Calendar Status | Connection health indicator |

## Implementation Phases

### Phase 1: Foundation (~2-3 weeks)
- Expo project setup in `mobile/`
- Cognito auth integration (login, session, role detection)
- Role-based navigation (client vs staff vs admin)
- API client layer (mirrors `web/src/api/client.js`)
- Basic screens: Login, Dashboard shell, My Bookings

### Phase 2: Client Experience (~2 weeks)
- My Bookings screen (view visits, status)
- Request Care screen (service type, date, pets)
- My Pets screen (view pet profiles)
- Cancel Visit flow
- Push notification setup (Expo + backend integration)

### Phase 3: Staff Experience (~1-2 weeks)
- My Schedule screen (today's visits)
- Visit Details screen (care instructions, client info)
- Visit Notes / completion logging
- Push notifications for new assignments

### Phase 4: Admin/Owner Experience (~2-3 weeks)
- Dashboard with stats
- Request List with filters and quick actions
- Approve/Decline flow
- Staff Assignment
- New Visit creation (offline client booking)
- Client/Staff Management

### Phase 5: App Store Submission (~1 week)
- App icons, splash screens, screenshots
- Privacy policy, terms of service
- Apple App Store submission
- Google Play Store submission
- TestFlight / internal testing track

## Push Notification Strategy

### Events That Should Push
| Event | Recipient | Push? | Email? |
|-------|-----------|-------|--------|
| New request received | Admin | ✅ | ✅ |
| Request approved | Client | ✅ | ✅ |
| Staff assigned | Staff | ✅ | ✅ |
| Visit scheduled | Client | ✅ | ✅ |
| Visit cancelled | Client + Staff + Admin | ✅ | ✅ |
| Visit reminder (1 day before) | Client + Staff | ✅ | ❌ |
| Visit completed | Client | ✅ | ❌ |

### Backend Changes for Push
- Store device tokens (FCM/APNs) on user profiles
- Add push notification provider alongside Postmark email
- `notify_event()` dispatches to both email + push based on user preferences

## What Stays Web-Only (For Now)

| Feature | Reason |
|---------|--------|
| MasterScheduler (full calendar view) | Complex drag-drop UI, better on desktop |
| Data Export (Excel) | File handling easier on desktop |
| Terraform/infrastructure management | Developer tool, not user-facing |
| Bulk operations (bulk purge, bulk status) | Risky on mobile, better with full screen |
| Google Calendar OAuth flow | Browser redirect required |

## Dependencies / Prerequisites

Before starting mobile development:
- [x] Backend API is stable and production-validated
- [x] Cognito auth works for all roles
- [x] Notification system is complete (email)
- [ ] Complete remaining 7B tasks (web polish)
- [ ] Push notification backend support (new)
- [ ] Device token storage schema (new)

## Risks

| Risk | Mitigation |
|------|-----------|
| App Store rejection | Follow Apple/Google guidelines from day 1 |
| Expo limitations for native features | Expo supports push, camera, location — sufficient for this app |
| Maintaining two UIs (web + mobile) | Shared API means no backend duplication; UI is the only divergence |
| Auth token refresh on mobile | Cognito SDK handles this; same pattern as web |

## Success Criteria

- [ ] All roles can perform their primary workflows on mobile
- [ ] Push notifications deliver reliably
- [ ] App Store + Play Store approved
- [ ] Staff/owner prefer mobile over web for daily operations
- [ ] Client can book and manage visits without calling Ryan
