# PTM0-S2A.2a — Production ownership inventory and proposed migration plan

Date: 2026-09-04; initial known-key reads completed by 07:44 America/New_York.
Authorized inventory-completion scan: 11:53:06–11:53:07 UTC (07:53 EDT).

Disposition: **PTM0_S2A2A_INVENTORY_AND_MIGRATION_PLAN_READY_FOR_INDEPENDENT_REVIEW**

Status: **READ-ONLY INVENTORY COMPLETE / PROPOSED MIGRATION ONLY / NO MUTATIONS**

This completion supersedes the prior inventory-blocked disposition. Matthew
explicitly authorized the bounded metadata-projected scan. The recommended
no-backfill option below requires independent ratification of a narrow S2A.1
contract amendment; inventory readiness does not approve that amendment or
authorize migration, IAM changes, implementation or deployment.

## Checkpoint and approved contract

Matthew reports independent approval of S2A.1:
`PTM0_S2A1_INDEPENDENT_OWNERSHIP_CONTRACT_APPROVED`.
The approved equality is resolved tenant = tenant metadata owner = secret
resource `CompanyId`; key/value comparisons are exact and case-sensitive.
Secret naming is not ownership evidence. See the
[ownership design](ptm0-s2a1-provider-ownership-contract-migration-design.md).

Starting branch for both passes: `main`; HEAD and local `origin/main` both
`1cca9dd1cca9be3a39257f4d3c11ed7de4c53ac3`.
Tracked worktree clean; index and stash empty. The initial pass began with three
untracked review documents and created this fourth document. The completion
pass began with the expected four and modifies only this document. No fetch,
commit, push or branch change occurred.

## Scan authorization, bounds and completeness

The initial two direct reads did not establish the population.
`modules/data/main.tf` defines no tenant-catalog index;
the existing `_handle_list_tenants` in `src/backend/handlers/platform_handler.py`
enumerates tenants by scanning the shared data table. Invoking that endpoint
would not avoid the same underlying scan.

Matthew's follow-up explicitly resolved this scope boundary. One bounded scan
traversal was executed via boto3, not the application endpoint:

- Table `togs-and-dogs-prod-data`, region `us-east-1`.
- Server FilterExpression: `begins_with(#pk, :tenant) AND #sk = :metadata`.
- Names: `#pk=PK`, `#sk=SK`; values: `:tenant={S:TENANT#}`,
  `:metadata={S:METADATA}`.
- ProjectionExpression:
  `#pk,#sk,company_id,calendar_secret_ref,calendar_provider,calendar_enabled`.
  The last two fields are necessary to detect enabled/derived bindings without
  an explicit ref; no labels, contact details, workflow payloads or other tenant
  attributes were projected.
- ConsistentRead true; Limit 100 evaluated items per API request. Maximum 100
  requests / 10,000 evaluated items; elapsed-time guard 120 seconds checked
  before each request, with 5-second connection/15-second read timeouts. A
  current request can finish beyond the elapsed guard; there is no infinite loop.
- SDK retries disabled (`total_max_attempts=1`). LastEvaluatedKey was passed
  only in memory, never displayed or persisted. Repeated cursor, malformed
  identity/field, duplicate metadata, timeout/cap or API error stops with a
  sanitized failure category and no successful completeness claim.
- Returned identifiers were validated against the exact tenant key/owner;
  only sanitized field-presence/configuration facts were printed.

Result: **10 Scan calls, 996 evaluated table items, 2 returned tenant metadata
records; final LastEvaluatedKey absent**. Filtering still evaluates underlying
table items; it did not return raw customer/application records. All pages were
exhausted well below the bounds. Complete observed tenant population is primary
and Alpha, with no other metadata record matching the canonical schema.

This is a completed point-in-time traversal, not a transactionally isolated
table snapshot or a guarantee against subsequent concurrent changes. Exact
inventory/binding preconditions must be rechecked before any approved mutation.
The unique-secret population below is all secrets referenced/default-resolved
by this tenant inventory, not a list of every secret in the AWS account.

## AWS identity and metadata anchor

Successful STS identity: account `358604342897`, assumed SSO role
`AWSReservedSSO_AdministratorAccess_11c170f9e933c874` (session name omitted).
No credentials were displayed or inspected. The initial sandboxed identity
attempt could not find the profile; a path-existence check was access-denied.
The same identity check succeeded with approved elevated execution. No SSO
login, credential-file content read or configuration modification was performed.

Projected GetFunctionConfiguration for `togs-and-dogs-prod-google-auth` returned:

