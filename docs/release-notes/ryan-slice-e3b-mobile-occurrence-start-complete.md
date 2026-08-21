# Ryan Slice E3B — Mobile Occurrence Selection and Start → Complete Workflow

**Date:** 2026-08-20
**Status:** ✅ IMPLEMENTED / VALIDATED / NOT DEPLOYED
**Distribution:** NOT INCLUDED IN CURRENT INTERNAL MOBILE BUILDS
**Starting SHA:** `e10a98e9a655631817803fd0756b03425889bd0b`

Mobile Schedule now hydrates active parents through the E3A exact-request read and projects authoritative child occurrences. Walk dates, Check-In date × window children, and Overnight start/end dates remain separate and deterministic. Tapping passes the exact child and `job_id`; selected-date array position is no longer used when authoritative occurrence data exists.

Staff detail exposes **Start Visit** for an exact unstarted `ASSIGNED` child. It sends only `job_id`/`request_id`, blocks duplicate in-flight taps, and uses server `started_at`/`started_by`. An ambiguous failure refetches once: persisted `started_at` reconciles success, otherwise Mobile shows a retryable error and invents no timestamp. Started is presentation-only; no canonical `IN_PROGRESS` exists.

**Complete Visit** calls existing per-child Complete with the exact `job_id` and preserves notes. Parent `/admin/review COMPLETED` fallback is not used. A singular legacy `job_id` remains safely usable, including Complete without Start; multiple legacy child IDs without occurrence data produce a refresh-required blocked state.

Validation: focused E3B/contract integration 18/18; full Mobile 132/132; TypeScript pass; shared constants 24/24; adapter validator 9/9; E3A backend regression 24/24; diff check pass. No backend, Terraform, shared status, Web, build, distribution, or deployment change occurred.

Early/late/same-day policy, reversal, mandatory Start-before-Complete, client visibility, notifications, Calendar effects, offline timestamps, and admin-on-behalf UX remain deferred.
