# PTM0-S2A.1 — Provider ownership contract and migration design

Date: 2026-09-04

Disposition: **PTM0_S2A1_OWNERSHIP_CONTRACT_READY_FOR_INDEPENDENT_REVIEW**

Status: **DESIGN ONLY / UNCOMMITTED / NOT IMPLEMENTED / NOT MIGRATED**

## Authority, checkpoint, and evidence limits

Matthew accepted the [S2A architecture conflict](ptm0-s2a-provider-binding-architecture-conflict.md)
and authorized an ownership contract and migration design, not implementation.
This record supplies that design; it does not retroactively change the earlier
stop record or certify production ownership.

Starting branch: `main`. HEAD and local `origin/main` both:
`1cca9dd1cca9be3a39257f4d3c11ed7de4c53ac3`.
Tracked worktree clean, index and stash empty. Two intentional untracked review
records were present: the architecture conflict above and the
[S2/F02 source review](ptm0-s2-f02-architecture-source-of-truth-review.md).
No remote fetch or live account inspection was performed.

Evidence consists of repository source, fixtures, historical release records,
and public AWS API documentation. Historical records are not current production
inventory. Current secret tags, tenant references, effective IAM permissions,
and upstream Google account ownership remain **unverified**. No secret value
is needed or permitted for this design or the proposed metadata migration.

S1/F01 remains COMPLETE. F02 remains UNRESOLVED; S2A implementation and S2B–S2E
have not begun. PTM-0 remains INCOMPLETE. Tenant resolution, tenants, Stripe,
Ryan testing, Mobile/TestFlight/App Store and production remain unchanged.

## 1. Existing reference and resource contract

| Source | Observed contract / limitation |
| --- | --- |
| `src/backend/common/google_calendar.py`, `resolve_google_token_secret_name` | Optional/None tenant becomes primary. Reads `TENANT#<company_id> / METADATA`; any truthy `calendar_secret_ref` wins without type, returned owner, or secret ownership validation. Primary then falls back to environment/hardcoded legacy reference. Other enabled tenants may use a generated path. |
| Same module, `get_tenant_secret_path` | Derives `<prefix>/calendar/<company_id>/tokens` from `GOOGLE_USER_TOKENS_NAME`, including its ARN-shaped input. Naming is a locator convention, not ownership proof. |
| `src/backend/common/calendar_metadata.py` | Explicit provider fields copy the reference (including null/missing). Absent provider for primary derives Google/legacy-path defaults; other tenants derive none/disabled/null. Truthy record company can override supplied company. These presentation defaults are not authoritative binding evidence. |
| `infra/prod/main.tf`, `modules/secrets/main.tf` and outputs | Shared legacy Google token resource is `<name_prefix>/google/user-tokens`; app client credentials are a separate `<name_prefix>/google/client-creds` resource. Environment wiring supplies secret identifiers. No per-tenant resource ownership lookup exists. |
| `tests/backend/test_r21g_google_token_isolation.py:75` | Explicit `custom/path/to/tokens` is accepted for Alpha. Other fixtures cover primary fallback and enabled-tenant derived paths. This exact custom string is fixture evidence, not proof that it is deployed. |
| `tests/backend/test_r21d_calendar_metadata_defaults.py` | Covers explicit canonical-looking path, primary legacy default, and unconfigured null. |
| `src/backend/common/tenant_provisioning.py` and provisioning flow | No maintained provider-binding registry; provider/secret onboarding is not supplied by the preview tenant builder. |

The source/configuration shapes are: explicit arbitrary string name/path;
environment secret identifier (name or ARN); primary hardcoded legacy name;
derived enabled-tenant path; missing/null/unconfigured reference. Truthy malformed
types are also currently passed through, but are defects, not supported shapes.
The search of tracked runtime/tests/infra/modules found no other
`calendar_secret_ref` consumer or writer. Historical plans also contain proposed
manual metadata backfills, not evidence those writes happened.

[21C](../planning/release-21c-tenant-calendar-provider-metadata-model.md) defines
the reference as string/null and calls tenant paths a future pattern.
[21F](../planning/release-21f-google-per-tenant-token-isolation-plan.md) prioritizes
explicit references over derived paths. Noncanonical names therefore represent
legitimate supported configuration, even though their actual production use is
unknown. Rejecting them just for their spelling would change the contract.

