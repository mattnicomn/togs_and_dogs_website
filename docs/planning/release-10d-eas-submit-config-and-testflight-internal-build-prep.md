# Release 10D: EAS Submit Configuration & TestFlight Internal Build Prep

**Status:** Config Finalized (Gate C Approved)
**Priority:** High (unblocks TestFlight distribution)
**Risk to Production:** None (config documentation + proposed change only)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** Document EAS submit config; apply only with explicit approval

---

## 1. App Store Connect Setup Summary

### Values Confirmed from Matthew's Manual Setup

| Field | Value | Status |
|-------|-------|--------|
| **Apple Team ID** | `2RA84Y5HZ3` | ✅ Confirmed |
| **Bundle ID** | `com.usmissionhero.toganddogs` | ✅ Matches app.json |
| **App Name (ASC)** | `toganddogs_app_1` | ⚠️ Placeholder — can rename before public release |
| **SKU** | `06092026` | ✅ |
| **Primary Language** | English (U.S.) | ✅ |
| **User Access** | Full Access | ✅ |
| **Platform** | iOS | ✅ |
| **ASC App ID (numeric)** | `6778488478` | ✅ Confirmed |
| **Privacy Policy URL** | `https://toganddogs.usmissionhero.com/privacy` | ✅ (set in ASC) |
| **Support URL** | `https://toganddogs.usmissionhero.com` | ✅ |

### Note on App Name

`toganddogs_app_1` is a placeholder name. This can be changed in App Store Connect → App Information → Name at any time before public App Store submission. For TestFlight testing, the name doesn't matter to testers (they see whatever is set).

### Note on "Submitted"

Matthew noted he "submitted for the app" — this likely means the App Store Connect record was successfully created. Apple will NOT process a review until a build is uploaded, so no action is triggered by record creation alone.

---

## 2. Confirmed Value: ASC App ID

**The numeric ASC App ID has been confirmed and added to the submit configuration.**

* **ASC App ID (numeric)**: `6778488478` (Provided by Matthew)

---

## 3. Applied eas.json Submit Configuration

**✅ CONFIGURATION APPLIED — Approved by Matthew**

Add a `submit` section to `mobile/eas.json`:

```json
{
  "cli": {
    "version": ">= 16.0.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal",
      "ios": {
        "simulator": false
      }
    },
    "preview": {
      "distribution": "internal"
    },
    "production": {
      "autoIncrement": true
    }
  },
  "submit": {
    "production": {
      "ios": {
        "appleId": "mattnicomn10@gmail.com",
        "ascAppId": "6778488478",
        "appleTeamId": "2RA84Y5HZ3"
      }
    }
  }
}
```

### Fields Explained

| Field | Value | Purpose |
|-------|-------|---------|
| `appleId` | Matthew's Apple ID email | Authentication for submission |
| `ascAppId` | **TBD** (numeric from ASC) | Identifies which App Store Connect app to upload to |
| `appleTeamId` | `2RA84Y5HZ3` | Identifies the Apple Developer team |

### Apple ID Note

The `appleId` field is the email associated with the Apple Developer account. If Matthew uses a different email for Apple (not `mattnicomn10@gmail.com`), update accordingly.

---

## 4. Internal TestFlight Build Upload Sequence

**⚠️ NOT APPROVED YET — For reference only**

Once `eas.json` is configured and Matthew approves:

### Step 1: Build Production Binary
```bash
cd mobile
npx eas build --profile production --platform ios
```
- Builds in EAS cloud (~5-10 minutes)
- Produces a signed `.ipa` file
- Uses `autoIncrement: true` to bump build number

### Step 2: Submit to App Store Connect
```bash
cd mobile
npx eas submit --platform ios
```
- Uploads the latest production build to TestFlight
- May prompt for Apple ID authentication (first time)
- If Apple requires an App Store Connect API key instead of interactive auth, will need additional setup

### Step 3: Wait for Processing
- Apple processes the build (~5-30 minutes)
- Build appears in App Store Connect → TestFlight → Builds tab
- Status goes from "Processing" → "Ready to Test"

