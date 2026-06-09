# Release 10A: Mobile Distribution & Testing Access Plan

**Status:** Planning
**Priority:** Medium (enables broader testing when Ryan is ready)
**Risk to Production:** None (planning-only)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Distribution strategy decision document

---

## 1. Current State

| Item | Value |
|------|-------|
| Expo SDK | 54 |
| EAS Project | `@mattnicomn/tog-and-dogs` |
| EAS Project ID | `6b77d541-ec62-4950-8375-aef7d21c12ea` |
| iOS Bundle ID | `com.usmissionhero.toganddogs` |
| Latest iOS Preview Build | `58efd764-f170-4d6e-801c-7a1a7e76a2af` |
| Current Tester | Matthew (single device, internal/ad-hoc) |
| Ryan Status | Too busy to test currently |
| App Store Listing | Does not exist |
| TestFlight | Not configured |
| Apple Developer Account | Active (required for EAS iOS builds) |

### What the Mobile App Supports

- Staff login + Today/Upcoming schedule
- Booking details with care instructions
- Mark Completed + Visit Notes per day
- Admin login + Dashboard + Request List + Filters
- Staff assignment/reassignment
- Per-visit completion visibility
- Token refresh / session management
- iOS preview build (standalone, no Expo Go required)

---

## 2. Distribution Options Considered

### Option 1: Continue EAS Preview/Ad-Hoc Builds (Current)

| Aspect | Details |
|--------|---------|
| How it works | `eas build --profile preview --platform ios` → install link/QR |
| Who can install | Only devices with registered UDIDs (via `eas device:create`) |
| Max devices | 100 per Apple Developer account per year |
| Review required | ❌ No Apple review |
| Expiration | Build is valid until provisioning profile expires (~1 year) |
| Good for | Matthew-only testing, immediate iteration |
| Limitation | Each new tester must register their device UDID first |

### Option 2: TestFlight Internal Testing

| Aspect | Details |
|--------|---------|
| How it works | Upload build to App Store Connect → invite internal testers |
| Who can install | Apple Developer team members (up to 100) |
| Max testers | 100 internal testers |
| Review required | ❌ No Apple review for internal testers |
| Expiration | 90 days per build |
| Good for | Matthew + Ryan + 1-2 trusted team members |
| Limitation | Testers must be added to the Apple Developer team as App Store Connect users |

### Option 3: TestFlight External Testing

| Aspect | Details |
|--------|---------|
| How it works | Upload build → create beta group → Apple reviews → invite external testers |
| Who can install | Anyone with an invite link (up to 10,000) |
| Max testers | 10,000 external testers |
| Review required | ✅ Yes — Apple Beta App Review (usually < 24 hours) |
| Expiration | 90 days per build |
| Good for | Ryan + staff + any client testers in the future |
| Limitation | Requires passing Apple's beta review (basic — checks for crashes, placeholders) |

### Option 4: Apple Unlisted App Store

| Aspect | Details |
|--------|---------|
| How it works | Submit to App Store but with "unlisted" distribution — only accessible via direct link |
| Who can install | Anyone with the link (no search discoverability) |
| Review required | ✅ Full App Store review |
| Expiration | None (permanent install until removed) |
| Good for | Semi-private distribution to staff/clients without public listing |
| Limitation | Full review process; must meet all App Store guidelines |

### Option 5: Public App Store

| Aspect | Details |
|--------|---------|
| How it works | Full public listing in the Apple App Store |
| Who can install | Anyone searching or with a link |
| Review required | ✅ Full App Store review |
| Good for | Client-facing distribution at scale |
| Limitation | Must meet all guidelines; requires screenshots, descriptions, privacy policy |

### Option 6: Apple Business Manager / Custom Apps

| Aspect | Details |
|--------|---------|
| How it works | Distribute via Apple Business Manager to a specific organization |
| Who can install | Employees/contractors of the enrolled organization |
| Review required | ✅ Yes |
| Good for | Enterprise/internal business apps |
| Limitation | Requires Apple Business Manager enrollment ($0 but bureaucratic); overkill for 2-5 users |

---

## 3. Decision Matrix

