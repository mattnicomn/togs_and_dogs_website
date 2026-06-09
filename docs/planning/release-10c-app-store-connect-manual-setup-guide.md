# Release 10C: App Store Connect Manual Setup Guide

**Status:** Manual Guide (for Matthew to follow when ready)
**Priority:** Medium (unblocks TestFlight distribution)
**Action Required By:** Matthew (manual, in browser)
**Estimated Time:** 15-20 minutes

---

## 1. Purpose

This guide walks Matthew through creating the App Store Connect app record manually. Once this record exists, Kiro/AG can configure `eas.json` for automated TestFlight submissions.

**Do not perform these steps until Matthew is ready to enable TestFlight distribution.**

---

## 2. Prerequisites

| Requirement | Status |
|-------------|--------|
| Apple Developer Program membership active | ✅ Verify at developer.apple.com |
| Apple ID with admin/account holder role | ✅ |
| Bundle ID registered: `com.usmissionhero.toganddogs` | ✅ (confirmed by successful EAS builds) |
| Privacy Policy live at a public URL | ✅ `https://toganddogs.usmissionhero.com/privacy` |
| App icon ready (1024×1024 PNG) | ✅ `mobile/assets/icon.png` |

---

## 3. Step-by-Step: Create App Store Connect Record

### Step 1: Sign In

1. Open: **https://appstoreconnect.apple.com**
2. Sign in with your Apple Developer account (same Apple ID used for EAS builds)

### Step 2: Navigate to Apps

1. From the dashboard, click **"My Apps"** (or the grid icon → Apps)
2. You'll see a list of your existing apps (may be empty)

### Step 3: Create New App

1. Click the **"+"** button (top-left of the app list)
2. Select **"New App"**

### Step 4: Fill In Required Fields

| Field | Recommended Value | Notes |
|-------|-------------------|-------|
| **Platforms** | ✅ iOS | Check only iOS for now |
| **Name** | `Tog & Dogs` | This is what appears on the App Store. Check availability — if taken, try "Tog & Dogs Pet Care" or "Tog and Dogs" |
| **Primary Language** | English (U.S.) | |
| **Bundle ID** | Select `com.usmissionhero.toganddogs` from dropdown | Must match exactly. If not in dropdown, it may need explicit registration in the Developer Portal → Identifiers |
| **SKU** | `tog-and-dogs-ios-001` | Internal-only identifier. Any unique string works. |
| **Full Access** | ✅ (or limit to specific users) | Controls who in your team can manage this app |

3. Click **"Create"**

### Step 5: Record the App Store Connect App ID

After creation, navigate to:
- **App Information** (left sidebar) → look for **Apple ID** field
- This is a numeric ID (e.g., `6478291234`)
- **This is your `ascAppId`** — needed for `eas.json`

### Step 6: Record Your Team ID

1. Open: **https://developer.apple.com/account**
2. Look for **Membership** or **Membership Details**
3. Find **Team ID** (a 10-character alphanumeric string, e.g., `A1B2C3D4E5`)
- **This is your `appleTeamId`** — needed for `eas.json`

### Step 7: Note the App URL

Your app's App Store Connect URL will be:
```
https://appstoreconnect.apple.com/apps/<APPLE_ID>
```
Bookmark this for future reference.

---

## 4. Required Metadata (Fill In Placeholders)

You do NOT need to fill all of these immediately. TestFlight only requires a subset. But here's what Apple will eventually need:

### For TestFlight (Minimum Required)

| Field | Where in ASC | Value |
|-------|-------------|-------|
| App Name | Already set in Step 4 | "Tog & Dogs" |
| Privacy Policy URL | App Information → Privacy Policy URL | `https://toganddogs.usmissionhero.com/privacy` |
| Age Rating | App Information → Age Rating | Fill questionnaire (all "No" → 4+) |
| Category | App Information → Category | "Business" or "Lifestyle" |

### For External Beta Testing (Additional)

| Field | Where in ASC | Suggested Value |
|-------|-------------|-----------------|
| Beta App Description | TestFlight → App Info | "Pet care scheduling and operations management for Tog & Dogs staff and administrators." |
| What to Test | TestFlight → Test Information (per group) | "Log in with your staff or admin credentials. View your schedule, approve bookings, assign staff, and mark visits as completed." |
| Feedback Email | TestFlight → Test Information | `mbn@usmissionhero.com` |

### For Full App Store (Later — Not Now)

