# Production Validation Report: Release 5F

**Date:** 2026-05-15  
**Environment:** Production  
**Validator:** AG (Manual)  
**Status:** ✅ FULLY ACCEPTED (after Hotfix)

## Validation Results

| # | Test | Result |
|---|------|--------|
| 1 | Active pets show by default | ✅ Pass |
| 2 | Archived pets hidden by default | ✅ Pass |
| 3 | Show Archived appears when archived pets exist (even with 1 active pet) | ✅ Pass |
| 4 | Checking Show Archived displays archived pets with ⊘ marker | ✅ Pass |
| 5 | Selecting archived pet shows Restore Pet | ✅ Pass |
| 6 | Restore Pet returns pet to active tabs | ✅ Pass |
| 7 | Archive Pet still works on active pets | ✅ Pass |
| 8 | Add Pet still works | ✅ Pass |
| 9 | Multi-pet tabs still work | ✅ Pass |
| 10 | Request List and Scheduler no regression | ✅ Pass |

## Hotfix Note

Initial deploy hid the "Show Archived" toggle when archiving left only 1 active pet (toggle was inside `hasMultiplePets` gate). Hotfix rendered the toggle independently of the multi-pet selector.
