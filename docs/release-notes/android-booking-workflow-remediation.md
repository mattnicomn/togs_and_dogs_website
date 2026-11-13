# Android Booking Workflow Remediation and Acceptance Tracker

**Date:** 2026-10-29 (America/New_York)
**Disposition:** `ANDROID_BOOKING_WORKFLOW_LOCAL_DRAFT_NOT_RELEASED`
**Base:** `8fe7fa78ad707ac67a05d29059d2771a9aa256c8`.
**Authority:** local development, validation and Draft PR delivery only. NOT merged, built, deployed, distributed or Ryan-tested by this package.

## Evidence and state/role matrix

This is a source-and-contract investigation with synthetic automated fixtures, not a reproduction on Ryan's device. The observed device build/source was not supplied. Latest documented Play internal artifact remains Android 1.0.0 versionCode 4 from source `bf9f80d95c1846f197bab24d96463906bc26bfce`; later source changes are not assumed present there. See [distributed-build evidence](phase-24a-9c2-paired-remediation-revalidation-closeout.md).

| State / surface | Before | Implemented result | Role / server boundary |
| --- | --- | --- | --- |
| Pending approval rejected for M&G | Backend rejection with no usable verification continuation | After the specific prerequisite rejection, close confirmation and expose existing Verify M&G; no automatic retry | Owner/admin only; operator must confirm the meeting actually occurred |
| MEET_GREET_REQUIRED / MG_SCHEDULED | Verify existed | Existing verification retained; successful MG_COMPLETED offers separate approval | Existing `VERIFY_MEET_GREET`, then separate `APPROVED`; all backend checks remain |
| MG_COMPLETED / READY_FOR_APPROVAL | Approval hidden | Explicit approval action in detail | Owner/admin only; backend can still reject quote/prerequisite requirements |
| QUOTE_SENT / QUOTED | No next-step explanation | Check client response in web quote details; parent status is not proof of canonical acceptance; refresh available | No owner quote mutation or approval shortcut added |
| QUOTE_NEEDED | Dead-end display | Explicit web quote-editor handoff | No new mobile price/Send API |
| ASSIGNED parent | Change Staff with unclear visit access | Load/refresh children and select an exact visit within detail | Owner/admin/staff may inspect; execution remains staff-only |
| Exact assigned child | Existing E3B/E3B.1 Start/Complete | Preserved; selected child supplies the exact identity | No owner-operator permission expansion; backend tenant/worker checks remain authoritative |
| Missing/ambiguous/wrong-parent child | Unsafe to guess | Block selection/action; show refresh guidance, read retry and failure state | No date/index-based job inference; no parent COMPLETED fallback |
| PROFILE_CREATED / onboarding | Workflow label could imply account creation | Explain separate profile, account linking and invitation steps; use web client management | No Cognito/profile writes added |
| Approval/assignment/completion confirmations | Missing pet field produced undefined; completion copy claimed all dates | Actual multi-pet label or neutral fallback; conditional side-effect wording; exact-child completion wording | No invented pet/client identity or promised success |

Staff, client, unknown and bootstrap/null roles cannot gain owner approval/verification actions. Owner/admin Start/Complete remains absent pending a separate product decision, despite broader existing backend possibilities. No new status, endpoint, backend permission, auth flow, tenant mode or payment behavior is introduced.

## Contract trace and onboarding investigation