| Criteria | EAS Ad-Hoc | TF Internal | TF External | Unlisted | Public |
|----------|-----------|-------------|-------------|----------|--------|
| No Apple review | ✅ | ✅ | ❌ | ❌ | ❌ |
| Ryan can install easily | ⚠️ (UDID reg) | ✅ | ✅ | ✅ | ✅ |
| No App Store Connect setup | ✅ | ❌ | ❌ | ❌ | ❌ |
| Fast iteration (< 5 min) | ✅ | ⚠️ (upload step) | ⚠️ | ❌ | ❌ |
| Professional install UX | ❌ | ✅ | ✅ | ✅ | ✅ |
| Can add testers without device UDID | ❌ | ✅ | ✅ | ✅ | ✅ |
| Suitable for current phase | ✅ | ✅ | Future | Future | Future |

---

## 4. Recommendation: Staged Approach

```
NOW (current):
  → Continue EAS preview/ad-hoc for Matthew's solo testing
  → Zero additional setup needed
  → Fastest iteration cycle

WHEN RYAN IS READY:
  → Set up TestFlight External Testing
  → Upload a build to App Store Connect
  → Submit for Apple Beta Review (~24 hours, one-time for first build)
  → Create a "Business Testers" external group
  → Invite Ryan by email — he installs via TestFlight app
  → 90-day build validity — rebuild monthly or as needed

WHEN 1-2 ADDITIONAL TESTERS NEEDED:
  → Add to the same TestFlight External group
  → No additional Apple review needed for same build
  → Invite testers by email — they install via TestFlight link

WHEN CLIENT-FACING MOBILE IS READY:
  → Unlisted or Public App Store submission
  → Full review, screenshots, description, privacy policy already exists
```

### Rationale

- **EAS ad-hoc is perfect for now** — Matthew is the only tester, and iteration speed matters more than install elegance.
- **TestFlight Internal is the right next step** — it removes the UDID friction for Ryan and requires zero Apple review.
- **TestFlight External defers Apple review** until the app is stable enough for non-technical testers.
- **Public App Store is premature** — client screens aren't built yet, and the app only serves admin/staff currently.

---

## 5. Tester Personas

| Persona | When | Distribution Method | Apple Account Needed? |
|---------|------|--------------------|-----------------------|
| **Matthew** (developer/owner) | Now | EAS ad-hoc build → TestFlight Internal | Already has Apple Developer account |
| **Ernest** (trusted dev/support) | When added | TestFlight Internal | Needs Apple ID + App Store Connect user role |
| **Ryan** (business owner) | When available | TestFlight External | Needs Apple ID + TestFlight invite email |
| **Optional Tester 1** (staff) | After Ryan validates | TestFlight External | Needs Apple ID + TestFlight invite email |
| **Optional Tester 2** (client) | Future | TestFlight External or Unlisted Store | Needs Apple ID |

### Internal vs External TestFlight — Clarification

- **TestFlight Internal** is for users who have an **App Store Connect account** (developer team members like Matthew and Ernest). Up to 100 users, no Apple review required.
- **TestFlight External** is for users who only need an **Apple ID** (business testers like Ryan, staff, optional testers). Up to 10,000 users, but the first build submitted to an external group requires Apple Beta App Review (~24 hours).
- **Ryan should be categorized as an External tester** unless he's intentionally added as an App Store Connect user. External testing is the simpler, lower-overhead path for a business owner who just needs to install and test the app.

---

## 6. Prerequisites for TestFlight (Not Approved Yet)

### App Store Connect Setup Needed

| Step | Status | Blocker? |
|------|--------|----------|
| Apple Developer account active | ✅ Already active | No |
| App Store Connect app record created | ❌ Not done | Blocking |
| Bundle ID registered in Apple Developer portal | ✅ `com.usmissionhero.toganddogs` | No |
| App name reserved in ASC | ❌ Not done | Blocking |
| Privacy policy URL configured | ✅ `toganddogs.usmissionhero.com/privacy` | No |
| Primary category selected | ❌ Not done | Blocking (choose "Business" or "Lifestyle") |
| App icon uploaded to ASC | ❌ Not done | Blocking |
| Build uploaded via EAS Submit | ❌ Not done | — |
| Ryan's Apple ID added as internal tester | ❌ Not done | — |

### EAS Submit Configuration

Add to `mobile/eas.json`:
```json
"submit": {
  "production": {
    "ios": {
      "appleId": "MATTHEW_APPLE_ID",
      "ascAppId": "APP_STORE_CONNECT_APP_ID",
      "appleTeamId": "TEAM_ID"
    }
  }
}
```

---

## 7. Step-by-Step Future Implementation Checklist

