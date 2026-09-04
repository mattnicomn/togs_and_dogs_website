# PTM0-S2A.2b — Provider ownership metadata and IAM migration evidence

Date: 2026-09-04.

Disposition: **PTM0_S2A2B_MIGRATION_READY_FOR_INDEPENDENT_VERIFICATION**.

Status: **TWO APPROVED PRODUCTION CHANGES COMPLETE / VERIFICATION PASS /
INDEPENDENT REVIEW PENDING / NO APPLICATION DEPLOYMENT**.

## Authority and checkpoint

Matthew explicitly approves only one ARN-scoped DescribeSecret IAM addition,
then one CompanyId tag addition after IAM convergence. Option B is authoritative:
no DynamoDB reference backfill. This does not implement primary compatibility,
start S2A.3/S2B–S2E, or authorize application deployment.

Starting branch main; HEAD and local origin/main both
`1cca9dd1cca9be3a39257f4d3c11ed7de4c53ac3`. Tracked files/index clean; stash empty;
four intentional untracked review documents. Only this fifth evidence document
is created by the migration task; leave it uncommitted.

Inventory provenance and complete two-tenant count come from the independently
approved [S2A.2a inventory](ptm0-s2a2a-provider-ownership-inventory-migration-plan.md).
Its completed scan was not repeated. Fresh strongly consistent projected GetItem
reads confirmed both exact tenant owners and absent calendar_provider,
calendar_enabled and calendar_secret_ref; Alpha remains unconfigured. Primary
assignment remains supported by reviewed 21F/21H records, deployment/source
mapping and zero duplicate bindings in the approved inventory, not secret naming.

## Sanitized pre-image saved before any production write

Preflight UTC: `2026-09-04T12:09:42.907172+00:00`.
STS account: `358604342897`; existing private workload SSO profile used through
the SDK. No credentials/session values were displayed or retrieved as evidence.

Secret ARN:
`arn:aws:secretsmanager:us-east-1:358604342897:secret:togs-and-dogs-prod/google/user-tokens-0zvNfK`

Secret name: `togs-and-dogs-prod/google/user-tokens`.
Exists; not scheduled for deletion; CompanyId absent. Exact original tags:

```json
{
  "Project": "TogsAndDogs",
  "Company": "USMissionHero",
  "ManagedBy": "terraform",
  "CostCenter": "ClientBillable",
  "Repo": "togs_and_dogs_website",
  "Environment": "prod",
  "Client": "TogAndDogs",
  "Application": "PetScheduling",
  "BillingModel": "PassThrough"
}
```

Metadata comparison hashes use SHA-256 of JSON sorted keys, compact separators,
UTF-8, and string conversion for metadata timestamps. No values were accessed.

- Configuration hash: `cabd47c52916330061bf8110b88ffa47aae4cc80f162443c56072ae4d5128e94`.
  Fields: ARN, Name, KmsKeyId, RotationEnabled, RotationLambdaARN, RotationRules,
  OwningService, PrimaryRegion, DeletedDate (missing fields represented as null).
- VersionIdsToStages mapping hash:
  `9c898d5a89910bae616cf8c3224e92ef14b9d66f2a048f44a5cd118e18dc9a64`.
  Two returned version entries. Raw version identifiers/stage mapping were not
  printed or persisted; only this non-secret comparison hash/count was recorded.

IAM policy ARN:
`arn:aws:iam::358604342897:policy/togs-and-dogs-prod-google-secrets`.

Default version: **v2**. Versions present: v2 (default, created
2026-05-07T20:59:48Z), v1 (nondefault, created 2026-04-18T12:27:14Z).
Two of five version slots occupied; no version deletion required or authorized.

Exact decoded existing policy document (object key order is not significant;
statement/list contents and order must be preserved):

```json
{
  "Statement": [
    {
      "Action": ["secretsmanager:GetSecretValue", "secretsmanager:PutSecretValue"],
      "Effect": "Allow",
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:358604342897:secret:togs-and-dogs-prod/google/client-creds-TBSqWN",
        "arn:aws:secretsmanager:us-east-1:358604342897:secret:togs-and-dogs-prod/google/user-tokens-0zvNfK"
      ]
    },
    {
      "Action": ["secretsmanager:GetSecretValue"],
      "Effect": "Allow",
      "Resource": [
        "arn:aws:secretsmanager:us-east-1:358604342897:secret:togs-and-dogs-prod/postmark/server-token-b17s3i"
      ]
    }
  ],
  "Version": "2012-10-17"
}
```

Canonical policy SHA-256:
`1575070c1baa3d14da42f7f2a4df79f60683854ea8de7c8c42800497e8a459b7`.

