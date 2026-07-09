# Release 22D — Care Request Date Validation Copy and Auto-Fill UX Polish

**Release Date:** 2026-07-09
**Status:** PASS (Pre-Deploy Checkpoint)
**Type:** Frontend-only (no backend, Terraform, Cognito, or production data changes)
**Scope:** /book IntakeForm Step 2 validation copy and Auto-fill UX refinement

---

## Background

Release 22C deployed the /book care request form validation improvements from Release 22B.
Manual validation (2026-07-09) confirmed that:
- Inline field-level errors appear correctly
- The calendar section is highlighted on error
- Page scrolls to the first invalid field
- The form does not submit without required fields

However, one UX confusion case was identified:
- A user can populate Start Date and End Date but still have 0/14 days selected.
- The current error message ("Please select at least one visit date on the calendar.") does not clarify
  that entering the date range is not enough — the user must click Auto-fill Calendar or manually select dates.
- The Auto-fill Calendar button does not look visually distinct enough to be clearly actionable.
- Preferred Visit Windows has no separate inline error; it is only mentioned in the generic summary.

---

## Goals

1. Fix the Visit Dates error copy to be context-aware: detect whether Start Date and End Date are filled
   but no dates are selected, and show a specific message in that case.
2. Make the Auto-fill Calendar button visually distinct (primary-style pill button, not a flat text button).
3. Rename the button to "Select Dates from Range" for clarity.
4. Add a separate inline error at the Preferred Visit Windows section if no windows are selected.
5. Update the top summary error to be generic and non-duplicative: "Please complete the highlighted schedule fields below."
6. If multiple sections are missing (dates + windows), the summary should list them.
7. Preserve existing scroll/focus behavior.
8. Preserve all existing field-level error clearing on valid input.

---

## Current State (from code inspection of web/src/components/IntakeForm.jsx)

### Validation logic (line 67–87)
- Step 2 errors checked: service_type and selected_dates only.
- selected_dates error message (line 76): "Please select at least one visit date on the calendar."
- No validation for preferred visit windows (visit_windows) in step 2.

### Top summary error (line 267–270)
- Shows if any validationErrors key exists.
- Current copy: "Please select your dates and visit windows."
- Does not distinguish between what is missing.

### Auto-fill Calendar button (lines 320–346)
- Uses className="button-secondary btn-range-autofill"
- Styled as a secondary/ghost button.
- No visual distinction from the surrounding layout section.

### Preferred Visit Windows section (lines 393–430)
- Has no fieldError state and no inline error rendering.
- The label "Preferred Visit Windows" is present but is not marked required and has no validation.

---

## Proposed Changes

### File: web/src/components/IntakeForm.jsx

#### 1. Context-aware Visit Dates error message (validateStep, line 73–77)

Current:
  if (!formData.selected_dates || formData.selected_dates.length === 0) {
    errors.selected_dates = "Please select at least one visit date on the calendar.";
  }

Proposed:
  if (!formData.selected_dates || formData.selected_dates.length === 0) {
    const hasRange = formData.range_start && formData.range_end;
    errors.selected_dates = hasRange
      ? "You entered a date range, but no visit dates are selected yet. Click \"Select Dates from Range\" or select dates manually on the calendar below."
      : "Please select at least one visit date on the calendar, or enter a Start Date and End Date and click \"Select Dates from Range\".";
  }

#### 2. Separate inline validation for Preferred Visit Windows (validateStep, line 73–77)

Add:
  if (!formData.visit_windows || formData.visit_windows.length === 0) {
    errors.visit_windows = "Please select at least one preferred visit window.";
  }

#### 3. Top summary error copy (line 267–270)

Current:
  "Please select your dates and visit windows."

Proposed:
  Generic: "Please complete the highlighted schedule fields below."
  With itemized list if multiple errors: list the field names (Visit Dates, Preferred Visit Windows)
  only if both are missing. If only one is missing, no list needed.

#### 4. Auto-fill Calendar button rename and styling (lines 320–346)

Current:
  className="button-secondary btn-range-autofill"
  Text: "Auto-fill Calendar"

Proposed:
  className="button-primary btn-range-autofill" (primary pill styled with CSS)
  Text: "Select Dates from Range"

#### 5. Preferred Visit Windows inline error render (lines 393–430)

Add an error container below the "Preferred Visit Windows" label, analogous to the selected_dates error.

---

## Matthew Alignment on Design Preferences

1. **Preferred Visit Windows required?**
   - Matthew Choice: **Required** (block advancing to Step 3 if no window selected).
2. **Button rename preference?**
   - Matthew Choice: **"Select Dates from Range"**.
3. **Summary error itemized list?**
   - Matthew Choice: **Yes** (include list when multiple sections are missing).

---

## Scope and Guardrails

- Frontend-only changes: IntakeForm.jsx and IntakeForm.css only.
- No backend changes.
- No Terraform.
- No Cognito changes.
- No tenant metadata changes.
- No Stripe changes.
- No Google Calendar token/secret changes.
- No production records created.
- No emails sent.
- No passwords reset or set.
- Do not submit production test data.
- Use targeted git add only. Do not use git add .
- No deployment in this plan document. Deployment requires a separate Matthew approval.

---

## Verification Plan

### Automated
- Run npm run build after implementation to confirm no build errors.
- No backend tests impacted (frontend-only change).

### Manual Matthew Validation (Post-Implementation)
A. /book Care Request Form — Step 2 (repeat validation):
   1. Enter Start Date and End Date, but do not click Select Dates from Range or select manually.
      Click Next. Confirm the error message explains the range is not enough until dates are selected.
   2. Click "Select Dates from Range" — confirm it looks like a primary action button (solid, distinct).
      Confirm it fills the calendar correctly.
   3. Do not select any Preferred Visit Window. Click Next.
      Confirm a separate inline error appears at the Preferred Visit Windows section (if required).
   4. With all required fields filled, confirm Next advances correctly with no error.
   5. Do not submit production test data.

---

## Related Issues

- USmissionhero Cognito linkage: "Cognito user not found" on Resend Invite is a separate orphaned
  profile cleanup/relink issue from Release 22A. Not in scope for 22D. Track separately.
- Staff disabled/protected button bubbling: not confirmed in 22C due to no disabled profiles visible.
  Should be validated independently when a disabled staff profile is present.

---

## Files to Modify

| File | Change |
|---|---|
| web/src/components/IntakeForm.jsx | Context-aware error message, visit_windows validation, summary copy, button rename, error clear handlers |
| web/src/components/IntakeForm.css | New pill button styles |

---

## Status

- [x] Matthew confirms: Preferred Visit Windows required? (Required)
- [x] Matthew confirms: Button label preference ("Select Dates from Range")
- [x] Matthew confirms: Summary itemized list preference (Yes)
- [x] Implementation (22D pre-deploy)
- [x] Build verification
- [ ] Matthew manual validation
- [ ] Production deployment
- [ ] 22C closed as PASS after 22D validation