- Table: `togs-and-dogs-prod-data`.
- Role: `arn:aws:iam::358604342897:role/togs-and-dogs-prod-lambda-exec`.
- Token secret reference: the full ARN designated **S1** below.

Only those fields and FunctionName were output, not the full environment.

**S1 exact token secret:**
`arn:aws:secretsmanager:us-east-1:358604342897:secret:togs-and-dogs-prod/google/user-tokens-0zvNfK`

DescribeSecret confirms S1 exists, with name
`togs-and-dogs-prod/google/user-tokens`, no returned deletion date and no returned
OwningService. GetResourcePolicy returned no ResourcePolicy field. No value or
secret-version data was requested.

## Complete sanitized tenant/provider inventory

Both initial GetItem calls and the completion Scan used ConsistentRead and
projected only the six binding fields listed above. Their observations agree.

| Tenant | Metadata owner | Explicit provider/enabled/ref | Reference form / resource | Classification |
| --- | --- | --- | --- | --- |
| `tog_and_dogs` | Exact match; existing `TENANT#tog_and_dogs / METADATA` | All three calendar fields absent (not explicit NULL) | Derived/default runtime selection; deployed environment locator is full ARN S1 | `UNTAGGED_BUT_PROVEN_BY_AUTHORITATIVE_PROVENANCE`; NOT steady-state PROVEN until tagged and verified |
| `test_tenant_alpha` | Exact match; existing `TENANT#test_tenant_alpha / METADATA` | All three calendar fields absent (not explicit NULL) | Absent; source-derived unconfigured provider; no secret selected or described for Alpha | `UNCONFIGURED` |

Primary provenance is not its name: Release 21F explicitly records the existing
global token store as belonging to primary, the only calendar-enabled tenant,
and preserves that association in its migration strategy. Release 21H records
primary calendar compatibility and Alpha unconfigured with no token migration
or tenant-field backfill. Current source preserves that exact fallback, live
Lambda configuration identifies S1, and live primary metadata has the correct
owner with no overriding reference. These together support the existing
assignment; complete metadata traversal found no other tenant alias/reference
to S1. This does not inspect or prove upstream token contents.

Sources:
[21F](../planning/release-21f-google-per-tenant-token-isolation-plan.md),
[21H](../release-notes/release-21h-google-per-tenant-token-isolation-production-validation.md),
`src/backend/common/google_calendar.py:42`,
`src/backend/common/calendar_metadata.py`, `infra/prod/main.tf`,
`modules/secrets/main.tf`.

S1's complete returned tag set:

| Key | Value |
| --- | --- |
| Project | TogsAndDogs |
| Company | USMissionHero |
| ManagedBy | terraform |
| CostCenter | ClientBillable |
| Repo | togs_and_dogs_website |
| Environment | prod |
| Client | TogAndDogs |
| Application | PetScheduling |
| BillingModel | PassThrough |

`CompanyId` is absent, not empty or conflicting. Generic Company/Client tags
are not tenant-owner proof. No new live ownership vocabulary was observed on S1.

### Counts and coverage

- Existing production tenants in completed canonical metadata inventory: **2**.
- Explicit provider configuration: **0**.
- Effective legacy Google bindings: **1**, primary.
- Explicit metadata secret refs: **0**; effective token refs: **1**.
- Unique referenced/default-resolved token secrets: **1**, S1, confirmed to exist.
- CompanyId coverage: **0/1**; proposed new owner tags: **1**.
- Unconfigured tenants: **1**, Alpha.
- Ambiguous/conflicting/duplicate/shared bindings: **0** in complete inventory.
  No sharing permission is inferred.
- Explicit full ARN / partial ARN / name-path references: **0 / 0 / 0**.
- Noncanonical explicit references: **0**. Primary's legacy default locator
  remains valid; no renaming requirement is introduced.
- Alpha has no explicit provider binding and no source-default token binding.
  This is metadata/configuration evidence, not a provider API validation.

## Current IAM evidence and exact conditional delta

Role has no inline policies and no returned PermissionsBoundary. Seven attached
managed policies were read at their current default versions:

| Policy name | Version |
| --- | --- |
| AWSLambdaBasicExecutionRole | v1 |
| togs-and-dogs-prod-dynamodb-access | v2 |
| togs-and-dogs-prod-cognito-admin | v4 |
| togs-and-dogs-prod-ses-access | v1 |
| togs-and-dogs-prod-lambda-sfn-start | v1 |
| togs-and-dogs-prod-lambda-invoke | v1 |
| togs-and-dogs-prod-google-secrets | v2 |

