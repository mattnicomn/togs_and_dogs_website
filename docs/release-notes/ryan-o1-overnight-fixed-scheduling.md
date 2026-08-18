# Ryan Cross-Platform Alignment O1 — Overnight Fixed 9PM–7AM Scheduling

**Date:** 2026-08-18  
**Status:** ✅ COMMITTED / PUSHED / NOT DEPLOYED  
**Commit:** `46bb6b87e5d5a191017d12aad66e81ff58945a15`  
**Independent Review:** Kiro `RYAN_O1_OVERNIGHT_FIXED_SCHEDULING_IMPLEMENTATION_CORRECT`  
**Starting SHA:** `c51828ec2ad592bdfbf4243a6ca06bd1bea3ccae`

## Approved Decision

Matthew approved one fixed schedule for every new `OVERNIGHT` request:

- the selected date is the local calendar date service starts;
- start is 21:00 local on that selected date;
- end is 07:00 local on the following calendar date;
- nominal duration is 600 minutes / 10 hours;
- one selected start-date creates one child occurrence; and
- there is no visits/day, selectable window, arbitrary time, or custom range.

Pricing is not part of O1.

## Previous Behavior

Before O1, the shared Overnight entry retained a 720-minute unresolved compatibility duration, no allowed windows, and an unresolved window-selection mode. New intake could fall through the legacy `ANYTIME` normalization. Historical Calendar paths could therefore produce an all-day event or use an explicit/legacy start plus 720 minutes. Single-date requests did not consistently use the deterministic child-occurrence Calendar path, while multi-date requests created one child per selected date with noncanonical identity.

## Local Implementation

- The generic service schema now distinguishes selectable-window, fixed, and legacy-compatibility schedules. `OVERNIGHT` is fixed at contract-owned `21:00` → `07:00`, crosses midnight, has confirmed 600-minute nominal duration, has no selectable windows, and retains `legacyDurationMinutes: 720` explicitly for historical compatibility.
- Generated Web, Mobile, and Backend adapters were regenerated through the established deterministic generator.
- New Web customer, Mobile customer, and Admin requests send no scheduling-selection fields. The backend rejects supplied window, visits/day, preferred/custom time, start-time, or end-time fields and derives an explicit persisted fixed-schedule marker plus contract values.
- The persisted `canonical_schedule_mode: fixed` marker is the new/history boundary. Unmarked historical Overnight records remain on the legacy read/Calendar path; there is no data migration or reinterpretation.
- Job creation emits one deterministic UUIDv5 child per selected Overnight start-date, in an Overnight-specific namespace. Each child carries selected-date 21:00, following-date 07:00, 600-minute nominal duration, fixed occurrence marker, and stable Calendar identity. Replay reuses the same child rather than duplicating it.
- Calendar generation constructs local selected-date 21:00 and local following-date 07:00 independently in `America/New_York`. It does not add 600 elapsed minutes, use the legacy window-start table, or create an all-day event. Ordinary, spring-forward, and fall-back tests preserve the exact local clocks even though elapsed UTC time is respectively 10, 9, or 11 hours.
- Web customer, Admin New Visit, Mobile Intake, and MasterScheduler display the fixed contract schedule and following-morning meaning without exposing a scheduling selector or pricing. Web/Mobile review surfaces the selected dates as Overnight start dates.
- Assignment, cancellation, Calendar deletion tolerance, and booking-level notification batching continue through existing handlers. Multi-date assignment reaches every child while retaining one `STAFF_ASSIGNED` and one `VISIT_SCHEDULED` notification for the batch.

## Compatibility and Boundaries

Historical unmarked Overnight records remain readable and retain the pre-O1 720-minute/all-day or exact-time interpretation. Existing legacy `visit_window`/`visit_windows` values are not migrated. Check-In and W1 Walk scheduling remain unchanged.

O1 has been independently reviewed (Kiro: `RYAN_O1_OVERNIGHT_FIXED_SCHEDULING_IMPLEMENTATION_CORRECT`), committed (`46bb6b87e5d5a191017d12aad66e81ff58945a15`), and pushed. It is NOT DEPLOYED, not built or distributed for Mobile, and not received by Ryan. No production request, booking, job, DynamoDB write, Calendar mutation, notification, deployment, Terraform, EAS, Cognito, Postmark, Stripe, tenant, or public-site action occurred.

## Local Validation

- shared constants: 23/23;
- generated adapter parity/determinism: 9/9;
- focused O1 backend: 22/22;
- combined O1/W1/Slice A/Slice B/R1 backend: 90/90;
- focused Web customer/Admin/Scheduler: 52/52;
- full Web Vitest: 286/286 across 22 files;
- legacy Web: 99/99;
- Web production build: success, 110 modules transformed;
- Mobile TypeScript: pass;
- focused Mobile Intake: 28/28;
- combined Mobile Intake/D1 navigation: 34/34; and
- full Mobile: 128/128 across 13 suites.

## Remaining Gates

Check-In pricing, Walk pricing, Overnight pricing, deposit policy, legacy-service retirement, Stripe automation, Slice E, Slice F, deployment, and Mobile build/distribution remain unresolved or separately approval-gated.

## Disposition

**Independent Review:** `RYAN_O1_OVERNIGHT_FIXED_SCHEDULING_IMPLEMENTATION_CORRECT`  
**Final Status:** `RYAN_O1_OVERNIGHT_FIXED_SCHEDULING_COMMITTED_PUSHED_NOT_DEPLOYED`
