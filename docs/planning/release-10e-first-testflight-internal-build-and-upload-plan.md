# Release 10E: First TestFlight Internal Build & Upload Plan

**Status:** Planning
**Priority:** High (next step to get the app on TestFlight)
**Risk to Production:** None (build + upload only, no backend/web changes)
**Terraform Required:** No
**Backend Changes:** None
**Scope:** EAS production build + upload to App Store Connect TestFlight

---

## 1. Current State Summary

| Item | Value | Status |
|------|-------|--------|
| EAS Project | `@mattnicomn/tog-and-dogs` | ✅ Linked |
| EAS Project ID | `6b77d541-ec62-4950-8375-aef7d21c12ea` | ✅ |
| iOS Bundle ID | `com.usmissionhero.toganddogs` | ✅ |
| Apple Team ID | `2RA84Y5HZ3` | ✅ In eas.json |
| ASC App ID | `6778488478` | ✅ In eas.json |
| Apple ID (auth) | `mattnicomn10@gmail.com` | ✅ In eas.json |
| App Name in ASC | `toganddogs_app_1` | ✅ (placeholder) |
| `eas.json` submit section | Configured | ✅ (Release 10D) |
| `app.json` production-ready | Version 1.0.0, buildNumber 1 | ✅ |
| Encryption exemption | `ITSAppUsesNonExemptEncryption: false` | ✅ |
| Latest validated preview build | `58efd764-f170-4d6e-801c-7a1a7e76a2af` | ✅ |
| **Production build uploaded to TestFlight** | ❌ Not done | **This release** |
| **Internal testers added** | ❌ Not done | After upload |

---

## 2. Preconditions Before Build

### Must Be True

| # | Precondition | Status |
|---|-------------|--------|
| 1 | `mobile/eas.json` has production build profile | ✅ |
| 2 | `mobile/eas.json` has submit section with ascAppId + appleTeamId | ✅ |
| 3 | `mobile/app.json` has `ios.bundleIdentifier` matching ASC record | ✅ |
| 4 | `mobile/app.json` has `version` and `ios.buildNumber` set | ✅ (1.0.0 / 1) |
| 5 | App Store Connect app record exists | ✅ |
| 6 | Apple Developer account is active | ✅ |
| 7 | EAS CLI installed and logged in | Verify at runtime |
| 8 | Working tree is clean (no uncommitted changes) | Verify at runtime |
| 9 | TypeScript compiles cleanly | Verify at runtime |

### Verify Before Running

```bash
cd mobile
git status              # Must be clean
npx tsc --noEmit        # Must pass 0 errors
npx eas whoami          # Must show logged-in Expo account
```

---

## 3. Apple / App Store Connect Readiness

| Requirement | Status | Notes |
|-------------|--------|-------|
| App record exists in ASC | ✅ | `toganddogs_app_1` |
| Bundle ID matches | ✅ | `com.usmissionhero.toganddogs` |
| Privacy Policy URL set | Should verify | Set during ASC creation |
| Age Rating configured | Should verify | Should be 4+ per 10C guide |
| Export Compliance declared in app.json | ✅ | `ITSAppUsesNonExemptEncryption: false` |
| Privacy Nutrition Label filled | Should verify | Answers documented in 10B |

If any ASC metadata is missing, Apple will warn during processing but won't block TestFlight internal testing.

---

## 4. EAS Readiness

| Requirement | Status | Notes |
|-------------|--------|-------|
| EAS CLI version ≥ 16.0.0 | Verify | `npx eas --version` |
| Expo account logged in | Verify | `npx eas whoami` |
| Apple credentials accessible | Verify at submit time | May prompt for Apple ID + 2FA |
| Production build profile configured | ✅ | `autoIncrement: true` |
| Submit profile configured | ✅ | appleId, ascAppId, appleTeamId |

---

## 5. Build + Upload Command Sequence

### ⚠️ NOT APPROVED YET — For reference only