None grants DescribeSecret, TagResource, UntagResource or wildcard Secrets
Manager actions. Existing `togs-and-dogs-prod-google-secrets` v2 grants Get/Put
SecretValue to exactly S1 and the shared client credential resource
`arn:aws:secretsmanager:us-east-1:358604342897:secret:togs-and-dogs-prod/google/client-creds-TBSqWN`.
Its separate Postmark statement grants GetSecretValue only; leave it unchanged.
There are no tag-based conditions in these attached policies. No secret resource
policy was returned for S1. This is not an account-wide audit of SCPs, all roles,
indirect invocation privileges or every possible policy denial.

Proposed delta, now reconciled to the complete inventory:

- Policy ARN: `arn:aws:iam::358604342897:policy/togs-and-dogs-prod-google-secrets`.
- Add one separate Allow statement: Action `secretsmanager:DescribeSecret`,
  Resource exactly S1. Preserve every existing statement unchanged.
- Do not simply add DescribeSecret to the existing two-resource statement:
  that would unnecessarily include the shared app-client credentials.
- Source representation is `aws_iam_policy.google_secrets_access` in
  `modules/iam/main.tf`; the role is shared in repository wiring and was
  confirmed live for google-auth. The permission change does not require code,
  environment or tenant-resolution changes.
- Wildcard resource permissions are avoidable for the observed binding. If
  complete inventory identifies another legitimate token secret, independently
  review its exact ARN; do not generalize to a prefix wildcard.
- Do not add a primary-owner tag condition to the shared role or treat IAM
  resource tags as a substitute for per-request tenant equality. Avoid bootstrap
  conditions that prevent describing untagged resources or performing rollback.
- Runtime receives no Tag/Untag rights. Future migration Tag/Untag must use a
  separately authorized operator identity with exact-resource/key scope. The
  inspected Lambda role lacks direct grants today; this does not prove that
  every other account principal is restricted appropriately.

Effective DescribeSecret access and source/IAM review must be independently
verified before enforcement. No IAM simulation or modification was performed.

## Proposed S2A.2b mutation package — NOT AUTHORIZED

### A. Owner tag (one provenance-supported resource)

- Resource: S1 exact ARN above.
- Expected API: Secrets Manager TagResource, adding only
  `CompanyId=tog_and_dogs`.
- Preconditions: complete inventory with no duplicate/cross-tenant binding;
  independent provenance approval; exact live resource/account/region; CompanyId
  still absent; unrelated tags unchanged; no deletion pending; no competing
  ownership convention; writer freeze and explicit Matthew mutation approval.
- Preserve the existing nine tags. Do not retag client credentials, Postmark,
  other shared resources or Alpha. If a conflicting owner appears, STOP.
- Independently DescribeSecret after tagging and verify exact owner plus all
  preserved tags and resource identity. Bound verification attempts; inconsistency
  holds release. A tag write is not an atomic conditional operation.
- Rollback only under separately approved serialized execution: re-describe,
  require CompanyId still equals the migration-written value and no intervening
  changes, then UntagResource for only `CompanyId` on S1; re-describe and compare
  the original nine-tag preimage. Never remove an owner tag this migration did
  not add. After enforcement deployment, do not untag automatically.

### B. Backfill decision — recommend zero DynamoDB mutations, pending review

Absence of the field alone is not a security justification to backfill it.
Compare two designs explicitly:

| Option | Contract and security | Compatibility / mutation cost |
| --- | --- | --- |
| A: explicit primary ref | Preserves S2A.1 section 3's approved requirement that the metadata row explicitly reference the secret. A full ARN pins resource identity and gives one uniform metadata-based binding model. | One additional conditional DynamoDB field write and inverse; current record has no ref. Required **if that existing explicit-reference requirement is retained**. |
| B: explicit-primary legacy binding | Requires explicitly resolved literal `tog_and_dogs`, an existing matching metadata owner, the reviewed configured legacy resource, and matching CompanyId. The resource tag remains mandatory; the path is never proof. | No DynamoDB write or rename. Retains established primary compatibility but makes trusted deployment configuration, rather than an explicit row ref, the second locator source for this one case. |

**Recommendation: B, as the minimum-mutation proposed contract amendment.** A
backfill is not technically necessary to enforce the three-way identity equality.
It remains necessary under the previously approved stronger explicit-row-ref
rule. Independent review must explicitly ratify B before using the no-backfill
release path; this report does not silently rewrite the S2A.1 approval.

