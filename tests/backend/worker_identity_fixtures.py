"""Synthetic only; no customer records, configuration or credentials."""
from common.worker_identity import principal_from_verified_claims, principal_key


def fixture():
    claims = {"iss": "https://issuer.example.invalid/pool-a", "sub": "subject-a",
              "custom:company_id": "tenant_a", "cognito:groups": ["owner"]}
    principal = principal_from_verified_claims(claims, (claims["iss"],), "tenant_a")
    wid = "wrk_" + "1" * 32
    worker = {"PK": "COMPANY#tenant_a", "SK": "WORKER#" + wid, "entity_type": "WORKER",
              "company_id": "tenant_a", "worker_id": wid, "staff_id": "staff-a",
              "contract_version": 1, "version": 1, "is_active": True, "is_assignable": True}
    link = principal_key(principal) | {"entity_type": "PRINCIPAL_WORKER_LINK", "company_id": "tenant_a",
        "issuer": principal.issuer, "subject": principal.subject, "worker_id": wid,
        "staff_id": "staff-a", "contract_version": 1, "version": 1, "is_active": True}
    staff = {"PK": "COMPANY#tenant_a", "SK": "STAFF#staff-a", "company_id": "tenant_a",
             "staff_id": "staff-a", "cognito_sub": "subject-a", "canonical_worker_id": wid,
             "identity_revision": 1, "is_active": True, "is_assignable": True}
    job = {"PK": "JOB#job-a", "SK": "REQ#request-a", "company_id": "tenant_a", "request_id": "request-a",
           "client_id": "client-a", "status": "ASSIGNED", "assigned_worker_id": wid,
           "assignment_contract_version": 1, "assignment_revision": 1, "execution_revision": 1}
    parent = {"PK": "REQ#request-a", "SK": "CLIENT#client-a", "company_id": "tenant_a",
              "request_id": "request-a", "client_id": "client-a", "job_ids": ["job-a", "job-b"],
              "workflow_revision": 1, "status": "ASSIGNED"}
    return principal, worker, link, staff, job, parent
