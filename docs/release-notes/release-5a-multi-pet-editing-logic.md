# Release 5A: Multi-Pet Independent Editing

**Deployed:** 2026-05-14 (Hotfix 2: 2026-05-15)  
**Environment:** Production  
**Status:** ✅ Fully Accepted — Production Validated After Hotfix 2  
**Type:** Feature Release (CareCard & State Management)

---

## Overview
Release 5A aims to enable independent editing for individual pets within a multi-pet request. Previously, edits made in the CareCard were global to the request; R5A introduces pet-specific tabs and saves.

## Proposed Features
- **Independent Pet Tabs:** Sub-navigation within the CareCard to switch between pets.
- **Granular Saves:** `handleSave` targets the specific `pet_id` of the selected pet.
- **State Reinitialization:** `formData` refreshes when switching pets to ensure edits apply to the correct profile.

## Current Issues (Validation Failure)

### 1. Unreliable Pet Selector Chips
Validation found that the pet selector chips (tabs) intermittently fail to appear for multi-pet records. 
- Newly created multi-pet records often show only the primary pet's name without switching options.
- Legacy multi-pet records continue to show merged fields instead of the tabbed interface.

### 2. State Management & Data Loss
Switching between pets (when tabs are visible) causes all unsaved changes to be discarded. 
- The `useEffect` in `CareCard.jsx` reinitializes `formData` and exits edit mode on every pet switch.
- Users expect to be able to edit multiple pets and save them as part of a single workflow or at least have their changes preserved between tabs.

### 3. Navigation Inconsistency
Inconsistent rendering of pet identities and headers when switching between records with different pet counts.

---

## Validation Results

| Goal | Description | Result | Observations |
|---|---|---|---|
| 1 | Open multi-pet CareCard | **PASS** | |
| 2 | Pet selector tabs visible | **FAIL** | Intermittent; often missing for multi-pet records. |
| 3 | Switch between pets | **FAIL** | Data loss occurs on switch; UI state is not persistent. |
| 4 | Edit field for specific pet | **PASS** | Works if tabs are visible and user saves before switching. |
| 5 | Change persistence | **PASS** | Works for single pet save. |
| 6 | Regression: Single-pet | **PASS** | Unaffected. |
| 7 | Regression: Legacy | **FAIL** | Legacy records do not benefit from the new UI. |

## Recommendation
**REJECTED.** Release 5A requires a hotfix to:
1. Ensure the `pet-selector-nav` reliably renders for all records containing multiple pets (fixing the `_allPets` population logic).
2. Implement a more robust state management strategy (e.g., a per-pet `formData` cache) to prevent data loss when switching tabs.
3. Fix the "Edit Mode Exit" behavior on pet switch if it interferes with user workflow.