The proposed B contract must include all of these guards:

1. Only the explicitly and successfully resolved literal primary ID qualifies;
   never use DEFAULT_COMPANY_ID substitution, omitted context, caught resolution
   errors, missing metadata, or Platform Admin status as authority.
2. Require the exact existing primary PK/SK and explicit matching `company_id`.
   No record synthesis. Eligibility/disabled-tenant checks remain independent.
3. Only a genuinely **absent** ref can select this narrow legacy branch. A
   present null/empty/malformed ref or an explicit ref whose ownership fails
   must fail closed, not fall back. Non-primary tenants never use this branch.
4. Resolve the existing trusted deployment locator, currently full ARN S1;
   require its reviewed account/region/resource identity and successful
   DescribeSecret with `CompanyId=tog_and_dogs`. No new hardcoded-name fallback
   or silent acceptance of configuration drift. Ownership failure denies access.
5. Carry the validated full ARN through token operations. No provider/value
   access before binding validation. The primary exception is to locator
   storage only, **never** an exception for an untagged secret.
6. Provenance-laundering wrappers identified in the S2A conflict remain an
   integration gate: common code cannot tell whether an upstream wrapper
   converted failed resolution to primary. Do not approve enforcement until
   caller provenance is reviewed within separately authorized slice boundaries.

Tradeoff: B avoids a data migration but retains two locator sources and therefore
requires explicit tests/configuration governance for the primary branch. A is
more uniform and keeps the exact existing design intact. Neither may infer
ownership from names or bless today's unsafe fallback. Runtime is unchanged now.

If independent review chooses A instead, the separate exact data proposal is:
conditional UpdateItem on `togs-and-dogs-prod-data`, key
`TENANT#tog_and_dogs / METADATA`, SET only `calendar_secret_ref` to full ARN S1,
conditioned on item existence, owner match, absent ref and unchanged calendar
configuration. Its inverse is conditional REMOVE of that field only while its
value and owner remain migration-written/unchanged. No row replacement,
provider enablement, Alpha change or other tenant field change. This alternative
needs its own explicit Matthew authorization and is not included in the preferred
S2A.2b mutation count.

### C. IAM and source reconciliation — SEPARATE APPROVAL REQUIRED

Add only the DescribeSecret statement specified above through a separately
approved IAM policy change; no runtime Tag/Untag grants. Exact proposed new
statement (all existing v2 statements preserved):

```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:DescribeSecret",
  "Resource": "arn:aws:secretsmanager:us-east-1:358604342897:secret:togs-and-dogs-prod/google/user-tokens-0zvNfK"
}
```

The underlying IAM mutation would be CreatePolicyVersion for the named policy,
with the reviewed complete document and SetAsDefault true. Before approval,
re-read v2/default/attachments and policy version capacity; if creation requires
deleting versions, STOP rather than add an unapproved deletion. No role attachment
or environment change is needed. The independent change package must determine
the established managed-source execution mechanism rather than apply current main.

Rollback, under unchanged-policy preconditions, is SetDefaultPolicyVersion back
to recorded v2, leaving the new nondefault version in place (no deletion implied).
If another actor changed the policy/default, STOP rather than revert concurrent
work. Reconcile the corresponding desired source change through its reviewed
process. Do not remove the permission after enforcement deployment automatically.

The tag's desired source state must be resource-specific and preserved through
future infrastructure reconciliation; never put CompanyId in global common_tags.
The later change package must reconcile against the deployed infrastructure
source and ensure secret initialization/version resources are untouched. This
task does not select or execute a Terraform/IAM mutation mechanism, generate a
Terraform plan, or authorize deployment of current main.

### Sequencing and enforcement interlock

Inventory and zero-duplicate checks are complete. Next, independently review the
exact package and ratify B or retain A; then obtain explicit execution approval.
Preferred B package: **one TagResource change + one scoped IAM policy change;
zero DynamoDB changes**, with separately reviewed desired-source reconciliation.
If A is selected, add only its independently authorized conditional backfill.

Before either write, recheck inventory/provenance and exact preimages. Serialize
owner/reference edits, apply only the approved package, independently verify
CompanyId, IAM and the chosen locator contract, and record fresh migration
evidence. No token/provider operation is necessary for this metadata migration.
Stop on any drift, conflict or unexpected permission/source change.

Current S2A.3 deployment interlock: **BLOCKED / NOT SATISFIED**. Unambiguous
inventory and zero duplicates are now evidenced; required tag and DescribeSecret
permission are still absent, the backfill alternative needs explicit design
ratification, and no migration has been executed or independently verified.
The conditions are satisfiable through later approved steps, not satisfied by
this read-only inventory. S2A.2b/S2A.3 and S2B–S2E remain not started.

