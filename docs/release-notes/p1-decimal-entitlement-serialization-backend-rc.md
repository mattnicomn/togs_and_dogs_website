# P1 Decimal Entitlement Serialization Backend RC

**Date:** 2026-08-31

**Canonical reconciliation date:** 2026-09-01

**Status:** SUPERSEDED BY SUCCESSFUL P1 BACKEND DEPLOYMENT AND PRODUCTION ACCEPTANCE

**Production status:** DEPLOYED / PRODUCTION ACCEPTANCE PASS / COMPLETE

> **2026-09-01 reconciliation:** The canonical package described below was
> subsequently deployed through the exact approved saved plan. Production is
> healthy on `CodeSha256 K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=`,
> API Gateway remains `prod -> atxpw3`, and Terraform state is serial `516` on
> the unchanged lineage. Read-only post-deployment validation found no Decimal
> serialization recurrence. A later Matthew-approved guarded real Web/API
> execution emitted a valid non-bypass `max_staff` limit decision containing
> numeric Decimal-backed `max_allowed=1`, with zero persistence or side
> effects. Final disposition: `P1_PRODUCTION_DECIMAL_ACCEPTANCE_PASS`; see
> `p1-decimal-entitlement-serialization-production-acceptance.md`.

## Exact baseline and candidate

- Deployed backend source/package baseline:
  `46ab28779cc3647ef3664f84ee793cf4a6e8539d`
- DOMAIN-1 RC evidence head:
  `5de430cb41536c1fab217309c10e1e4f78bb98ff`
- Deployed DOMAIN-1 package SHA-256:
  `5BD46E19ACBA6AB418352517C19D4BF62BFEC7263B704136593F2B04369AC558`
- P1 repository source commit:
  `e4d0d42fc5e352a7526012513f37ddb0026fc674`
- Isolated RC branch:
  `release/p1-decimal-entitlement-backend-rc`
- Isolated runtime/test commit:
  `97cb6ebffe8b727e7a6833988107a40e65ba2105`
- Candidate backend tree:
  `8647798706f96a50e183aacd05e2cd3e2ae3f0c6`

The authoritative DOMAIN-1 deployment record identifies `46ab287...` as the
exact package/plan source and `5de430c...` as its later evidence head. The
approved deployment applied only 13 shared-package Lambda code updates and
placed all 13 functions on the package above. All subsequent repository
release records through this checkpoint describe Web deployment, read-only or
controlled validation, cleanup, documentation, or the not-deployed P1 fix;
none records a later backend package deployment.

Production API context remains repository-documented as REST API `a022yxuiue`,
stage `prod`, deployment `atxpw3`. No AWS call was made to rediscover it.

## Main versus deployed backend drift

Current `main` at `e4d0d42...` differs from the deployed backend source in 13
runtime paths. The RC does not inherit this drift.

| Runtime path | Classification |
|---|---|
| `src/backend/common/entitlement.py` | P1 approved delta |
| `src/backend/common/billing.py` | Intentionally not deployed Preview V1 tenant-onboarding work |
| `src/backend/common/tenant_catalog.py` | Intentionally not deployed Preview V1 tenant-onboarding work |
| `src/backend/common/tenant_provisioning.py` | Intentionally not deployed Preview V1 tenant-onboarding work |
| `src/backend/common/tenant_read_adapter.py` | Intentionally not deployed Preview V1 tenant-onboarding work |
| `src/backend/handlers/platform_onboarding_handler.py` | Intentionally not deployed Preview V1 tenant-onboarding work |
| `src/backend/common/check_in.py` | Intentionally not deployed Ryan scheduling/workflow work |
| `src/backend/common/generated_service_types.py` | Intentionally not deployed generated service metadata and Ryan scheduling work |
| `src/backend/common/google_calendar.py` | Intentionally not deployed Ryan scheduling/Calendar work |
| `src/backend/common/service_contract.py` | Intentionally not deployed Ryan scheduling contract work |
| `src/backend/handlers/intake_handler.py` | Intentionally not deployed Ryan booking-window work |
| `src/backend/handlers/job_handler.py` | Intentionally not deployed Ryan child-occurrence scheduling work |
| `src/backend/handlers/review_handler.py` | Intentionally not deployed Ryan child-Calendar handoff work |