#### Step 1: Verify Environment

```bash
cd mobile
git status                    # Clean working tree
npx tsc --noEmit              # TypeScript passes
npx eas whoami                # Logged in as mattnicomn
npx eas --version             # ≥ 16.0.0
```

#### Step 2: Production Build

```bash
cd mobile
npx eas build --profile production --platform ios
```

**What happens:**
- EAS builds the app in Expo's cloud infrastructure
- Uses Apple distribution certificate (EAS manages this automatically)
- Produces a signed `.ipa` file ready for App Store / TestFlight
- `autoIncrement: true` bumps `ios.buildNumber` (1 → 2, etc.)
- Takes approximately 5-15 minutes
- Returns a build URL/ID on success

**Expected output:**
```
✔ Build finished
  Platform:      iOS
  Profile:       production
  Distribution:  store
  Build ID:      xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
  URL:           https://expo.dev/accounts/mattnicomn/projects/tog-and-dogs/builds/xxxxx
```

#### Step 3: Submit to App Store Connect

```bash
cd mobile
npx eas submit --platform ios
```

**What happens:**
- Uploads the latest production build to App Store Connect
- May prompt for Apple ID authentication (email + password + 2FA code)
- First-time submission may require accepting terms in App Store Connect
- Takes approximately 2-5 minutes for upload
- After upload, Apple processes the build (~5-30 minutes)

**Alternative (specify build explicitly):**
```bash
npx eas submit --platform ios --id BUILD_ID_FROM_STEP_2
```

**Expected output:**
```
✔ Submitted to Apple App Store Connect
  App Store Connect: https://appstoreconnect.apple.com/apps/6778488478/testflight/ios
```

#### Step 4: Verify in App Store Connect

1. Open: https://appstoreconnect.apple.com/apps/6778488478/testflight/ios
2. Navigate to **TestFlight** → **Builds** tab
3. Confirm the build appears (may show "Processing" initially)
4. Wait until status changes to **"Ready to Test"** (~5-30 minutes)

---

## 6. After Build Appears in TestFlight

### Adding Internal Testers (Gate C)

1. In App Store Connect → TestFlight → **Internal Testing**
2. Click **"+"** to create a new group (e.g., "Development Team")
3. Add Matthew's Apple ID as an internal tester
   - Must be an App Store Connect user with Developer/App Manager role
4. Tester receives email → opens TestFlight app → installs the build

### Verifying the TestFlight Build

| # | Check | Expected |
|---|-------|----------|
| 1 | Build status in ASC | "Ready to Test" |
| 2 | Build number | 2 (auto-incremented from 1) |
| 3 | Version | 1.0.0 |
| 4 | Encryption | "No" (from infoPlist declaration) |
| 5 | Install via TestFlight | App launches to login screen |
| 6 | Login works | Cognito auth succeeds |
| 7 | Dashboard loads | Real data from production API |
| 8 | Schedule visible | Today/Upcoming visits |
| 9 | Mark Completed works | Visit notes saved |

---

## 7. Potential Issues and Troubleshooting

| Issue | Cause | Resolution |
|-------|-------|-----------|
| "Invalid credentials" during submit | Wrong Apple ID or password | Re-enter credentials; verify 2FA |
| "No matching provisioning profile" | EAS credential management issue | Run `eas credentials` to check/reset |
| Build fails with code signing error | Certificate or profile mismatch | EAS usually auto-manages; check `eas credentials` |
| "App record not found" | ascAppId mismatch | Verify `6778488478` matches ASC |
| Processing stuck | Apple-side delay | Wait up to 1 hour; check Apple System Status |
| "Missing compliance information" | Export compliance not declared | Already handled in app.json; if asked, select "No" |
| "Missing privacy information" | Nutrition label incomplete | Complete in ASC → App Privacy section |
| Build uploaded but "Missing Metadata" | ASC requires privacy/age/category | Fill remaining metadata in ASC (non-blocking for internal TF) |

