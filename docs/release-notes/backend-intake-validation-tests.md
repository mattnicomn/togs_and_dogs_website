# Backend Intake Validation Tests

## Purpose
Ensure that all incoming `Request Care` submissions are valid, complete, and secure, preventing the creation of malformed or "UNKNOWN" records in the system.

## Test Coverage
- **Valid Intake**: Confirms that correctly formatted requests are saved with `PENDING_REVIEW` status and appropriate metadata.
- **Field Validation**: 
    - Rejects requests missing `pet_names`.
    - Rejects requests with empty or whitespace-only `pet_names`.
    - Rejects requests missing `client_name`.
- **Security / Injection Protection**:
    - Verifies that any `status` field provided by the caller is ignored, ensuring new requests always start as `PENDING_REVIEW`.
- **Database Integrity**:
    - Mocks DynamoDB writes to verify that no data is persisted for invalid requests.

## Production Code Changes
- **`intake_handler.py`**: Hardened the validation logic to check for blank or whitespace-only strings in required fields (`client_name`, `client_email`, `start_date`, `pet_names`).

## How to Run Tests
Run the following command from the project root:
```bash
pytest tests/backend/test_intake_validation.py
```

## Known Limitations / Gaps
- Currently enforces `client_name`, `client_email`, `start_date`, and `pet_names`.
- Does not yet validate date formats (e.g., ensuring `start_date` is a valid ISO string).
- Does not yet validate email format beyond being non-empty.