The reviewed P1 tests and documentation are repository evidence, not
production runtime behavior. No relevant runtime difference is uncertain.

## Exact RC composition

The RC was created in a fresh isolated worktree from `46ab287...`. It applies
the independently reviewed P1 change and its three exact test-file changes.
Relative to deployed baseline, runtime source has exactly one changed path,
two inserted lines, and one replaced line:

- `src/backend/common/entitlement.py`
  - import the existing `common.response.DecimalEncoder`;
  - serialize decision logs with
    `json.dumps(log_payload, cls=DecimalEncoder)`.

There is no second serializer and no handler, tenant-resolution, entitlement,
comparison, message, failure-mode, or enforcement change.

## Dependency and package compatibility

The deployed baseline already contains `common.response.DecimalEncoder` with
whole `Decimal` values encoded as JSON integers and fractional values encoded
as JSON numbers. The isolated import resolves from the RC source successfully.
There is no circular import, external dependency, requirements, Lambda layer,
environment-variable, Terraform, API Gateway, or package-path change.

All 40 tracked backend Python files compile.

### Canonical production packaging boundary

The repository's canonical production path is Terraform data source
`archive_file.backend_zip` using `hashicorp/archive` v2.7.1. It reads
`src/backend`, applies the committed cache/bytecode/log/temp excludes, writes
`infra/prod/backend.zip`, and supplies `output_base64sha256` to all 13 Lambda
resources. No separate repository backend-packaging script exists.

The provider configuration guarantees the intended input selection but does
not normalize ZIP timestamps or other container metadata. Prior repository
packaging reviews explicitly record that binary checksums can vary across
builds or environments because of timestamps, OS metadata, and ordering. A
canonical production artifact therefore cannot be claimed from a local
normalized ZIP without inventing semantics different from the Terraform
archive-provider process. The future production artifact must be generated
and hashed during a separately approved deployment-planning stage using that
canonical process.

### Corrected local package evidence: Method B

The existing ZIP is classified as a **LOCAL REVIEW SNAPSHOT**, not a
deterministic or production artifact:

- original snapshot: 40 entries, 139,002 bytes, SHA-256
  `4C170DE38987D827DB94164BAE599C13497263EC5916FDA8109AB86B08F4E0FC`;
- independent rebuild: the same 40 entry paths and contents, 139,002 bytes,
  SHA-256
  `3DB42A6285FCB20F833E23D45A605299ED2EBA56BD028E2669B713E71C5B4761`;
- byte-level difference: ZIP entry timestamps/container metadata differed for
  the 40 entries; entry paths and file contents did not differ.

Each ZIP SHA-256 identifies only that exact container snapshot. Repeated
builds may differ at the byte level even when source content is unchanged.
At that review checkpoint, no normalized ZIP was created because a custom
normalized builder would have been reproducible source evidence only and
would not represent the canonical Terraform artifact. The later reconciliation
below uses the configured Terraform archive provider rather than a custom ZIP
builder.

Content verification found exactly 40 tracked Python entries, with no missing
or unexpected paths. Thirty-nine entries matched the isolated RC worktree
byte-for-byte; the remaining entry matched after line-ending normalization
only. Thus all 40 entries are source-equivalent, and the independent rebuild
had the same entry contents. Candidate-versus-deployed runtime comparison
still identifies only `common/entitlement.py`, proving that no undeployed
Preview V1 or Ryan scheduling/workflow source version leaked into the package.
There are no tests, docs, secrets, bytecode, caches, logs, Terraform plan
files, non-Python artifacts, or nested ZIPs.

