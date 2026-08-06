# Phase 24A-2C.2D.4 — Optional Google Calendar Color Metadata Design & Value Assessment

**Status:** **PHASE 24A-2C.2D.4 ASSESSED / NO IMPLEMENTATION RECOMMENDED / GOOGLE-SPECIFIC COLOR MAP REMAINS ISOLATED IN CALENDAR RUNTIME / CONFIGURABLE COLOR POLICY DEFERRED / NOT DEPLOYED**

**Date:** 2026-08-05
**Base checkpoint:** `6ec161d47b97881fcdfc13727859f8a47c00bfc1` (`feat: wire generated calendar service metadata`)

---

## 1. Scope and authorization

Matthew explicitly authorized a read-only Phase 24A-2C.2D.4 value and design assessment for optional Google Calendar color metadata, followed by this documentation-only local closeout.

The authorization explicitly required:
- keeping `SERVICE_COLORS` handwritten and isolated in `src/backend/common/google_calendar.py`;
- performing zero application source code, test, contract, generator, validator, backend handler, persistence, scheduling, notification, web, mobile, infrastructure, or dependency changes;
- performing zero staging, commit, push, deployment, production testing, production-data access, Google Calendar API invocation, event creation/update/deletion/resynchronization, or multi-tenant configuration.

## 2. Starting checkpoint

Assessment and closeout documentation began on `main` at `6ec161d47b97881fcdfc13727859f8a47c00bfc1`, with `HEAD` equal to `origin/main`, a clean working tree, and an empty stash.

The latest completed validated production release remains Phase 1B.5C-D.2. Phase 24A remains local-only and is not deployed or distributed. Phases 2D.1, 2D.2, and 2D.3 are committed and pushed at the base checkpoint. Phase 2D.4 completes the planned Phase 2D backend service-metadata workstream as an assessed no-implementation closeout.

## 3. Assessment purpose

Phase 24A-2C.2D.1 hardened contract duration and label parity, Phase 24A-2C.2D.2 introduced the generated backend adapter `src/backend/common/generated_service_types.py`, and Phase 24A-2C.2D.3 derived `SERVICE_DURATIONS` and `FRIENDLY_SERVICE_NAMES` (`label`) directly from generated contract metadata. Phase 2D.4 evaluated whether the remaining handwritten calendar dictionary literal in `google_calendar.py` — `SERVICE_COLORS` — should also be migrated into canonical contract metadata, derived via the generator, or configured separately.

## 4. Current color inventory

In `src/backend/common/google_calendar.py`:

```python
SERVICE_COLORS = {
    'WALK_30MIN': '9', 'WALK_60MIN': '9', 'DROPIN_1HR': '7',
    'DROPIN_3HR': '7', 'OVERNIGHT': '6', 'PET_SITTING': '10', 'MEET_GREET': '3',
}
```

Unresolved/fallback color:
```python
color_id = SERVICE_COLORS.get(service_type, '8')
```

Visual mapping:
- `WALK_30MIN` / `WALK_60MIN` → `"9"` (Blueberry / Blue)
- `DROPIN_1HR` / `DROPIN_3HR` → `"7"` (Peacock / Cyan)
- `OVERNIGHT` → `"6"` (Tangerine / Orange)
- `PET_SITTING` → `"10"` (Basil / Green)
- `MEET_GREET` → `"3"` (Grape / Purple)
- Unresolved / noncanonical / missing fallback → `"8"` (Graphite / Gray)

## 5. Runtime consumer scope

- `_build_event_body()` in `src/backend/common/google_calendar.py` is the **ONLY** reader of `SERVICE_COLORS` across the repository.
- Web UI components use design system CSS color tokens (`web/src/generated/color-tokens.css`). They do not consume or display Google Calendar `colorId` strings.
- Mobile UI components use React Native theme colors (`mobile/src/theme/generatedColors.ts`). They do not consume or display Google Calendar `colorId` strings.
- Shared JSON contracts and generated platform adapters contain zero calendar color properties.

## 6. Canonical-contract fitness conclusion

Adding a property such as `calendarColorId` to `shared/constants/service-types.json` was **REJECTED** because:
1. Google Calendar `colorId` strings (`"9"`, `"7"`, `"6"`, etc.) are Google API-specific presentation keys, not platform-neutral service metadata.
2. Exposing provider-specific keys in `service-types.json` pollutes the shared cross-platform contract.
3. Web and mobile platform adapters would receive dead, unconsumed metadata.
4. It creates premature coupling to Google Calendar and limits future calendar provider flexibility (e.g. Outlook / Apple Calendar).

## 7. Backend-generated-metadata fitness conclusion

Injecting `SERVICE_COLORS` into `src/backend/common/generated_service_types.py` via the generator without canonical contract backing was **REJECTED** because:
1. Generator outputs must remain 100% derived from the canonical contract source (`shared/constants/service-types.json`).
2. Generating backend-only metadata not present in the canonical contract would create un-sourced hidden authority in the generator script.
3. It would break four-way adapter validation parity enforced by `shared/validate-contract-adapters.mjs`.

## 8. Calendar-specific configuration conclusion

1. The handwritten `SERVICE_COLORS` map is currently correctly isolated inside `src/backend/common/google_calendar.py`.
2. Future configurable color preferences (e.g., per-tenant or per-calendar colors) belong under a separately approved future calendar-preferences or multi-tenant SaaS phase.
3. Speculative multi-tenant configuration is unapproved and prohibited by current project guardrails (`TENANT_RESOLUTION_MODE=multi` remains disabled).

## 9. Manual Google color override implications