Role: `arn:aws:iam::358604342897:role/togs-and-dogs-prod-lambda-exec`.
Inline policies: none; PermissionsBoundary: absent. Attached policies:

- `arn:aws:iam::358604342897:policy/togs-and-dogs-prod-cognito-admin`
- `arn:aws:iam::358604342897:policy/togs-and-dogs-prod-dynamodb-access`
- `arn:aws:iam::358604342897:policy/togs-and-dogs-prod-google-secrets`
- `arn:aws:iam::358604342897:policy/togs-and-dogs-prod-lambda-invoke`
- `arn:aws:iam::358604342897:policy/togs-and-dogs-prod-lambda-sfn-start`
- `arn:aws:iam::358604342897:policy/togs-and-dogs-prod-ses-access`
- `arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole`

## Approved execution and rollback boundaries

The independently reviewed inventory names direct CreatePolicyVersion as the
underlying IAM mutation. Use that narrow API with SetAsDefault true, preserving
the live v2 document exactly and appending one separate Allow statement for
DescribeSecret on the exact token ARN. No role attachments, existing Get/Put
permissions, wildcard scopes or runtime Tag/Untag permissions may change.
Do not run Terraform or bundle unrelated infrastructure.

Recheck exact preconditions immediately before writes. Disable SDK retries for
mutation calls; uncertain outcomes require read-only reconciliation, not blind
retry. IAM convergence requires the new default document, old statements,
version set and role attachments to match the expected post-image before tagging.

Only then call TagResource with the one new tag. Post-tag DescribeSecret must
show exactly the previous nine plus CompanyId=tog_and_dogs, unchanged ARN/name,
configuration hash and returned version-stage hash/count.

If IAM verification fails, restore default v2 only after checking the current
default is the migration-created version (stop on unrelated concurrent changes).
Leave nondefault versions intact. If tag succeeds but verification fails, remove
only CompanyId and preserve prior tags; do not modify values or DynamoDB. Report
any rollback and any uncertain result; never silently broaden recovery.

## Managed-source reconciliation boundary

`modules/iam/main.tf` and `modules/secrets/main.tf` remain unchanged under this
two-production-change-only approval. They do not yet declare the added IAM
statement/resource-specific tag. Therefore the approved direct changes create
known desired-source differences, not a claim of Terraform convergence. A later
separately approved source reconciliation must preserve these changes before
any infrastructure apply; never add CompanyId to global common_tags or touch
secret initialization/version resources. No Terraform state/plan/apply is used
here. S2A.3 remains gated on independent migration verification and the reviewed
enforcement/release process.

## Execution results

The sanitized pre-image above was written to this file before either production
mutation. Immediately preceding IAM creation, account, secret ARN/name and nine
tags, policy default/version set/document hash, attachments/inline policies and
role boundary were rechecked. All matched. Before tagging, IAM v3/default/hash
and the original secret tag/configuration/version-stage hashes were rechecked.
No material precondition change was found.

### 1. IAM mutation and convergence

Exactly one `iam:CreatePolicyVersion` on the approved policy ARN, with
`SetAsDefault=true`. Appended this separate statement to a deep copy of the
verified existing v2 document, preserving both original statements and their
Action/Resource lists exactly:

```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:DescribeSecret",
  "Resource": "arn:aws:secretsmanager:us-east-1:358604342897:secret:togs-and-dogs-prod/google/user-tokens-0zvNfK"
}
```

- Created/default version: **v3**, created `2026-09-04T12:12:15Z`.
- AWS request ID: `137791d9-93ff-497c-a2e7-0f08bb58b822`.
- v3 canonical document SHA-256:
  `e4333ff54dbf1a9fe77b18d0a0a9e354e108c32843f282d1cfe7a78403e48474`.
- Original v2 document hash unchanged; v1/v2 retained, no version deletion.
- Version set is exactly v1, v2, v3; default changed only v2 -> v3.
- Two consecutive verification rounds passed: default version, exact v3
  document, unchanged v2 document, expected version set, all seven unchanged
  attachments, no inline policies and no boundary.
- No Get/Put permission change; DescribeSecret is a singleton exact-resource
  statement, not added to the two-resource client/token statement.
- No new wildcard scope; no runtime TagResource/UntagResource grants.

Only after this convergence passed was tagging attempted. Configuration
verification is not a Lambda invocation or runtime credentials probe; no claim
of testing every IAM enforcement point/SCP or all unrelated account resources
is made. Within the inspected policy/role boundaries, all changes were exactly
the approved addition; no unrelated IAM mutation API was called.

### 2. Secret tag mutation and convergence

Exactly one `secretsmanager:TagResource`, with SecretId equal to the approved
full ARN and Tags containing only `{Key: CompanyId, Value: tog_and_dogs}`.