The stable evidence below is the sorted UTF-8 manifest
`path<TAB>SHA256(entry bytes)<LF>`. Its SHA-256 is
`87B4215623916219D8DE115844EB38AE3CD27C44C50549F88590F8B91632B904`.
Because entry contents were identical, it applies to both local snapshots
independently of their ZIP timestamps.

```text
common/__init__.py	E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855
common/audit.py	376BA74AD9ABEBE3B99E1B39AFEEC25F928573B125A3390A70A2AE6507E82A98
common/auth.py	96067137559978770AEE1460B2AEFDF29C8F120B61F54940412A44176B478A53
common/billing.py	C66225317D7BB3971333880B40680D284531E321A8FF099D48D62C5655042EB9
common/calendar_metadata.py	5EF6D481FB265CE2B0FB08476270E5610CB5A7F6D423635835FFFAF33D102F8B
common/cascade.py	48169C91A0DA5CAD527B92CD3554B6578EB85E844828A396B66B0646D3B6B3E3
common/client_profile.py	43413ACA44AE1B4AEA3113F9CCD4D0A1BC16D5D7F9C87C24924BFC1E49F12BE7
common/client_view.py	A957DF352EED81363681AA710BCB0F558C7800AB38EA3C3CEA11E648DB8D8403
common/db.py	66BD58DB7EA6CB1D26A19AC5958DFF124990FAD76C9C1CE4C5B3B391F25EBB58
common/email.py	F3451D90F4F9EDBB58FA8BC71069F3C81C8D3192B4640127B117E41BE55A3D2A
common/entitlement.py	4FB90DCEE5C297FBC9B4115B82C0591454FD51F682D0BBF2DF4A64FDA5FA2973
common/google_calendar.py	E590E16F762265BDED63D347C73EE96AA1C8545190455F89A5ECEED9DFB47170
common/notifications/__init__.py	08D89D4CF1629E2126CA2AA0D3927A9D0A998340BEEDBDEB5B1EFADE45DAB88D
common/notifications/config.py	9D968B530F030231B049653603E8A2AF76BE5854408735F2C19EB99DEC3104AE
common/notifications/postmark_client.py	D9890AC70DB321007553D9CC7C7CBA7A7C18EEEE1CDF7270378B4330D0C6BDA3
common/notifications/resolver.py	F46003B442664F7081BE9E8D990D4FBBB331D78933D79ABE3BC718E6DFB89865
common/notifications/service.py	3195CB5E70D1861C2BF34F4684E73C5CB07D796E44628B90EA29F8823F24C08B
common/notifications/ses_client.py	C8F8DF23B36685816C91805275EE67CB67AC65BDDFD4982081C2F855663469EA
common/notifications/suppression.py	E2D72976D93327A73A9495B666D650044D5C612F6FF465A6042F870512F19A63
common/notifications/templates.py	CE8719937272ABF8E7569BC78DFBBCE04869AE0C3DC41AEADAE24B7D078DF7C6
common/pet_profile.py	51546B728FEC95BA734DF05A5FC1D7D811633C39D4ED07668CB57DBFC5EABF02
common/protected_accounts.py	61A09AE27B728485C78C1925C0C25B9DE20D35D4117151E3A4CC5552C7CBFD9F
common/response.py	A728474E1EEA2F779542A6F218998BF731917E42045059513858CA0926EF9BB4
common/status.py	D5162C336D12019377C8E100DD63E69C3A46F717F24DDD07CBCD20D05AC1455C
common/stripe_client.py	F2D3168577949E6A4DA56EC18D590FEC6B87A981CB5C124858A32667629B3EA9
common/tenant_route.py	5972D62CEFB7E2AB8C08452B1B4A534E34A1271BD487ECAA7CD76A5A8228A4BF
handlers/__init__.py	E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855
handlers/admin_handler.py	1BC6277D486B418C54270D57E845DDC55B310248C329844C5AF5EC14CC58A292
handlers/assignment_handler.py	58957FA9535B171F655C64A36BE0ECFD929E34CB6FAE3ECEB0C07AC700B4197D
handlers/cancellation_handler.py	E0FC0FFDC00F2BEB9EE0505A1190324D19652ACE545F642E89632B88B5B607A6
handlers/device_handler.py	BDA9B0C8133D04251DA54E9EDDB6D0814D88F80795675B7050CA944DF87F5100
handlers/google_auth_handler.py	1094BAF72969098A4119C59771A60251057A5CFE2069FF8474207098DD0AF94E
handlers/intake_handler.py	24FA7D29769FFA4C9DF3575548F3BE62B72934B435125E215FF3006F948BAD09
handlers/job_handler.py	22E1DD3119105C23A7215495E78960A8A5B63715CC1CF26FEBC9268C4AA62600
handlers/notification_feedback_handler.py	F6B8ED84FFB9ED6FED7E44DBDA19C8AE051FE97DDD4BF7241628AF80EDFA7AC3
handlers/pet_handler.py	B2E924F2CCA413BEB32C8B7E36546AFF4C0B4F4419F0598EB1E5A6865C7823AE
handlers/platform_handler.py	86691A86777472D6CD7A78A6B9FE296B98C265441FFCC391D128432546069B1D
handlers/postmark_webhook_handler.py	BA9C91F0EE301DCB246A00E89954B42C77F44A950E7CD85EB2A5F1A5B1E8459D
handlers/review_handler.py	FE125B55A58CCB1D0DDBAC3DBAFA7E3B583D3089CB9B2CB9CD72F36FA06A885D
handlers/stripe_webhook_handler.py	D617AB27B2B91E6283E85B289714C95869F2B9ABA6974FCB06CDE8EA4CB276F3
```