**⚠️ NOT APPROVED YET — for reference only**

### Phase A: TestFlight Setup + External Testing (for Ryan)

1. [ ] Log into App Store Connect (appstoreconnect.apple.com)
2. [ ] Create new app: name "Tog & Dogs", bundle ID `com.usmissionhero.toganddogs`
3. [ ] Set primary language, category (Business/Lifestyle)
4. [ ] Set privacy policy URL: `https://toganddogs.usmissionhero.com/privacy`
5. [ ] Build the app: `eas build --profile production --platform ios`
6. [ ] Submit to TestFlight: `eas submit --platform ios`
7. [ ] Wait for processing (~5-15 minutes)
8. [ ] Create "Business Testers" external testing group
9. [ ] Add test information (description of what to test, feedback email)
10. [ ] Submit build for Apple Beta App Review (~24 hours)
11. [ ] After approval: invite Ryan by email to the external group
12. [ ] Ryan receives TestFlight invite → installs TestFlight app → installs Tog & Dogs

### Phase B: Additional External Testers

13. [ ] Add new testers to existing "Business Testers" group by email
14. [ ] No additional Apple review needed (same approved build)
15. [ ] Testers receive invite → install via TestFlight

---

## 8. Approval Gates

| Gate | What It Controls | Who Approves |
|------|-----------------|--------------|
| **Gate 1** | Create App Store Connect record | Matthew |
| **Gate 2** | Build + upload first TestFlight build | Matthew |
| **Gate 3** | Invite Ryan as internal tester | Matthew (when Ryan is ready) |
| **Gate 4** | Submit for external beta review | Matthew (when additional testers needed) |
| **Gate 5** | Public App Store submission | Matthew + Ryan (when client app is ready) |

No gate should be crossed without explicit approval.

---

## 9. Risks and Open Questions

| Risk/Question | Impact | Resolution |
|---------------|--------|-----------|
| Ryan's Apple ID unknown | Blocks TestFlight invite | Ask Ryan for Apple ID when ready |
| App name "Tog & Dogs" may be taken on App Store | Blocks ASC record creation | Check availability; alternatives: "Tog and Dogs", "Tog & Dogs Pet Care" |
| 90-day TestFlight expiration | Tester builds stop working | Rebuild + re-upload monthly (EAS makes this trivial) |
| Apple Beta Review rejection | Blocks external testing | Unlikely for functional app; ensure no placeholder screens remain |
| Push notifications not implemented | No alert delivery to TestFlight testers | Not blocking for workflow testing; add later |
| App only serves admin/staff roles currently | Clients can't do anything useful | Fine — TestFlight is for internal validation, not client rollout |

---

## 10. Validation Checklist (For When Matthew Approves Moving Forward)

| # | Check | Expected |
|---|-------|----------|
| 1 | App Store Connect record created | App visible in ASC dashboard |
| 2 | Bundle ID matches EAS config | `com.usmissionhero.toganddogs` |
| 3 | Privacy policy URL accessible | Returns 200 with content |
| 4 | EAS production build succeeds | No build errors |
| 5 | Build uploaded to TestFlight | Visible in ASC Builds tab |
| 6 | Processing completes | Build available for testing |
| 7 | Internal tester receives invite | Email delivered |
| 8 | Tester can install via TestFlight | App installs and launches |
| 9 | Login works on TestFlight build | Cognito auth succeeds |
| 10 | Schedule/bookings visible | Real data loads |

---

## 11. What This Planning Document Does NOT Authorize

- ❌ Creating the App Store Connect record
- ❌ Building or uploading any new iOS builds
- ❌ Submitting to Apple for any review
- ❌ Inviting any TestFlight testers
- ❌ Modifying `eas.json` or `app.json`
- ❌ Modifying any code
- ❌ Changing any AWS/production resources
- ❌ Pushing anything to origin/main without approval

This is a decision document only. Implementation requires separate explicit approval per gate.

---

## 12. Summary

**For now:** Continue EAS ad-hoc preview builds for Matthew. Zero additional work needed.

**When Ryan is ready:** Set up TestFlight Internal (~30 min of App Store Connect configuration + one build upload). Ryan installs via TestFlight app with no UDID friction.

**When more testers are needed:** TestFlight External with Apple Beta Review (~24 hour approval). Invite by email.

**Public App Store:** Only after client-facing screens are built and Ryan has validated the admin/staff workflow in production.
