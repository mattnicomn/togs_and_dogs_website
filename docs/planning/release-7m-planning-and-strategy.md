# Release 7M Planning & Strategy — Admin UI Service Labels & Smoke Test Validation

This planning document outlines the recommended next steps, low-risk polish areas, and strategy for **Release 7M**. 

---

## 🔍 Focus Area Analysis & Repo Status

### 1. The Untracked `.kiro/specs/terms-and-privacy-policy/` Folder
- **Status:** Contains the specifications and design drafts for the terms-and-privacy policy consent workflows.
- **Analysis:** These are configuration/specification assets associated with the repository-level Kiro spec engine, which are intended to reside in the workspace without active code deployments.
- **Recommendation:** Keep this folder as-is and untracked (or add to `.gitignore` if required), as it does not represent deployable code.

### 2. The Untracked `docs/planning/mobile-app-strategy.md` File
- **Status:** Contains the comprehensive React Native Expo monorepo strategy, screen inventory, and push notification blueprint.
- **Analysis:** This document is extremely valuable for the repository's long-term roadmap.
- **Recommendation:** Formally commit and track this file under `docs/planning/` in Release 7M to clean up `git status` and persist this strategic roadmap.

### 3. Admin UI display polish for internal service labels
- **Status:** Verified that `web/src/components/AdminDashboard.jsx` at line 3760 renders the raw database service key (e.g., `PET_SITTING`, `WALK_30MIN`, `DROPIN_1HR`) directly.
- **Analysis:** Displays raw UPPERCASE strings with underscores in the "Customer / Service" column of the request table.
- **Recommendation:** Implement a clean, friendly mapping function `getServiceLabel(service_type)` matching the `templates.py` backend mappings (e.g. `WALK_30MIN` -> `30-Minute Walk`, `PET_SITTING` -> `Pet Sitting`).

### 4. Repeatable E2E Production Smoke Test Checklist
- **Status:** No centralized, repeatable manual validation checklist exists in the repo today.
- **Analysis:** With the introduction of multi-day bookings, non-consecutive occurrences, batch-dedup, and parent-JOB context merging, a centralized, step-by-step smoke test guide is crucial for future deployments.
- **Recommendation:** Create a formal, reusable validation document under `docs/validation/production-smoke-test-checklist.md` that guides testers through verifying both single-day and multi-day workflows.

---

## 📋 Proposed Scope: Release 7M

We recommend scoping **Release 7M** as a **zero-risk UI polish & repository hygiene** release containing three key deliverables:

### 1. Frontend: Admin UI Service Labels Polish
- **Target File:** [`web/src/components/AdminDashboard.jsx`](file:///c:/Users/mattn/OneDrive/Desktop/togs_and_dogs_website/web/src/components/AdminDashboard.jsx)
- **Changes:**
  - Implement a new helper function `getServiceLabel` inside the component:
    ```javascript
    const getServiceLabel = (serviceType) => {
      if (!serviceType) return 'UNKNOWN SERVICE';
      const friendly = {
        'WALK_30MIN': '30-Minute Walk',
        'WALK_60MIN': '60-Minute Walk',
        'DROPIN_1HR': '1-Hour Drop-in',
        'DROPIN_3HR': '3-Hour Drop-in',
        'OVERNIGHT': 'Overnight Care',
        'PET_SITTING': 'Pet Sitting',
        'MEET_GREET': 'Meet & Greet'
      };
      return friendly[serviceType] || serviceType.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    };
    ```
  - Refactor line 3760 to use this mapping:
    ```html
    <span className="micro-text">{getServiceLabel(item.service_type)}</span>
    ```

### 2. Strategy: Track Mobile App Strategy
- **Action:** Stage and commit the existing `docs/planning/mobile-app-strategy.md` file to formally integrate it into the main branch.

### 3. Validation: Repeatable E2E Smoke Test Checklist
- **Target File:** [NEW] `docs/validation/production-smoke-test-checklist.md`
- **Changes:** Create a repeatable checklist document outlining the precise manual validation flows:
  - **Scenario A: Single-Day Booking Flow** (submission, approval, assignment, calendar validation, singular notification check).
  - **Scenario B: Multi-Day Non-Consecutive Booking Flow** (submission with non-consecutive dates, approval, assignment, child JOB allocation, parent dates context merging, deduplicated notification dispatch, Google Calendar multi-event verify).
  - **Scenario C: Visit Cancellation Flow** (cancellation cascade, client-friendly email subject validation).

---

## ⚡ Risk Assessment & Deployment

- **Risk:** **NEGLIGIBLE**. Frontend changes are purely cosmetic and non-functional.
- **Backend/Terraform Impact:** **NONE**. Zero modifications to python code, infrastructure templates, or production database payloads.
- **Deployment Requirement:** Rebuild frontend (`npm run build` in `/web`) and run standard S3 sync and CloudFront invalidation.