---

## 8. Rollback / Cleanup

| Scenario | Action |
|----------|--------|
| Build fails | No cleanup needed — nothing uploaded |
| Submit fails | No cleanup needed — build exists on EAS but not in ASC |
| Build uploaded but wrong | Expire the build in ASC → TestFlight → Builds → select → "Expire Build" |
| Testers added prematurely | Remove from group in ASC → TestFlight → group → remove tester |
| Want to revert eas.json | `git revert` the 10D commit — but not recommended unless wrong values |

No backend, web, or production data is affected by any of these steps.

---

## 9. Risks and Open Questions

| Risk / Question | Impact | Resolution |
|----------------|--------|-----------|
| Apple ID 2FA prompt during submit | Requires interactive terminal | AG needs Matthew present or use App Store Connect API key |
| First submission may require Terms acceptance in ASC | Blocks upload until accepted | Matthew accepts in browser |
| `autoIncrement` changes buildNumber in app.json | Creates a git diff | Commit the incremented buildNumber after successful build |
| Build uses current `main` branch code | Must be clean and validated | Verify `git status` + `tsc` before building |
| Apple processing time varies | 5 min to 1 hour | Just wait; no action needed |

---

## 10. Approval Gates

| Gate | Action | Approver | Status |
|------|--------|----------|--------|
| **Gate A** | Run `eas build --profile production --platform ios` | Matthew | ⏳ Pending |
| **Gate B** | Run `eas submit --platform ios` | Matthew | ⏳ Pending |
| **Gate C** | Add Matthew as internal tester in ASC | Matthew | ⏳ Pending |
| **Gate D** | Create external group + submit for beta review (for Ryan) | Matthew | Future |

**Gates are sequential.** Do not proceed to B without A succeeding. Do not proceed to C without B succeeding.

---

## 11. AG Execution Prompt Draft

**⚠️ Matthew: Copy this to AG only after approving Gates A and B**

```
AG — execute Release 10E: First TestFlight Production Build + Upload.

This creates a production iOS build and uploads it to App Store Connect for TestFlight.
Do NOT add testers. Do NOT submit for App Store review.

=== Precondition Checks ===

cd mobile
git status              # Must be clean
npx tsc --noEmit        # Must pass
npx eas whoami          # Must be logged in
npx eas --version       # Must be >= 16.0.0

Report: All preconditions pass? If any fail, STOP and report.

=== Step 1: Production Build ===

cd mobile
npx eas build --profile production --platform ios

Wait for build to complete (~5-15 minutes).
Report: Build ID, build URL, success/failure.

=== Step 2: Submit to TestFlight ===

cd mobile
npx eas submit --platform ios

This will prompt for Apple ID authentication (mattnicomn10@gmail.com).
Matthew must provide the 2FA code if prompted.
Report: Submission success/failure, any errors.

=== Step 3: Verify in App Store Connect ===

Check: https://appstoreconnect.apple.com/apps/6778488478/testflight/ios
Report: Build appears? Processing status? Time to "Ready to Test"?

=== Step 4: Commit buildNumber Increment ===

If eas build auto-incremented the buildNumber in app.json:
  git add mobile/app.json
  git commit -m "chore: bump ios buildNumber after first TestFlight production build"
  git push

=== Do NOT ===

- Do NOT add testers
- Do NOT submit for App Store review
- Do NOT modify backend, web, or AWS
- Do NOT change app functionality

Return: build ID, build URL, submit status, ASC screenshot or status description.
```

---

## 12. What This Document Does NOT Authorize

- ❌ Running `eas build`
- ❌ Running `eas submit`
- ❌ Adding TestFlight testers
- ❌ Submitting for Apple review
- ❌ Modifying mobile code
- ❌ Changing AWS/production resources
- ❌ Modifying credentials or certificates

Implementation requires Matthew to explicitly approve each gate and hand the AG prompt to the implementation agent.