| Field | Value |
|-------|-------|
| Subtitle | "Pet Care Operations" (30 chars max) |
| Description | (Draft later — ~170 chars recommended) |
| Keywords | pet sitting, dog walking, pet care, scheduling, staff management |
| Support URL | `https://toganddogs.usmissionhero.com` |
| Marketing URL | (optional — leave blank for now) |
| Screenshots | (capture later — 6.5" iPhone required minimum) |

---

## 5. Privacy / Data Collection Setup

When Apple asks about data collection (App Privacy section):

### Select "Yes" for:

| Data Type | Category | Linked to Identity? | Used for Tracking? |
|-----------|----------|--------------------|--------------------|
| Contact Info → Email Address | App Functionality | Yes | No |
| Contact Info → Name | App Functionality | Yes | No |
| Contact Info → Phone Number | App Functionality | Yes | No |
| Contact Info → Physical Address | App Functionality | Yes | No |
| User Content (visit notes) | App Functionality | Yes | No |
| Identifiers (user ID) | App Functionality | Yes | No |

### Select "No" for everything else:
- No analytics collected
- No advertising data
- No location tracking
- No health data
- No financial data
- No diagnostics/crash reporting (yet)

---

## 6. Age Rating Questionnaire

Answer **"No"** to all questions:
- Cartoon/fantasy violence: No
- Realistic violence: No
- Sexual content: No
- Nudity: No
- Profanity: No
- Drugs: No
- Alcohol/tobacco: No
- Horror: No
- Gambling: No
- Contests: No
- Unrestricted web access: No

**Result: 4+ rating**

---

## 7. Export Compliance

Already handled in `app.json`:
```json
"infoPlist": {
  "ITSAppUsesNonExemptEncryption": false
}
```

When Apple asks during upload: the app uses HTTPS only (standard iOS networking). No custom encryption algorithms. Select "No" for non-exempt encryption.

---

## 8. What NOT to Do Yet

| ❌ Do NOT | Reason |
|-----------|--------|
| Upload a build | Requires `eas.json` submit config first |
| Submit for App Review | Not ready for public listing |
| Invite testers | Requires build uploaded + processed first |
| Set pricing | App is free; this is auto-set |
| Upload screenshots | Not needed for internal TestFlight; needed later for external |
| Fill in full App Store description | Only needed for public release |
| Enable in-app purchases | None exist |
| Create App Store Connect API keys | Only needed if automating submission without interactive auth |

---

## 9. Matthew Fill-In Section

**After completing the steps above, fill in these values and provide them to Kiro/ChatGPT:**

```
Apple Team ID: ___________________________
ASC App ID (numeric): ___________________________
App Store Connect URL: https://appstoreconnect.apple.com/apps/___________
Exact App Display Name: ___________________________
SKU Used: ___________________________
Support URL: https://toganddogs.usmissionhero.com
Privacy Policy URL: https://toganddogs.usmissionhero.com/privacy
Category Selected: ___________________________
Age Rating Confirmed: 4+ (Yes/No): ___________
Notes / Blockers: ___________________________
```

---

## 10. Post-Setup Handoff

Once Matthew has created the App Store Connect record and filled in the values above, provide them to Kiro/ChatGPT. The next steps will be:

1. **Kiro updates `mobile/eas.json`** with the `submit` section containing `ascAppId` and `appleTeamId`
2. **AG runs `eas build --profile production --platform ios`** to create a store-ready build
3. **AG runs `eas submit --platform ios`** to upload to TestFlight
4. **Matthew adds internal testers** (Matthew/Ernest) in App Store Connect
5. **When Ryan is ready:** Matthew creates external group, submits for beta review, invites Ryan

**None of these happen until Matthew explicitly approves each step.**

---

## 11. Troubleshooting

| Issue | Solution |
|-------|----------|
| Bundle ID not in dropdown | Register it at developer.apple.com → Certificates, Identifiers & Profiles → Identifiers → + → App IDs |
| App name "Tog & Dogs" already taken | Try "Tog & Dogs Pet Care", "Tog and Dogs", or "Tog & Dogs Operations" |
| "You don't have permission" | Verify your Apple ID has Account Holder or Admin role in the Developer Program |
| Can't find Team ID | developer.apple.com → Account → Membership (may require scrolling) |
| Can't find ASC App ID | App Store Connect → your app → App Information → look for "Apple ID" numeric field |

---

## 12. Timeline Expectation

| Action | Time |
|--------|------|
| Create ASC record | 5-10 minutes |
| Fill privacy/age/category | 5-10 minutes |
| Total setup | ~15-20 minutes |
| First build upload (future, after Kiro configures) | ~10 minutes (EAS build ~5 min + submit ~5 min) |
| Internal TestFlight available | ~15-30 min after upload (processing) |
| External beta review | ~24 hours after submission |