The snapshot was not committed, uploaded, or used by Terraform. Neither ZIP
hash is represented as an approved production Terraform/archive-provider
artifact.

### Deployment-plan hard stop and canonical reconciliation

The first deployment-planning attempt generated saved plan
`p1-decimal-entitlement-backend-20260831-state513.tfplan`, SHA-256
`156F2CCFD4F58815E018A64B647BC44627573E7ED2F5305A1A67C0EF74CBCAB3`.
That plan is **PERMANENTLY REJECTED / MUST NOT APPLY / MUST NOT REUSE** because
its canonical provider package exposed a source-byte mismatch before the plan
was accepted or reviewed. The rejected plan remains local, ignored, and
uncommitted.

The failed package was 139,515 bytes with SHA-256
`42C3663C1962882DD815CB50B792945D7EB13D167CF59C9AC3B0B82DEC5186A6`
and provider Base64 SHA-256
`QsNmPBliiC3YFctQt5KUXX6xPRZ89Zyaw7C4LexRhqY=`. Its 40-file content manifest
was `E0C7CEDE43E4B1E73BAAE4009D6006E92A22827468AB4975DA72368B16D1A096`.
Only `common/entitlement.py` differed from the approved review manifest: it
was 18,780 bytes with 527 CRLF terminators and four lone-LF terminators.

#### Line-ending source of truth and root cause

- the deployed-baseline Git blob is LF-only: 18,190 bytes / 530 LF;
- the P1 runtime-commit and current-head Git blob is LF-only: 18,253 bytes /
  531 LF;
- `.gitattributes` has no rule for backend Python files; its only line-ending
  rule is the unrelated API semantic JSON file;
- system Git configuration sets `core.autocrlf=true`; `core.safecrlf` and
  `core.eol` are unset;
- therefore Git's repository representation is LF while the established
  Windows worktree representation for backend Python is CRLF;
- `archive_file.source_dir` consumes checked-out filesystem/worktree bytes,
  not raw Git object bytes.

The four lone-LF line terminators were at lines 16, 17, 18, and 86: the import
hunk's two context lines, the new `DecimalEncoder` import, and the changed
`logger.info(json.dumps(..., cls=DecimalEncoder))` line. The P1 patch writer
introduced LF terminators for those hunk lines into an otherwise CRLF Windows
checkout. Normalized text was identical; no code token, indentation, or other
whitespace differed.