In `google_calendar.py`, `update_calendar_event()` issues full-body event updates to Google Calendar, which re-applies `'colorId': color_id` on subsequent automated updates (e.g. status changes, worker assignments). This behavior is intrinsic to Google Calendar API full-body payload sync and exists independently of where `SERVICE_COLORS` is defined.

## 10. Practical value classification

**`NEGLIGIBLE / NEGATIVE VALUE`**

- **Benefit of moving color IDs to shared contracts:** None. Zero web/mobile UI benefit; zero backend functional benefit.
- **Cost of moving color IDs to shared contracts:** Contract pollution, 3-adapter bloat, validator burden, and unnecessary Lambda/web/mobile rebuild diffs on any color adjustment.

## 11. Option comparison summary

| Option | Evaluated Approach | Decision | Rationale |
|---|---|---|---|
| 1 | Add `calendarColorId` to `service-types.json` | **REJECTED** | Pollutes cross-platform contract with Google-specific string IDs; bloats web & mobile adapters. |
| 2 | Add provider-neutral color tokens (`displayColor`) | **REJECTED** | Unnecessary abstraction layer; web/mobile already have CSS/RN design token systems. |
| 3 | Backend-only generator-injected color map | **REJECTED** | Injects un-sourced authority into generator; breaks 4-way adapter validation symmetry. |
| 4 | Tenant/calendar-configurable color settings | **DEFERRED** | Premature for current single-tenant local baseline (`TENANT_RESOLUTION_MODE=multi` unapproved). |
| 5 | **Keep `SERVICE_COLORS` handwritten in `google_calendar.py`** | **APPROVED** | **Clean encapsulation, zero contract drift, zero web/mobile pollution, 100% behavior-preserving, 0 risk.** |
| 6 | Omit `colorId` completely (use calendar default) | **REJECTED** | Would visually alter Google Calendar events and break existing characterization tests. |

## 12. Recommended decision

**Keep `SERVICE_COLORS` handwritten and isolated in `src/backend/common/google_calendar.py`.**

Phase 24A-2C.2D.4 is complete as an assessed no-implementation closeout.

## 13. Application source and test impact

- **Zero application source code changes.** `src/backend/common/google_calendar.py` remains byte-identical to commit `6ec161d47b97881fcdfc13727859f8a47c00bfc1`.
- **Zero test changes.** All 117 backend pytest tests remain passing.

## 14. Validation results

| Validation Suite | Result | Notes |
|---|---|---|
| Shared constants validator | **18/18 passed** | `node shared/validate-constants.mjs` |
| Shared adapter validator | **8/8 passed** | `node shared/validate-contract-adapters.mjs` |
| Generated backend metadata tests | **6/6 passed** | `test_phase24a_generated_service_types.py` |
| Service duration parity tests | **59/59 passed** | `test_phase24a_service_duration_contract_parity.py` |
| Calendar hardening regression | **18/18 passed** | `test_r7d_calendar_hardening.py` |
| All-day calendar regression | **12/12 passed** | `test_r6g_calendar_all_day.py` |
| Multi-day jobs regression | **22/22 passed** | `test_r7e_multi_day_jobs.py` |
| **Combined affected backend suite** | **117/117 passed** | All 5 test files pass cleanly |
| `git diff --check` | **Clean (0 errors)** | Zero formatting or trailing whitespace issues |

## 15. Deployment and existing-event implications

- Zero deployment impact. No backend Lambda, web asset, or mobile adapter changed.
- Zero existing-event impact. Event creation and update formatting remain unchanged.
- No production-data access or Google Calendar API calls occurred.

## 16. Risks and rollback

- **Risk:** Zero. No application code, contracts, or generated adapters were changed.
- **Rollback:** Documentation-only. Revert documentation additions if closeout is cancelled.

## 17. Approval gates

This local closeout does not authorize staging, commit, push, backend packaging, deployment, production-data access, Google Calendar API invocation, or multi-tenant configuration. Commit and push require a separate Matthew decision. Deployment requires a separately reviewed plan and explicit approval.

## 18. Remaining deferred work

- Backend service-identifier acceptance policy;
- production assessment;
- normalization and migration/deprecation;
- existing-event resynchronization;
- tenant-configurable calendar preferences;
- backend deployment review.

The planned Phase 24A-2C.2D backend service-metadata stream is locally complete across all four subphases (2D.1 parity/hardening, 2D.2 generated adapter, 2D.3 duration/name wiring, 2D.4 color assessment closeout).

## 19. Final status

**PHASE 24A-2C.2D.4 ASSESSED / NO IMPLEMENTATION RECOMMENDED / GOOGLE-SPECIFIC COLOR MAP REMAINS ISOLATED IN CALENDAR RUNTIME / CONFIGURABLE COLOR POLICY DEFERRED / NOT DEPLOYED**

**Phase 24A-2C.2D:** **PHASE 24A-2C.2D LOCALLY COMPLETE / 2D.1 PARITY AND VALIDATOR HARDENING COMPLETE / 2D.2 GENERATED BACKEND METADATA COMPLETE / 2D.3 CALENDAR DURATION AND FRIENDLY-NAME WIRING COMPLETE / 2D.4 ASSESSED WITH NO IMPLEMENTATION RECOMMENDED / NOT DEPLOYED**

**Phase 24A-2C.2:** **PARTIALLY COMPLETE LOCALLY / 2C.2A COMPLETE / 2C.2B LOCALLY COMPLETE FOR APPROVED FRONTEND SCOPE / 2C.2C COMPLETE / 2C.2D LOCALLY COMPLETE / NOT DEPLOYED OR DISTRIBUTED**
