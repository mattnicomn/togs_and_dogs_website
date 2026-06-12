# Release 10K: Internal TestFlight Build for Login Error Fix Plan

**Status:** ⏳ Pending Matthew's approval  
**Priority:** High (remedial build for login error visibility regression)  
**Risk to Production:** None (mobile build + upload only; no backend, web, or database changes)  
**Scope:** EAS production build + upload to App Store Connect / TestFlight (build `1.0.0 (3)`)  

---

## 1. Goal Description

Implement Release 10K to compile, build, and submit the login error visibility fix (implemented in Release 10J) to Apple App Store Connect / TestFlight. This allows the user to manually verify that the login error screen functions correctly and doesn't silently wipe the login fields without displaying feedback.

## 2. Preconditions Before Build

Verify that the local environment and credentials are correct before proceeding:

| # | Precondition | Status |
|---|-------------|--------|
| 1 | `mobile/eas.json` configuration verified | ✅ (No changes needed) |
| 2 | `mobile/app.json` configuration verified | ✅ (No changes needed) |
| 3 | Logged in to EAS CLI as `mattnicomn` | ✅ Verified (`npx eas whoami`) |
| 4 | Working tree is clean (all 10J fixes pushed) | ✅ Verified (`git status`) |
| 5 | TypeScript compiles cleanly | ✅ Verified (`npx tsc --noEmit` passed) |

---

## 3. Build + Upload Command Sequence

### Step 1: Pre-Build Checks
Verify the workspace is clean and compiles:
```bash
cd mobile
git status
npx tsc --noEmit
```

### Step 2: Production iOS Build (Gate A)
Build the app on Expo's remote build servers:
```bash
cd mobile
npx eas build --profile production --platform ios
```
*   **What happens:**
    *   EAS builds the bundle remotely using Expo's cloud servers.
    *   `autoIncrement: true` automatically bumps the remote iOS build number from `2` to `3`.
    *   Returns a build ID and build URL.
    *   Takes approximately 5-15 minutes.

### Step 3: TestFlight Submission (Gate B)
Upload the build to App Store Connect:
```bash
cd mobile
npx eas submit --platform ios
```
*   **What happens:**
    *   The build is sent to App Store Connect.
    *   EAS uses the pre-configured App Store Connect API Key (`Key ID: 2JDRC3Z2D8`) configured during the Release 10E setup.
    *   Takes approximately 2-5 minutes.

---

## 4. Verification Plan (Gate C)

Matthew will manually test the build on device once Apple finishes processing build `1.0.0 (3)` (usually 5–15 minutes after upload):

### Pre-test
- [ ] Confirm Apple processing email received.
- [ ] Open App Store Connect → TestFlight → verify build `1.0.0 (3)` shows status `Ready to Test`.
- [ ] Update and install the app via TestFlight on iPhone 15 Pro.

### Manual Verification Checklist
| # | Test Case | Expected Behavior | Pass? |
|---|-----------|-------------------|-------|
| 1 | **Wrong password entered** | Error message appears: *"Incorrect email or password. Please try again."* Email field remains populated; password field is cleared. | |
| 2 | **Empty fields submitted** | Error message: *"Please enter your email and password."* | |
| 3 | **Correct credentials (admin)** | Logs in successfully; routes to Admin Dashboard. Welcome subtitle says *"Welcome back, mattnicomn10"*. | |
| 4 | **Correct credentials (client)** | Logs in successfully; routes to Client Dashboard and displays visits for `brearockwell@gmail.com`. | |
| 5 | **Correct credentials (staff)** | Logs in successfully; routes to Staff Dashboard and displays assigned visits. | |
| 6 | **Forgot password flow** | Tapping "Forgot password?" is functional and lets user request a reset code. | |

---

## 5. Rollback / Cleanup

If any issues occur during build or submission:
- **Build fails:** No action required (nothing is modified on device or App Store Connect).
- **Upload fails:** Re-run the submit command.
- **Build needs replacement:** Set the build to Expired in App Store Connect TestFlight build options, then rebuild.

No web, database, or backend resources are modified during this release.

---

## 6. Approval Gates

| Gate | Action | Approver | Status |
|------|--------|----------|--------|
| **Gate A** | Run EAS Build for production iOS | Matthew | ⏳ Pending Approval |
| **Gate B** | Submit/Upload build to App Store Connect | Matthew | ⏳ Pending Approval |
| **Gate C** | Verify the fix on iPhone 15 Pro via TestFlight | Matthew | ⏳ Pending TestFlight |
