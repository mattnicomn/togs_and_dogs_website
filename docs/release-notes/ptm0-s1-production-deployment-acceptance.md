# PTM0-S1 production deployment and acceptance

Date: 2026-09-03

Status: **PTM0-S1 DEPLOYED / PRODUCTION ACCEPTANCE PASS / COMPLETE**

Authoritative disposition: `PTM0_S1_PRODUCTION_ACCEPTANCE_EVIDENCE_SUFFICIENT`

This closeout completes **F01 / PTM0-S1 only**. It does not complete PTM-0.
F02 remains untouched and unresolved, PTM0-S2 has not started, and the remaining
PTM-0 findings and phases retain their existing approval gates.

## Checkpoints and deployed package

- Authoritative repository `main`: `82a2df808cc028e2000fd7539212dae7c4772244`
- Isolated S1 RC: `c31be0ab6f95ba77707f33980cadc0c998dda6e3`
- Deployed backend `CodeSha256`:
  `kmf9B9gD4pZ1wy1plBDVwSVtAIbNl7ybOdqxjVMemiI=`
- Production Terraform state: serial `519`, lineage
  `7235fddd-c101-fe62-7669-7b7b3d858955`
- Apply result: `0 added / 13 changed / 0 destroyed`, with zero replacements.

The approved isolated package updated the shared code package for the existing
13 Lambda functions. It did not deploy current `main` wholesale. No Lambda
configuration, environment variable, IAM, API Gateway, DynamoDB, Cognito,
tenant-resolution, Google/OAuth, Stripe, Web, Mobile, DNS, or notification
change is part of this release.

## Production acceptance evidence

### Live-proven

- Alpha denies an existing untagged legacy request.
- The primary tenant admits that same legacy request.
- Primary-tenant tagged-list compatibility is preserved.
- Wrong-company records are excluded.
- A 16-read traversal cap returns a generic HTTP 503 response with no partial
  results, continuation cursor, excluded key, or hidden-record metadata.
- Authorized cursor continuation succeeds without skips or duplicates.
- Platform Admin remains separated from tenant-plane authority.

### Offline adversarial coverage

- `NULL`, empty, and malformed tenant tags fail closed.
- Authorized–excluded–authorized ordering preserves safe pagination.
- Client-ID collisions do not cross tenant boundaries.

Focused tests against a package identical to the deployed package passed
`118/118`. Risk-based acceptance did not require a production fixture, and no
production fixture or other production test data was created.

## Preserved boundaries

- `TENANT_RESOLUTION_MODE=multi` is unchanged.
- No additional or second customer tenant was created; the existing internal
  `test_tenant_alpha` tenant remains unchanged.
- F02 is **UNTOUCHED / UNRESOLVED**.
- PTM0-S2 is **NOT STARTED**.
- PTM-0 overall is **INCOMPLETE**.
- Stripe remains sandbox-only.
- No Ryan testing, Mobile, TestFlight, or App Store state changed.

## Final milestone

`PTM0-S1 DEPLOYED / PRODUCTION ACCEPTANCE PASS / COMPLETE`

The next step, if separately authorized, is to scope and independently review
F02 / PTM0-S2. This closeout supplies no authority to start it.