## Read-only command ledger

AWS CLI `2.22.18`. All production CLI commands used
`--profile usmissionhero-website-prod --output json --no-cli-pager`, except
get-policy version lookup used `--output text`. Regional commands used
`--region us-east-1`. Successful calls were:

1. `sts get-caller-identity --query '{Account:Account,Arn:Arn}'`.
2. `lambda get-function-configuration --function-name togs-and-dogs-prod-google-auth`
   with query `{FunctionName:FunctionName,Role:Role,DataTable:Environment.Variables.DATA_TABLE_NAME,TokenSecret:Environment.Variables.GOOGLE_USER_TOKENS_NAME}`.
3. `dynamodb get-item --table-name togs-and-dogs-prod-data --consistent-read`
   with key `PK={S=TENANT#tog_and_dogs},SK={S=METADATA}` and projection
   `PK,SK,company_id,calendar_provider,calendar_enabled,calendar_secret_ref`.
4. Same GetItem with key `PK={S=TENANT#test_tenant_alpha},SK={S=METADATA}`.
5. `secretsmanager describe-secret --secret-id <S1>` with query
   `{ARN:ARN,Name:Name,Tags:Tags,DeletedDate:DeletedDate,OwningService:OwningService}`.
6. `iam list-attached-role-policies --role-name togs-and-dogs-prod-lambda-exec`.
7. `iam list-role-policies --role-name togs-and-dogs-prod-lambda-exec`.
8. `iam get-role --role-name togs-and-dogs-prod-lambda-exec` with query
   `Role.{Arn:Arn,PermissionsBoundary:PermissionsBoundary}`.
9. `iam get-policy --policy-arn arn:aws:iam::358604342897:policy/togs-and-dogs-prod-google-secrets`
   with query `Policy.{Arn:Arn,DefaultVersionId:DefaultVersionId}`.
10. For each of the seven attached policies in the table: `iam get-policy
    --policy-arn <exact attached ARN> --query Policy.DefaultVersionId`, then
    `iam get-policy-version --policy-arn <same ARN> --version-id <returned version>
    --query PolicyVersion.Document`. Customer policy ARNs use the account above;
    basic logging uses `arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole`.
11. `secretsmanager get-resource-policy --secret-id <S1>`.

Two earlier JSON-quoted GetItem attempts failed local CLI argument parsing;
neither reached DynamoDB. Corrected shorthand calls above succeeded. The initial
sandbox STS failure also did not establish an AWS identity.

Completion-pass operations:

1. Local `python -c` boto3 availability/executable checks. The first elevated
   `python` invocation resolved to a nonworking Windows alias and made no API
   calls. Retried with the verified executable
   `C:\Users\mattn\Desktop\lambda_package\python.exe`, running an in-memory
   inventory-only script; no application modules were imported or files created.
2. STS GetCallerIdentity via boto3, account checked against `358604342897` before
   any Scan. Printed only account and execution timestamps, no credential/session
   data. boto3 Session profile/region match the CLI profile/region above.
3. Exactly ten DynamoDB Scan calls with the parameters/bounds and sanitized
   output described in the scan section. Final continuation key absent.
4. Repeated projected GetFunctionConfiguration for google-auth, returning only
   FunctionName, Role and TokenSecret (unchanged S1/role).
5. Repeated projected DescribeSecret for S1 (same nine tags, CompanyId absent).
6. Repeated GetPolicy for the exact Google policy (default still v2). Prior
   seven-policy inspection remains the IAM evidence; no claim of a fresh audit
   of every account policy or SCP is made.

No mutation API, provider endpoint, Lambda invocation, Terraform/state read,
secret-value API, AWS debug output or raw credential/session inspection occurred.

## Final local scope

Only this Markdown record was updated in the completion pass (created during
the initial pass). The three prior review documents remain
unchanged. Runtime/tests/infra/application files: unchanged. No tests/imports,
packaging, staging, commits or pushes. Production writes, secret-value access,
Google/provider API access, Terraform operations and deployments: **ZERO**.

Ending HEAD/origin/main unchanged at the checkpoint; tracked worktree/index
clean, stash empty; four intentional untracked review documents. F02 remains
unresolved; S1 complete; PTM-0 incomplete. Inventory scope blocker is resolved.
Stop for independent review; do not execute any proposed mutation.