[21H](../release-notes/release-21h-google-per-tenant-token-isolation-production-validation.md)
records primary Google compatibility, Alpha unconfigured, and no token migration
or metadata backfill. It supports investigating the legacy token resource as a
primary-owned candidate; it does not prove present resource tags or exact live
bindings. Its Platform IAM explanation is already qualified by the S2 source
review and is not relied upon here.

## 2. Existing tags and ownership mechanism decision

`infra/prod/locals.tf` defines shared tags:
`Company=USMissionHero`, `Project=TogsAndDogs`, `Environment=<environment>`,
`ManagedBy=terraform`, `Repo=togs_and_dogs_website`, `Client=TogAndDogs`,
`Application=PetScheduling`, `CostCenter=ClientBillable`, `BillingModel=PassThrough`.
`infra/prod/providers.tf` applies these as provider defaults; `modules/secrets/main.tf`
also applies `var.tags` to Google client credentials, Google user tokens, app
secrets and Postmark. They classify platform/project/billing resources. They do
not identify canonical tenant ownership. In particular, neither `Company` nor
`Client` may be reinterpreted as `company_id`.

No authoritative `CompanyId`/`TenantId` secret-owner tag, DescribeSecret ownership
check, or separate DynamoDB provider-binding registry was found in tracked
source/configuration. This is not a claim that no out-of-band live tag exists.

**Recommended new contract key: `CompanyId`.** This is a proposed addition after
reviewing repository and AWS tag conventions, NOT an existing project standard
or a tag created by this task. Its exact, case-sensitive value is the canonical
tenant `company_id`. Its casing follows the existing tag vocabulary while its
meaning remains distinct from platform `Company`. Independent review must ratify
the key. A separately authorized live metadata preflight must check for an
existing authoritative convention; if it finds one, stop and reconcile this
design rather than silently introduce aliases or a competing key.

Apply this ownership field only to a tenant's provider **token** secret. Do not
tag the shared Google OAuth application credentials, Postmark, or other shared
secrets as owned by the primary tenant. Token-secret ownership must be assigned
through the controlled migration manifest, not inferred from the generic tags,
the path, the current requesting tenant, or a display/account label.

AWS `DescribeSecret` returns ARN/name/tags without the secret value and requires
`secretsmanager:DescribeSecret`. Its `OwningService` field identifies an AWS
service, not this application's tenant. Use a projected metadata response, not
a raw response dump. [AWS DescribeSecret](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_DescribeSecret.html).