### Step 4: Add Internal Testers
- In App Store Connect → TestFlight → Internal Testing
- Add Matthew (and Ernest if applicable) as internal testers
- They must be App Store Connect users with at least "App Manager" or "Developer" role
- Testers receive an email invitation to install via TestFlight

### Step 5: Install and Verify
- Open TestFlight app on iPhone
- Accept invite → install "toganddogs_app_1"
- Launch → verify login, schedule, actions all work

---

## 5. Authentication for EAS Submit

EAS Submit needs to authenticate with Apple. Two options:

### Option A: Interactive Login (Simpler, Recommended First)

When `eas submit` runs, it may prompt for:
- Apple ID email
- Apple ID password
- Two-factor authentication code

This works for manual submissions but requires interactive terminal access.

### Option B: App Store Connect API Key (Better for Automation)

Create an API key in App Store Connect → Users and Access → Keys:
- Download the `.p8` file
- Note the Key ID and Issuer ID
- Configure in `eas.json` or via environment variables

**Recommendation:** Start with Option A (interactive). Switch to Option B only if automation is needed later.

---

## 6. Config Gaps Identified

| Gap | Severity | Resolution |
|-----|----------|-----------|
| `ascAppId` not yet provided | Resolved | ✅ Confirmed App ID: `6778488478` |
| `appleId` email unconfirmed | Resolved | ✅ Confirmed Apple ID: `mattnicomn10@gmail.com` |
| No `submit` section in `eas.json` | Resolved | ✅ Submit configuration applied to mobile/eas.json |
| App name is placeholder | ⚠️ Low | Can rename in ASC before public release |
| No screenshots uploaded | Not blocking for internal TF | Needed for external beta review only |
| No beta description written | Not blocking for internal TF | Needed for external testers only |

---

## 7. Approval Gates

| Gate | Action | Status |
|------|--------|--------|
| **Gate A** | Matthew provides ASC App ID | ✅ Completed |
| **Gate B** | Matthew confirms Apple ID email for eas.json | ✅ Completed |
| **Gate C** | Matthew approves `eas.json` submit config change | ✅ Completed |
| **Gate D** | Matthew approves first production build | ⏳ Pending |
| **Gate E** | Matthew approves first TestFlight submission | ⏳ Pending |
| **Gate F** | Matthew adds himself as internal tester | ⏳ Pending |

---

## 8. Risks and Open Questions

| Risk / Question | Impact | Resolution |
|----------------|--------|-----------|
| ASC App ID not yet available | Blocks eas.json config | Matthew checks App Information page |
| EAS Submit auth fails (2FA, token issue) | Blocks upload | Try interactive first; API key fallback |
| Build fails in production profile | Blocks upload | Same code passed preview; low risk |
| Apple processes build slowly | Delays testing | Usually < 30 min; just wait |
| Placeholder app name confuses testers | Low | Ryan won't test until name is cleaned up; internal testers understand |
| First-time submit credential caching | May require re-auth | Normal EAS behavior |

---

## 9. Rollback / Cleanup

- If `eas.json` is updated and something breaks: revert the one-line submit section change
- If a build is uploaded to TestFlight incorrectly: it can be expired/removed in ASC
- If testers are added prematurely: they can be removed from the group in ASC
- No production backend, web, or mobile app behavior changes — only distribution channel

---

## 10. Next Steps (After Matthew Provides ASC App ID)

1. Matthew provides the numeric ASC App ID
2. Matthew confirms Apple ID email for authentication
3. Kiro proposes exact `eas.json` diff for approval
4. Matthew approves → Kiro/AG applies the config change
5. Matthew approves → AG runs `eas build --profile production --platform ios`
6. Matthew approves → AG runs `eas submit --platform ios`
7. Matthew adds internal testers in App Store Connect
8. Testers install and validate via TestFlight

---

## 11. What This Document Does NOT Authorize

- ❌ Modifying `eas.json`
- ❌ Building any iOS binaries
- ❌ Submitting anything to Apple
- ❌ Adding testers to TestFlight
- ❌ Changing App Store Connect metadata
- ❌ Modifying mobile code
- ❌ Any AWS/production changes

This is a planning document. Each action requires separate explicit approval.
