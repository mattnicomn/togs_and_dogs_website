# Release Notes: Phase 1B.3 — Admin Dashboard Hook-Order Production Hotfix (Pre-Deploy)

**Date:** 2026-07-21 (UTC)  
**Status:** ✅ LOCAL IMPLEMENTATION & VALIDATION COMPLETE — PRODUCTION DEPLOYMENT PENDING MATTHEW APPROVAL  
**Type:** Frontend-only bugfix (React/Vite)

---

## 1. Executive Summary

During the Phase 1B.3 authenticated manual smoke test, a production loading failure was discovered on the `/admin` and `/admin/` routes. Direct navigation or transition to `/admin` while authenticated caused the browser to crash to a blank screen.

The root cause was diagnosed as a **React Hook Order Violation** in `AdminDashboard.jsx`. A `useRef` hook introduced in Phase 1B.3 was declared after an early return block that handles unauthenticated login screens. When the session resolved, the component rendered more hooks than in the previous unauthenticated render, causing React to throw Minified Error #310 and crash.

This hotfix resolves the issue by moving the hook declaration to the top-level section of the component body, ensuring it runs on every render regardless of authentication state. Two new structural regression tests have been added to the test suite, and all 140 automated tests pass cleanly.

No backend changes, database changes, Cognito writes, or CloudFront configuration modifications occurred. Production deployment is pending Matthew's approval.

---

## 2. Diagnostics & Root Cause

- **Diagnostic Commit:** `7eb2647`
- **Symptom:** direct navigation or client-side transition to `/admin` while authenticated renders a completely blank screen, accompanied by:
  `Error: Minified React error #310; visit https://react.dev/errors/310` ("Rendered more hooks than during the previous render.")
- **Root Cause:**
  In `web/src/components/AdminDashboard.jsx`, the authentication check was performed at line 2906:
  ```javascript
  if (!isAuthenticated) {
    // returns early with login form or reset challenge
    return ( ... );
  }
  ```
  However, the `clientDrawerTriggerRef` was declared on line 2981 (after the early return block):
  ```javascript
  const clientDrawerTriggerRef = useRef(null);
  ```
  This violated React's hook order invariants, crashing the React app on authentication state transitions.

---

## 3. Bounded Correction Details

The correction relocates the hook declaration to the top-level block before the early return checks:

### Source Modification
In `web/src/components/AdminDashboard.jsx`:
- Moved `clientDrawerTriggerRef` to the top-level ref section (near line 98):
  ```diff
    const activeTabRef = useRef(null);
    const staffDrawerTriggerRef = useRef(null);
    const staffDrawerCloseBtnRef = useRef(null);
  + const clientDrawerTriggerRef = useRef(null);
  ```
- Removed the duplicate declaration from line 2981.

No other functional, styling, API, or authentication logic was changed.

---

## 4. Test & Build Validation

### Automated Tests
- **Legacy Suite (Node test runner):** 96 passed (increased by 2 new regression tests), 0 failed
- **Component Suite (Vitest):** 44 passed, 0 failed
- **Total Combined:** 140 passed, 0 failed
- **Status:** PASS

### Structural Regression Coverage Added
Two new tests were added to `web/tests/phase1b3.test.js`:
1. **Hook Occurrence and Order Check**: Asserts that `clientDrawerTriggerRef` is defined exactly once and appears textually before `if (!isAuthenticated)`.
2. **Hook Invariant Check**: Asserts that no React hooks (`useState`, `useEffect`, `useRef`, `useMemo`, `useCallback`, `useContext`) are declared after the authentication early return block.

### Production Build
- **Vite Build:** SUCCESS
- **Modules Transformed:** 107
- **JavaScript Bundle File:** `dist/assets/index-BnpMcuCZ.js` (968.18 KB)
- **CSS Bundle File:** `dist/assets/index-CRQyBP3J.css` (83.30 KB)
- **Known Warning:** Standard bundle size warning (>500 KB) remains.

---

## 5. Exclusions & Safety Guards

- ❌ **No AWS Access:** No S3 syncs or CloudFront invalidations were performed.
- ❌ **No Production Modification:** No live files, configuration, backend Lambdas, API Gateways, or databases were changed.
- ❌ **No Cognito Writes:** No Cognito users, groups, or passwords were altered.
- ❌ **No Stripe/Google Calendar Changes:** Unaffected.

---

## 6. Next Gate: Kiro Hotfix Review & Matthew Approval

The local hotfix is complete and verified. The status of Phase 1B.3 is updated to:
- **Status:** Local Bounded Hook-Order Correction Implemented — Production Hotfix Deployment Pending Review and Matthew Approval.
