# Backend RBAC and Purge Safety Tests

## Purpose
To ensure continuous validation of security-critical administrative behaviors and prevent regressions in authorization or destructive lifecycle operations.

## Test Coverage
- **Role-Based Access Control (RBAC)**:
    - Verified that only `Admin` and `Owner` roles can access lifecycle and management APIs.
    - Verified that `Staff` and `Client` roles are correctly denied access (403 Forbidden) to administrative endpoints.
- **Purge Safety**:
    - Verified that permanent deletion (`PURGE`) is strictly blocked for any record not in `DELETED` status.
    - Verified that `PURGE` actions on `DELETED` records are successful and traceable.
- **Malformed Record Handling**:
    - Verified that malformed or missing-status records can be safely moved to Trash (`DELETED`) by authorized users.
    - Verified that malformed records cannot be directly purged without first being moved to Trash.
- **Bulk Operation Integrity**:
    - Verified that bulk purge operations skip non-`DELETED` records.
- **Audit Logging**:
    - Verified that all destructive and sensitive actions generate appropriate audit records, including success and rejection cases.

## Test Framework
- **Framework**: `pytest`
- **Mocking**: `unittest.mock` (Mocked DynamoDB table and Audit service)
- **Location**: `tests/backend/test_rbac_and_purge_safety.py`

## How to Run Tests
1. Ensure `pytest` is installed.
2. Run the following command from the root directory:
   ```bash
   pytest tests/backend/test_rbac_and_purge_safety.py
   ```

## Corrective Actions
During test development, a scope-shadowing issue with the `uuid` module in `admin_handler.py` was identified and resolved. This fix ensures stable execution of bulk operations and audit logging.

## Production Status
- **Backend**: Updated with `uuid` scope fix.
- **Deployment**: Synchronized with Terraform state.
