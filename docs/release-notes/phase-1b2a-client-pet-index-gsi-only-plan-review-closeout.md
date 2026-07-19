# Phase 1B.2A: ClientPetIndex GSI-Only Plan Review Closeout

**Date:** 2026-07-19
**Reviewer:** Kiro
**Status:** ✅ READY FOR CLIENTPETINDEX APPLY APPROVAL

---

## Commits Reviewed

| Commit | Description |
|--------|-------------|
| `757cabb` | feat(infra): restore ClientPetIndex configuration |
| `9577421` | docs: record ClientPetIndex GSI-only Terraform plan |

## Saved Plan Identity

| Item | Value |
|------|-------|
| Filename | `infra/prod/phase-1b2a-client-pet-index-gsi-only.tfplan` |
| SHA256 | `858986d96a673ba7256bb0c4b369216f69220fb6d3d5d4310664c51e5d7ef90a` |
| Summary | **0 to add, 1 to change, 0 to destroy** |

## Exact Resource and Action

- Resource: `module.data.aws_dynamodb_table.main`
- Action: **in-place update**
- Adds: `client_id` attribute (String), `pet_id` attribute (String), `ClientPetIndex` GSI
- GSI configuration: hash_key=`client_id`, range_key=`pet_id`, projection=ALL
- No replacement
- No destruction
- No Lambda changes
- No unrelated resource changes

## Preserved Table Configuration

- ✅ Table name unchanged
- ✅ PAY_PER_REQUEST billing unchanged
- ✅ PK (String) + SK (String) primary key unchanged
- ✅ StatusIndex (status + created_at) unchanged
- ✅ WorkerIndex (worker_id + assigned_at) unchanged
- ✅ TTL (expires_at) unchanged
- ✅ Tags unchanged
- ✅ No provisioned throughput, autoscaling, streams, or table replacement

## Index Participation Expectations (From Previous Dry-Run)

| Category | Count | GSI Behavior |
|----------|-------|-------------|
| Total PET records | 84 | — |
| Expected to enter ClientPetIndex (have valid client_id + pet_id) | 81 | Indexed |
| Of those: have company_id (tenant-defensible) | 68 | Returned by future backend |
| Of those: lack company_id (excluded by future tenant defense) | 13 | Indexed but operationally filtered out |
| Lack one or both GSI key attributes | 3 | NOT indexed |

## Rollout Requirements

- The plan represents an in-place DynamoDB table update
- No application code currently queries ClientPetIndex
- DynamoDB will automatically backfill eligible items into the index
- Index status must be monitored until `ACTIVE`
- Backend query cutover is prohibited until status reaches ACTIVE
- GSI queries are eventually consistent
- Application behavior remains completely unchanged until a separately approved backend deployment
- Operational monitoring is required during creation and backfill

## Future Tenant-Defense Requirements (Not Part of GSI Apply)

The future backend implementation must:
1. Derive trusted company_id from authenticated tenant context
2. GetItem canonical client: `PK=COMPANY#{company_id}, SK=CLIENT#{client_id}`
3. Return safe not-found/denial if ownership invalid
4. Query ClientPetIndex by client_id
5. Paginate all pages until LastEvaluatedKey absent
6. Reject/omit PET results with missing or mismatched company_id
7. Preserve active-only semantics (missing is_active = active)
8. Preserve existing `{"pets": [...]}` response contract
9. Never fall back to Scan

## Release Gates Status

- ✅ Backend Lambda deployment complete and manually smoke-tested
- ✅ ClientPetIndex configuration restored
- ✅ GSI-only plan saved and reviewed
- ⬜ GSI apply (requires separate Matthew approval)
- ⬜ Monitor GSI until ACTIVE
- ⬜ Backend query-cutover implementation
- ⬜ Backend query-cutover deployment
- ⬜ Frontend pet inventory implementation
- ⬜ Frontend deployment
- Old combined Lambda/GSI plan: must NEVER be applied
- Remediation: remains deferred

---

## Next Approval Gate

**Matthew approves applying the saved GSI-only plan:**
```
terraform -chdir=infra/prod apply phase-1b2a-client-pet-index-gsi-only.tfplan
```

This adds the ClientPetIndex GSI to the production DynamoDB table. No Lambda, API Gateway, IAM, Cognito, or other changes. Index backfill begins automatically. Application behavior is unchanged until a future backend deployment.