- AWS request ID: `1ac483f1-7edb-4b3a-987e-d99752133250`.
- Final exact tag set is the saved nine-tag pre-image plus
  `CompanyId=tog_and_dogs`: **10 tags**.
- Three DescribeSecret verification reads were used to obtain two consecutive
  complete post-image matches within the bounded convergence loop.
- ARN/name unchanged; configuration hash unchanged at
  `cabd47c52916330061bf8110b88ffa47aae4cc80f162443c56072ae4d5128e94`.
- Returned VersionIdsToStages mapping hash unchanged at
  `9c898d5a89910bae616cf8c3224e92ef14b9d66f2a048f44a5cd118e18dc9a64`;
  returned version count remains **2**.

No secret-version, value, rotation, or secret-configuration mutation API was
called. Metadata comparison supports no observed version/configuration change
during the migration; it is not a content-byte comparison or an exhaustive
historical-version audit. No secret value was accessed to make this claim.

### 3. Final read-only snapshot

Final verification UTC: `2026-09-04T12:14:18.381890+00:00` — **PASS**.

GetPolicy/GetPolicyVersion/ListPolicyVersions confirmed v3 default, unchanged v2
document and exact v1/v2/v3 set. Role attachment/inline/boundary reads matched the
pre-image. DescribeSecret reconfirmed all ten tags and unchanged configuration
and returned version-stage metadata hashes. No extra production write occurred.

Rollback operations: **NONE**. Neither default-version restoration nor
UntagResource was needed or performed. No uncertain write outcome or blind
mutation retry occurred.

## Read/write API ledger and safeguards

Execution used in-memory Python scripts, launched with the verified executable
`C:\Users\mattn\Desktop\lambda_package\python.exe`; boto3 Session profile
`usmissionhero-website-prod`, region `us-east-1`. No application modules were
imported. SDK configuration: 5-second connect/15-second read timeouts and
`total_max_attempts=1`. Convergence loops were bounded to six rounds with
two-second intervals, requiring two consecutive matches. Raw service exceptions
were not printed; only sanitized error categories would have been returned.

Read-only API families actually used in this task:

- STS GetCallerIdentity, checked for exact account before each mutation phase;
  output evidence restricted to account.
- Secrets Manager DescribeSecret on the one approved ARN; tags/configuration
  and version-stage comparison only, no raw response dump or value access.
- DynamoDB GetItem, exactly once for each known tenant in the preflight, strong
  consistency and projection restricted to PK, SK, company_id and three calendar
  binding fields. No Scan repeated; no workflow records requested.
- IAM GetPolicy/GetPolicyVersion/ListPolicyVersions on the approved policy;
  ListAttachedRolePolicies/ListRolePolicies/GetRole on the approved role.

Production mutation calls actually performed: **2**:

1. IAM CreatePolicyVersion(SetAsDefault=true) on the exact policy.
2. Secrets Manager TagResource for only CompanyId on the exact secret.

No Attach/DetachRolePolicy, existing version deletion, inline-policy mutation,
SetDefaultPolicyVersion rollback, UntagResource rollback or other write call.
No Terraform executable/initialization/state/plan/apply command was performed.

## Option B and final boundaries

Option B is now authoritative by Matthew's explicit approval. The earlier
inventory document's request for option ratification is historical and satisfied
by this approval; the original S2A.1 explicit-primary-ref requirement is amended
for the reviewed deliberate primary-compatibility branch only. Ordinary tenants
still require explicit references and matching CompanyId. Failed/implicit tenant
resolution must never become primary authority. This task implements none of
that runtime behavior.

- DynamoDB reference backfill: **NOT PERFORMED / NOT REQUIRED BY OPTION B**.
- Secret values accessed: **ZERO**; Google/provider calls: **ZERO**.
- DynamoDB writes, tenant/provider configuration changes: **ZERO**.
- Terraform commands/operations: **ZERO**; infrastructure-source edits: **ZERO**.
- Runtime/application deployment: **NO**; runtime/tests/Mobile/Stripe/Ryan work:
  **NONE**.
- S2A.3: **NOT STARTED / BLOCKED UNTIL INDEPENDENT MIGRATION REVIEW**.
  S2B–S2E: not started. F02 unresolved; S1 complete; PTM-0 incomplete.
- Only this evidence Markdown file created; prior four review files unchanged.
- No staging, commit or push; HEAD/local origin/main remain
  `1cca9dd1cca9be3a39257f4d3c11ed7de4c53ac3`, branch main.
- Ending tracked worktree/index clean; stash empty; five intentional untracked
  review documents. Markdown local link and whitespace checks pass.

Stop after this evidence record. Independent verification and separately scoped
managed-source reconciliation/enforcement work are subsequent gates, not actions
authorized or begun by this migration task.