- [Request detail](../../mobile/src/screens/RequestDetailScreen.tsx) and [request card](../../mobile/src/components/RequestCard.tsx) use the existing [API client](../../mobile/src/api/client.ts): `/admin/review`, exact request read, assignment, `/admin/job/start` and `/admin/job/complete`.
- [Occurrence resolver](../../mobile/src/utils/occurrences.ts) remains unchanged. Refreshed parent identity is checked; cross-parent child data and ambiguous legacy children fail closed. Refresh does not retry mutations, ignores late responses after unmount and disables execution while reading.
- [Review handler](../../src/backend/handlers/review_handler.py) validates status transitions and M&G/quote prerequisites. The mobile change does not replace these checks with local assumptions or infer canonical quote acceptance from QUOTE_SENT.
- Confirmed source disconnect: web `CREATE_PROFILE` maps to `PROFILE_CREATED` through review; that label alone is not proof of profile provisioning. Actual `CUSTOMER_INTAKE` approval separately invokes `auto_create_or_link_client_profile`; failure is deliberately non-blocking. [Profile helper](../../src/backend/common/client_profile.py) and client onboarding endpoints are separate from a request status.
- **Not established:** a particular client's profile/account is broken, which private record failed, or whether a deployed backend differs. No customer data, Cognito operation or production query was used. No automatic account/invitation repair is attempted.
- [PCH-OPS](../planning/petcare-hero-operational-workflow-mobile-first.md) contains dated discovery plus later OPS-2A/2B work. Existing Decline and Verify functionality is preserved rather than reimplemented from stale discovery rows. [Ryan alignment](../planning/ryan-cross-platform-services-scheduling-workflow-alignment.md) and its legacy service/window rules remain controlling.

## Validation and acceptance tracking

- Isolated Node 22.23.4; fresh mobile `npm ci` from committed lockfile. No dependency, lockfile, Expo version or build-profile change.
- `npm run typecheck --prefix mobile`: PASS. `npm run test:ci --prefix mobile -- --runInBand`: 321/321 PASS across 35 suites (297 existing tests plus 24 new regressions); zero failing tests. New integration/copy suites contribute 17 + 7 passing cases. Existing React act/open-handle notices persist; no test suppression or increased timeout was introduced.
- New regression suites: [workflow integration](../../mobile/__tests__/AndroidBookingWorkflow.test.tsx) and [legacy confirmation copy](../../mobile/__tests__/bookingWorkflowCopy.test.ts).
- Coverage: M&G-to-approval, backend-denied approval, denied roles, terminal/quote blocked states, missing/legacy names, web handoff truthfulness, owner read-only visits, exact second-child Start/Complete, wrong-parent data, ambiguous hydration/retry and unmount races. Existing E3B/E3B.1, decline/401/403, role and generated-contract suites also run.
- Shared compatibility validators: tokens 9/9, constants 24/24, adapters 7/7, contract adapters 9/9. First Windows generator-idempotence checks encountered CRLF/LF differences; repeat checks passed after generator normalization. Generated outputs were verified identical to HEAD and checkout line endings reinstated; none are included in the change.
- Legacy service/window adapters, backend APIs, web runtime, canonical policies and CI configuration are unchanged.
- Author-agent self-review only; no independent human review claimed. No screenshot or private client data is included.

| Acceptance gate | Status |
| --- | --- |
| Local automated behavior/roles/compatibility | Corrective checkpoint PASS: TypeScript; 334 tests / 35 suites; 49 shared validator checks |
| Android emulator/physical device acceptance | NOT RUN; separately authorized testing/build needed |
| Exact Ryan installed build and role | UNKNOWN; owner confirmation needed without private records |
| Owner/admin visit-execution UX | DEFERRED product decision; staff-only preserved |
| Owner quote editor / client-response handoff | WEB HANDOFF; no mobile owner quote editor in this package |
| Profile/invitation lifecycle remediation | INVESTIGATED; targeted backend/account work requires separate scope and evidence |
| CI / integration readiness | Inspect exact PR head/run; baseline failures and canonical CLEAN/RC gates remain separate |
| Android build / distribution / Ryan testing | NOT AUTHORIZED OR PERFORMED |

## Release blockers and next owner decisions