Only `src/backend/common/entitlement.py` was mechanically normalized to the
established checkout representation. It is now 18,784 bytes with 531 CRLF
terminators and zero lone LF. The Git-normalized object hash remains the exact
reviewed P1 object, so this worktree-byte correction creates no Git source
content delta. Semantic comparison to deployed baseline still shows only:

- `from common.response import DecimalEncoder`;
- `logger.info(json.dumps(log_payload, cls=DecimalEncoder))` replacing plain
  `json.dumps(log_payload)`.

No other runtime, test, Terraform, Web, Mobile, or infrastructure source was
changed.

#### Canonical provider artifact and manifest policy

The archive was regenerated without a production backend, AWS provider,
remote state, resource block, `terraform plan` command, or apply. An isolated
local-only Terraform fixture evaluated the exact `hashicorp/archive` v2.7.1
data source, production source directory, output path, and exclusion list via
one `terraform test` plan-phase data-source run. A second independent fixture
run confirmed content-level repeatability.

Both provider builds contained exactly 40 expected Python entries, byte-matched
the normalized RC worktree, and contained no tests, docs, secrets, cache,
bytecode, logs, tfvars, plan files, or nested archives. In this environment,
both builds were 139,513 bytes with identical ZIP SHA-256
`2BF654E0FE7EB69DD1752410C2BA77D897655D28BD45E07FD822A7289A933925`
and provider Base64 SHA-256
`K/ZU4P5+tp3RdSQQwrp32JdlXSi9ReB/2CKnKJqTOSU=`. This does not claim ZIP
container byte determinism across environments.

The exact canonical package-entry manifest is
`87B4215623916219D8DE115844EB38AE3CD27C44C50549F88590F8B91632B904`.
It equals the prior review manifest, but is now authoritative for the next
deployment-planning gate because it was independently recomputed from the
configured Terraform provider artifact after worktree normalization—not
because the earlier Git-archive snapshot happened to have that value.
Normalized semantic contents of the rejected and reconciled packages remain
identical.

## Post-reconciliation local validation

- focused P1 Decimal regression selection: 5/5 passed;
- entitlement observability: 6/6 passed;
- entitlement wiring / realistic `max_staff`: 20/20 passed;
- core entitlement enforcement: 9/9 passed;
- relevant active-client/monthly-booking selection: 15/15 passed, with the two
  already documented date-stale baseline tests deselected;
- corrected R11E tenant-enforcement file: 16/16 passed;
- disabled-tenant plus Platform Admin boundaries: 26/26 passed;
- deployed E3A compatibility: 24/24 passed;
- tenant-route plus public-intake boundaries: 49/49 passed;
- isolated import and `DecimalEncoder` resolution: passed;
- all tracked backend Python files: compile passed;
- `git diff --check`: passed.

Existing unrelated baseline classifications remain unchanged. No legacy test
was weakened or altered outside the three independently reviewed P1 test
files.

## Historical pre-deployment release boundary

At this RC checkpoint, the earlier deployment-planning attempt had generated the permanently rejected
saved plan identified above. No `terraform plan` command or production plan was
run during this reconciliation, and no Terraform apply has been run. No AWS
access, Lambda/API mutation, production invocation, production data write,
Cognito, DNS, CloudFront, Postmark, Calendar, Stripe, Mobile, tenant, or B1A
Web/API write-path action occurred in this reconciliation. The RC branch
remains local and is not pushed by this preparation.

At that time, this record established a review candidate rather than production
readiness or deployment approval. The later approved deployment is reconciled
at the top of this document. B1A real Web/API write-path validation remains a
separate approval gate.

## Historical next step

**INDEPENDENT REVIEW OF CANONICAL PACKAGE / LINE-ENDING RECONCILIATION**

Only after independent approval may a brand-new, uniquely named production
Terraform plan be generated. The rejected plan must never be applied or
reused.