AWS tags are case-sensitive; setting an existing key overwrites its value. Blank
tag values are allowed by AWS but forbidden by this contract. Consequently a
successful tag API call alone cannot prove a safe ownership migration.
[AWS tagging semantics](https://docs.aws.amazon.com/secretsmanager/latest/userguide/managing-secrets_tagging.html).

**Registry decision:** do not add a DynamoDB binding registry in S2A. It would
create a third writable ownership assertion and synchronization/rollback duties
without independently proving the external resource's owner. Resource tags
provide the requested second side directly. This recommendation depends on
controlled tag/ref writers; tags are not cryptographic ownership evidence. If
that control cannot be established, hold and revisit the model rather than
declare a registry or path convention safe by assumption.

## 3. Proposed steady-state resolver contract

The required equality is:

`explicit resolved tenant == metadata.company_id == secret.Tags[CompanyId]`

1. Receive an explicitly successful tenant resolution; no optional/None/default
   substitution. Validate canonical string identity without trimming, coercing,
   or case-folding mismatches. Existing company-ID syntax is lowercase letters,
   digits and underscores, length 3–64; existing primary remains a valid owner
   (do not reuse provisioning's reserved-ID rejection).
2. Fetch the exact tenant metadata key. Require matching PK/SK and explicit
   `company_id`. Missing/malformed/conflicting metadata denies access. Tenant
   lifecycle, entitlements and provider enablement remain additional gates;
   ownership does not override them or grant Platform Admin tenant-plane access.
3. Require an explicit nonempty string `calendar_secret_ref` for a configured
   token operation. No environment or generated-path fallback, even for primary.
   A legitimately unconfigured provider remains a distinct no-provider result,
   not successful token access or a successful provider mutation.
4. Accept exact friendly names, including `custom/path/to/tokens`, or complete
   ARNs. Resolve in the approved workload account/region; reject partial ARN,
   cross-account/region, or unexpected-resource ambiguity in this slice. Check
   returned name/ARN against the requested locator and use that returned full
   ARN for subsequent operations. Migration evidence pins full ARNs; a name is
   only a locator and cannot itself authorize a replacement resource.
5. Describe that resource; require exactly one valid `CompanyId` equal to the
   resolved tenant and row owner. Reject absent, blank, malformed, inaccessible,
   conflicting, or deletion-pending metadata. Wrong-case lookalike ownership
   fields must not become aliases or override the canonical field; ambiguous
   ownership declarations require correction, not best-effort interpretation.
6. Only then can an otherwise authorized operation use that validated binding.
   A wrong-tenant reference fails even if its path looks canonical. A correctly
   tagged noncanonical name succeeds. Resource ownership is not a statement
   that credentials inside the secret belong to a particular Google account;
   historical assignment provenance must establish that during migration.
7. Carry one validated tenant/ARN binding through the operation. No re-resolution
   with a default tenant or different name between read/refresh/save. Denial
   must precede token read/write, Google refresh/exchange/event calls, revoked
   marking and any downstream application write. Do not log raw SDK errors,
   secret references/tags, token material or cross-tenant details to clients.
8. Metadata lookup failure fails closed, not empty-token success. Especially do
   not convert an ownership failure to `delete_event_detailed`'s current
   success/already-gone result: callers could otherwise remove event references.

No cross-request positive ownership cache is proposed for S2A.3. DynamoDB and
Secrets Manager do not form an atomic snapshot: validate as close as practical
to use and bind the full ARN, but do not claim that repeated reads eliminate a
time-of-check/time-of-use race. Ownership transfer/resource replacement is
forbidden during operations and requires a separately controlled quiesced
migration. Restricting both metadata writers is part of the security model.

Existing handler wrappers can turn missing tenant context into an explicit
primary before the common layer sees it. Common enforcement cannot recover that
lost provenance. S2A.3 must report these integration limits and any required
interface approval; it must not silently implement S2B–S2E or claim F02 resolved.

## 4. IAM implications

`modules/iam/main.tf` grants the shared Lambda execution role GetSecretValue and
PutSecretValue on the configured Google client/token ARNs, and GetSecretValue
on Postmark. It does not grant DescribeSecret, TagResource or UntagResource.
The `secretsmanager:*` mention in `infra/prod/platform_preview_iam.tf` is a
prohibition comment, not an allow. Current effective live permissions are unknown.

Proposed additive runtime requirement: **DescribeSecret on exact approved token
secret ARNs** for the roles that execute the resolver. No ListSecrets, wildcard
secret access, new Get/Put value rights, tag mutations or KMS permission is
needed merely to inspect ownership metadata. Existing Get/Put grants do not
imply Describe permission. Noncanonical refs remain subject to IAM; acceptance
of a name does not authorize expanding access to arbitrary resources.

The role is shared, so a resource tag alone does not bind a request to a tenant
through IAM. Application equality checks remain mandatory. Do not invent
per-request principal tags/ABAC as part of S2A. The current broad tenant-table
write access is also not a tamper-proof ownership control; review reference
writers and restrict unauthorized ownership edits before enforcement release.

A separate, time-bounded migration identity would need DescribeSecret plus
TagResource on the exact approved resources, and UntagResource only for approved
rollback. It must not have secret-value read/write rights for this procedure.
Constrain tag keys/approved values and resource scope in the reviewed policy;
confirm other policies cannot bypass the intended restrictions. Runtime
identities must not gain owner-tag editing authority. Tag-based policy effects,
resource policies, boundaries and organizational denies need metadata-only
effective-policy review under separate authorization.

Conditional tenant-reference backfill, if required, needs exact-item DynamoDB
GetItem/UpdateItem permission and its own explicit approval. Review source and
effective IAM before granting anything; no IAM change occurs in this task.

## 5. S2A.2 migration design — not an executable approval

Migration is required **where** a legitimate configured binding lacks the tag
or an explicit metadata reference. Source defaults make that a real compatibility
dependency; current production need/count cannot be determined from repository
evidence alone. No exact live ARN list or claim of untagged production is invented.

### Gate M0 — independent design and inventory authorization

Approve this contract, the exact tag vocabulary, metadata-only inventory scope
and an accountable ownership assigner. Inventory only approved tenant METADATA
keys and known candidate resources, not workflow records or a table-wide scan.
Use projected, strongly consistent tenant GetItem and DescribeSecret on the
explicit references plus the documented legacy candidate. No GetSecretValue,
BatchGetSecretValue, token/status endpoint, Lambda invocation, Google call or
secret version operation is part of inventory or migration.

For each candidate prepare a reviewed, non-secret manifest containing:

- Canonical tenant ID and exact tenant key; existing owner/reference field
  presence, types and values; provider eligibility (without changing it).
- Exact secret ARN/name/account/region; preexisting CompanyId presence/value,
  conflicting ownership conventions, and unrelated tags to preserve.
- Proposed tag/reference changes and authoritative assignment provenance.
- Exact permissions/source changes, expected verification and per-field inverse.

The authority is Matthew's approved tenant-to-resource assignment backed by
onboarding/migration records and independently checked metadata, not simply
whatever reference a tenant currently contains. For primary, the 21F/21H legacy
history plus exact-resource/operator confirmation is the candidate evidence.
Other/noncanonical secrets need their own equally explicit provenance. If that
evidence is absent, contradictory, shared by multiple tenants, or requires
inspecting token values to settle, STOP without tagging. Existing matching tags
also require provenance review, not automatic adoption of an unexplained tag.

Two friendly-name/ARN aliases for one resource must normalize to the same ARN;
different tenants cannot both own it. Metadata-only evidence proves the routing
assignment, not the upstream contents. No new token secret/tenant/provider
enablement is included. Unconfigured Alpha needs no invented binding.

### Gate M1 — separately approved narrow execution package

Obtain explicit approval for the exact manifest, tag mutations, any conditional
tenant-reference backfill, permission adjustments and rollback. If a row lacks
its own canonical owner, do not silently repair it under reference backfill;
stop for separate tenant metadata review. Preserve existing valid refs (including
noncanonical names). Backfill only genuinely absent references from approved
provenance; malformed/null/conflicting configured refs require explicit review.

Reconcile source ownership of Terraform-managed tags before executing changes:
the repository currently declares only shared `var.tags`. The desired owner
must be resource-specific, **never** added to global `common_tags` or applied to
all secrets. The separately reviewed migration package must specify how the
approved owner tag persists in the actual deployed infrastructure source and
how later reconciliation will avoid removing it. Do not blindly apply current
main, ignore all tags, or touch `google_user_tokens_init`/secret versions. This
design grants no Terraform/source editing or plan/apply authority; the later
metadata/IAM package must request any needed infrastructure approval explicitly.

### Gate M2 — serialized metadata-only migration

Freeze ownership/reference changes for the approved resources and prevent
concurrent control-plane writers; if this cannot be assured, HOLD. Re-read and
match exact approved preconditions immediately before every mutation.

For an absent owner tag only, TagResource adds `CompanyId=<approved company_id>`
to the exact ARN. A matching, provenance-approved tag is a no-op; a conflicting
tag stops, never overwrite it. TagResource has no expected-value/CAS parameter,
so read-then-tag is not an atomic condition; serialization is required. It
requires TagResource permission and can affect tag-based access policies.
[AWS TagResource](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_TagResource.html).

If separately approved, backfill only `calendar_secret_ref` on the existing
metadata item with UpdateItem conditioned on the exact recorded prestate and
matching company owner. Do not PutItem/replace the row, enable the calendar,
change lifecycle/entitlements/status, or create tenant/workflow records.
Apply any separately approved minimal metadata-read IAM addition. Record each
successful step; stop on a mismatch, denial or unexpected change. A partial
migration is not success and does not unlock resolver deployment.

### Gate M3 — independent verification and release interlock

An independent reviewer/identity reads projected tenant metadata and describes
every manifest ARN, establishing the three-way equality, preserved unrelated
fields, exact expected IAM grants and no conflicting resource assignment.
Verify changes against approved API audit events without collecting credentials,
raw responses or secret values. Audit counts must match approved metadata writes;
no secret-version writes or provider calls belong to this procedure.

Secrets Manager changes are eventually consistent. Require bounded repeated
fresh metadata reads during the approved verification window; unresolved or
inconsistent observations HOLD. Do not treat an arbitrary sleep interval or
successful TagResource response as proof of convergence everywhere.
[AWS consistency guidance](https://docs.aws.amazon.com/secretsmanager/latest/userguide/troubleshoot.html).

Record the independent verdict, manifest digest, exact source/IAM review and
verification time. S2A.3 release preparation must require this evidence and
recheck its freshness/binding preconditions before any deployment approval.
Missing evidence, new drift or an unapproved runtime interface dependency blocks
release. No runtime environment switch bypassing ownership is proposed.

### Exact rollback boundaries

Before enforcement deployment, a separately approved rollback can reverse only
steps recorded as changed by this migration:

1. Under the same writer freeze, reread the resource/row and require the exact
   migration-written state. On any intervening change, STOP for review.
2. Restore a backfilled reference to its precise preimage using conditional
   UpdateItem (REMOVE if originally absent). Never overwrite the entire item.
3. Remove only the newly introduced `CompanyId` from the exact ARN using
   UntagResource. Leave preexisting correct owner tags and all other tags alone.
   No ownership overwrite is allowed by the forward migration, so no conflicting
   owner value should ever need restoration.
4. Reverse only the approved additive IAM/source changes if applied, preserving
   prior policies/configuration. Each such operation needs its own approved
   execution mechanism; do not infer permission to run Terraform.
5. Independently repeat projected reads and compare exact preimages. If metadata
   is inconsistent, retain HOLD; do not proceed to resolver deployment.

UntagResource removes specified keys, requires its own permission, and has no
expected-value condition; its access-policy effects and the freeze must be
reviewed just as for tagging.
[AWS UntagResource](https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_UntagResource.html).

After enforcement is deployed, removing required metadata can cause denial.
Do not automatically untag/revert refs or roll back code then. Stop and obtain
separate operational rollback authorization; maintain the fail-closed gate.
No rollback ever reads/writes token values, deletes secrets/versions, rotates
credentials or invokes Google. Metadata rollback is not proof of calendar health.

## 6. Compatibility, decomposition and future tests

Adopt the proposed decomposition:

| Slice | Deliverable / boundary |
| --- | --- |
| S2A.1 | This ownership contract and migration design, independent review only. |
| S2A.2 | Separately approved existing-secret metadata migration, required explicit-ref backfills, scoped metadata IAM/source reconciliation and independent verification. No token-value access or provider activity. |
| S2A.3 | Separately authorized common resolver enforcement and focused offline tests against this contract; release gated on S2A.2 evidence and reviewed caller integration. No automatic deployment. |

No new temporary runtime exception is recommended. The existing deployed backend
remains unchanged while migration/review is pending; that is retention of the
current unresolved risk, not certification that fallback is safe. Require an
explicit follow-up gate, not an indefinite `untagged + primary => allowed` branch.
Primary compatibility in steady state comes from its explicitly registered,
owned legacy secret. No renaming or token migration is necessary for that.

S2A.3's future test matrix must cover exact triple equality; valid noncanonical
and complete-ARN/name aliases; wrong tenant/owner/resource; missing/null/empty/
malformed context, ref and tags; Describe denial/error/deletion; unconfigured
provider versus binding failure; explicit owned primary and no default fallback;
and zero value reads/writes, Google calls or downstream success on denied paths.
Test validated-ARN continuity across refresh/save and the delete-denial sentinel.
Caller provenance laundering and omitted-company paths must remain explicit
integration blockers where outside the common-only scope. These are proposed
tests only: none was added, edited, imported or executed in S2A.1.

## 7. Scope and local verification record

- Only this Markdown design record was created; the two prior review records
  remain unchanged. No runtime, tests, Terraform, scripts or continuity status
  files were edited.
- Local source searches/reads and Git hygiene checks only. Public AWS
  documentation accessed; AWS account/service calls, production access, Google
  access, credential/session inspection and secret-value access: **ZERO**.
- Terraform operations, packaging, deployment, migration and production writes:
  **ZERO**. No S2A.2/S2A.3 or S2B–S2E execution.
- Staging, commits, pushes: **NONE**. HEAD/origin remain at the checkpoint.
- Ending tracked worktree and index clean; stash empty; three intentional
  untracked review Markdown files including this record.

Next step: independent review of the ownership key, assignment provenance,
writer-governance assumptions, migration/rollback gates and common/caller slice
boundary. Design readiness does not authorize inventory, migration, implementation
or release. Stop here.
