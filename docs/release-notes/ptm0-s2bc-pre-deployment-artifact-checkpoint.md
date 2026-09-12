# PTM0-S2B + minimal S2C pre-deployment artifact checkpoint

Date: 2026-09-12

Disposition: **`PTM0_S2BC_ARTIFACTS_INDEPENDENTLY_APPROVED` — NOT YET AUTHORIZED FOR DEPLOYMENT**

This is a documentation-only checkpoint. Preparing it performed no deployment,
artifact upload, artifact rebuild, production AWS access, CloudFront invalidation,
Lambda update, Terraform operation, provider/secret access, or runtime/test source
modification. The isolated release branches were not pushed. `main` remained
`c092ed25de983a50982ea45fd5abbb29bf0a2fb3`; the two pre-existing untracked S2A.2d
review documents remained untouched and excluded.

PTM-0 overall remains **INCOMPLETE**. S2B/S2C artifacts are independently approved
but undeployed; production acceptance is a separate authorization.

---

## Authoritative release identities

### Backend (PTM0-S2B) frozen source and artifact

| Item | Value |
|------|-------|
| Branch (isolated, unpushed) | `release/ptm0-s2bc-backend-reconcile` |
| Commit | `414312a1caf91b03dcce7bc093d3c0ae579c9888` |
| Tree | `86602e6084748f49f3439a7498722bc218d9d7c7` |
| Parent deployed source (S2 RC1) | `b32b374e45cac09dc7006047954ff60c041b0bf0` |
| Canonical artifact | `scratch/ptm0_s2bc_rc/package/ptm0-s2b-414312a-canonical.zip` |
| ZIP SHA-256 | `38B02A3D0B5CE2F6303129D1499C55D66253995A0E62212C525F1A5C1555B7D2` |
| ZIP size (bytes) | `145451` |
| Entry count | `41` |
| Content-manifest SHA-256 (LF-normalized) | `52C27CFBD625635FC7131011755EB73396C2049DD206A35B707C3CA9ED5A2513` |
| Deployed backend rollback ZIP SHA-256 (S2 RC1) | `0849407128C4ADC85F0DB5B6A4BEB78A28E8F09EAA600B4AD10C7167DA421954` |

Exact five changed runtime entries versus the deployed S2 RC1 package (0 added,
0 removed, exactly 5 content-changed):

1. `common/calendar_metadata.py`
2. `common/google_calendar.py` — content delta is only the approved
   `_refresh_bound_tokens` persistence-failure guard (single hunk); no
   scheduling/service/event-ID/window change.
3. `handlers/admin_handler.py`
4. `handlers/google_auth_handler.py`
5. `handlers/platform_handler.py`

Backend validation record (retained evidence; not re-executed for this checkpoint):

- reconciled backend candidate: `641 passed, 0 failed, 0 skipped, 0 external transport attempts`
- independent reconciliation-touched verification: `236 passed`
- package-focused S2B security: `135 passed` (S2B.1 `40`, S2B.2 `64`, S2B.3 `31`)
- `13/13` Lambda entry-point cold imports from the extracted package only (no fallback to main/worktree)
- `41/41` package Python files syntax-validated
- package contains zero unexpected entries (no tests/docs/scratch/.git/bytecode; no absolute/`..` paths)
- exact five-entry runtime delta independently verified; canonical build is content-manifest deterministic (ZIP-container byte identity was also observed on repeat build but is not the canonical contract)

### Frontend (minimal S2C) frozen source and artifact

| Item | Value |
|------|-------|
| Branch (isolated, unpushed) | `release/ptm0-s2bc-web-reconcile` |
| Commit | `709f7cf1e55bba4b3b176c10fc83861f9917559e` |
| Tree | `841f26625703da8efba45b962b183d91ebc3651f` |
| Parent deployed source (PTM-3D.1 web) | `3025f2f1e3991f990d0d4adde79b910e955fd6d1` |
| Artifact directory | `scratch/ptm0_s2bc_rc/web/dist/` |
| Build-manifest SHA-256 | `2EF7F45902FF9DE2F865B3AF6EB217EFF42D9F25573B5E3F4887D181934CEBE6` |
| index.html SHA-256 | `7546B2CCC8B7903CA0D4F7487803F8A69DF57E49F6591A84381A235C3F5A73A7` |
| Primary JS | `assets/index-D3a5IJFf.js` |
| CSS | `assets/index-BroXJAxV.css` |
| Recorded deployed rollback JS | `assets/index-CdPio7XK.js` |

Frontend validation record (retained evidence; not re-executed for this checkpoint):

- Codex isolated candidate: `270 passed`
- Kiro UNKNOWN focused: `9 passed`
- Kiro isolated discovered suite: `174 passed`
- artifact inventory: `11 files`, total `4,439,958` bytes; build structure validated
- generated JS independently confirmed to contain the approved S2C `UNKNOWN` behavior
- CSS `assets/index-BroXJAxV.css` is byte-identical to the recorded deployed baseline
- no lockfile/source mutation during `npm ci` + `vite build`
- commit differs from the web baseline in exactly two files:
  `web/src/components/AdminDashboard.jsx`, `web/tests/GoogleCalendarUnknownStatus.test.jsx`

---

## Deployment contract

1. S2B backend and S2C frontend are **separate release artifacts**.
2. They are considered production-ready **only together**.
3. Required deployment ordering:
   - A. Deploy the frontend S2C artifact first.
   - B. Verify the frontend artifact/publication identity.
   - C. Deploy the backend S2B artifact second.
   - D. Verify all 13 Lambda `CodeSha256` / update status.
   - E. Production acceptance remains **separately authorized**.
4. The backend MUST NOT deploy first: the currently deployed frontend does not
   explicitly represent the new truthful `UNKNOWN` provider status.
5. The frontend S2C build is backward-compatible with the currently deployed
   backend and can therefore safely precede backend activation.
6. Backend and frontend **rollback boundaries remain separate**.
7. The web must not be rolled back to a pre-`UNKNOWN` build while S2B is active.
8. Backend code rollback does **not** reverse consumed OAuth transaction records,
   provider-state writes, or other persisted state changes. No automatic data
   repair is part of rollback.

---

## Current project status

| Item | Status |
|------|--------|
| S2A.3 | Deployed; not fully production-accepted |
| S2D.1 | Deployed; not fully production-accepted |
| S2B.1 | Complete |
| S2B.2 | Complete |
| S2B.3 | Complete |
| S2B integrated implementation | Independently approved |
| Minimal S2C `UNKNOWN` compatibility | Complete and independently approved |
| Reconciled backend source | Independently approved |
| Reconciled frontend source | Independently approved |
| Backend artifact | Independently approved |
| Frontend artifact | Independently approved |
| Production deployment | **NOT YET AUTHORIZED** |
| Production acceptance | PARTIAL / PRELIMINARY — P1 only |
| P2–P5 | Deferred / unexecuted |
| S2D.2 | Not started |
| S2E | Not started |
| F02 | **INCOMPLETE** — S2B/S2C address the F02 Google-fallback / fail-open availability paths at the source/artifact level, but F02 closure requires the separately authorized coordinated deployment and production acceptance, which have not occurred |
| PTM-0 | Incomplete |

---

## Next recommended action

Obtain explicit Matthew authorization for the coordinated S2C→S2B deployment
(frontend first, backend second) per the deployment contract above. No deployment,
upload, Lambda update, Terraform operation, CloudFront invalidation, or production
acceptance is authorized by this checkpoint.