1. Review this source-only Draft; any merge/Ready action needs separate authority and current canonical gates. PR43/44/45 remain untouched; PR45's proposed exception is inactive and cannot authorize this PR.
2. Resolve existing advisory CI/governance and independent RC-integrity blockers without weakening policy. PR19 reconstructed source is source-only; original historical plan/ZIP remain MISSING. Preservation work is separate.
3. Decide Ryan's owner-versus-assigned-staff workflow and any owner-operator UX policy; do not bypass RBAC by changing role locally.
4. Approve an exact mobile release candidate and production-backend compatibility review. Current main includes merged-but-undeployed work; do not deploy/build indiscriminately or activate W1/intake behavior.
5. Separately authorize Android build, sanitized device acceptance, internal distribution and Ryan testing. Current DEV selection fails closed; no DEV backend is created here.
6. Scope future owner quote/cancellation parity and actual profile/onboarding diagnosis separately. Production payment, Stripe live, tenant changes, AWS/Terraform/account migration and mobile distribution remain gated.

## PR46 corrective review checkpoint — 2026-10-29

The fresh author-agent review of initial head `c519aacf36bd728acc3c84433c3df3f176413732` found two confirmed defects not covered by its passing 321-test suite: shared unsaved notes could cross from child A to B, and reselecting a started child restored its stale pre-Start snapshot. That initial validation is historical evidence, not independent reviewer approval or proof those cases passed.

Corrective implementation:

- Unsaved drafts are held in memory under the exact request/client/child-job tuple. Selecting A/B restores only that child's draft. Ambiguous identity disables editing. Successful completion clears only the submitted child's draft; failure retains it. Refresh does not remap notes, and leaving the screen discards its unsaved in-memory drafts. No persistent storage or cross-screen draft transfer is added.
- Confirmed Start results update both the selected occurrence and the parent's selectable child collection. Server-returned status/timestamps are preserved; reselecting A and switching A→B→A no longer restores stale Start. Existing replay, failed-Start reconciliation, unmount guards and exact-child resolver remain in force.
- Completion confirmation identifies the selected visit date and window. Missing date information is labeled unavailable rather than inferred from the first date of a multi-day booking.
- Staff-only execution remains unchanged. Owner-as-sitter and owner quote management remain separate product proposals; no backend, RBAC, quote/payment or service/window changes.

Corrective regressions add **13 passing cases**: A→B and B→A notes, draft retention across failed/successful refresh, failed completion without cross-child submission, unmount isolation, Start/reselection across children, immediate refresh during active Start, READY_FOR_APPROVAL positive confirmation, and five denied/non-staff execution roles. The existing race/replay/legacy suites remain passing.

Validation: isolated Node 22.23.4; `npm run typecheck --prefix mobile` PASS; full `npm run test:ci --prefix mobile -- --runInBand` **334/334 PASS across 35 suites**, up from 321 at the initial head, zero failing tests. Shared tokens/constants/adapters/contract-adapters **9/24/7/9 PASS**. The known Windows generator CRLF/LF idempotence issue recurred on the first adapter checks; repeat checks passed, generated content matched HEAD and original checkout line endings were reinstated. No generated files, dependencies or lockfiles are included. Existing React act/open-handle notices persist; no suppression or timeout increase.

The corrected immutable head, actual CI run and baseline reconciliation are recorded in PR46's delivery record. This checkpoint does not claim independent approval, Android device acceptance, build, distribution, deployment, Ryan testing or integration readiness. PR43/44/45 and retained release evidence remain unchanged.

Device acceptance still requires separate authorization. Add explicit checks for A→B→A draft isolation, failure/retry, leaving the screen with unsaved notes, Start→reselect, selected date/window confirmation, and denied roles to the original acceptance matrix.

## Resume checkpoint

Dedicated branch: `mobile/android-workflow-remediation`. Exact commit/PR and CI run are bound by the GitHub delivery record; avoid a self-referential commit hash in this file. Next action is owner review and separately scoped acceptance planning, not deployment. Original release outcomes, other worktrees/branches, retained evidence and PR43/44/45 are preserved.