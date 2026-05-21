# Lessons Learned

## Notification System

### Null-Safety is Non-Negotiable
- `context.get('key', 'default')` does NOT protect against explicit `None` values (key exists but value is None)
- Always use `context.get('key') or 'default'` pattern
- The `_safe(value, default)` helper was created to standardize this
- Every template field must have a safe fallback — no exceptions

### Notification Failures Must Never Block Workflows
- The entire `notify_event()` function is wrapped in try/except
- Any crash inside notification code returns `{"success": False}` without propagating
- This is critical — a template bug should never prevent a client from being approved

### Workflow Type Gates Notification Routing
- `VISIT_CANCELLED` only fires for `VISIT_BOOKING`, not `CUSTOMER_INTAKE`
- Always check `determine_workflow_type()` when debugging "notification didn't fire"
- The explicit `workflow_type` field on the record takes priority over heuristics

### Multi-Recipient Templates Need Neutral Tone
- `VISIT_CANCELLED` goes to client + staff + admin (same email)
- Cannot use "Hi {client_name}" — recipient may be staff or admin
- Use neutral greeting: "Hello,"

## DynamoDB / Data

### DynamoDB `update-item` Creates Records If Key Doesn't Exist
- Using `update-item` with a wrong PK/SK creates a phantom record
- Always verify the correct PK/SK before running DynamoDB updates
- Clean up phantoms immediately after discovery

### Keep Count Logic and Filter Logic Aligned
- If a filter predicate changes, the sidebar count must use the same predicate
- Mismatch causes "3 items shown but count says 5" confusion
- Both use `getFilterPredicate()` — keep them in sync

### Never Allow Active/Scheduled Records to Appear in Trash
- `isDeletedRecord()` must be checked before `isActiveRecord()`
- Terminal statuses: DELETED, TRASH, ARCHIVED, COMPLETED, CANCELLED
- Active records are everything NOT in a terminal status AND not a data issue

## Identity / Auth

### Cognito Identity and App Profile Data Need Clear Boundaries
- Cognito `sub` = authentication identity
- CLIENT# record = application profile
- `resolve_client_identity()` bridges them via `cognito_sub` or email match
- Admin/owner accounts in Cognito should NOT auto-resolve to client profiles
- "Linked" in Admin UI means CLIENT# record has `cognito_sub` — but portal resolution also requires `role == 'client'`

### Protected Accounts Must Not Be Auto-Linked
- `mbn@usmissionhero.com` is both an admin login AND has a client profile
- This creates confusion — portal says "not linked" because resolver rejects non-client roles
- Future: warn before linking protected admin/staff accounts to client profiles

## Deployment / Terraform

### `archive_file` Caching
- Terraform's `archive_file` data source may not detect file changes if the output zip already exists
- Delete `infra/prod/backend.zip` to force regeneration
- If plan still shows "no changes," the code was already deployed in a prior apply

### AWS SSO Sessions Expire Frequently
- AWS CLI hangs when SSO token expires (blocks non-interactive terminals)
- Always run `aws sso login --profile usmissionhero-website-prod` before CLI operations
- Kiro's terminal cannot complete interactive SSO — provide manual commands instead

### OneDrive Path Complexity
- Workspace is on OneDrive (`C:\Users\mattn\OneDrive\Desktop\...`)
- This can cause file sync delays and path resolution issues
- Terraform and Python may read stale file versions if OneDrive hasn't synced

## Validation

### Check the Right Lambda
- Admin Dashboard "Cancel" button → review Lambda (not cancellation Lambda)
- CareCard assignment dropdown → assign Lambda (not review Lambda)
- Always verify which Lambda handles the action before checking logs

### Postmark Test Mode Restricts Recipients
- Until account is approved, only `@usmissionhero.com` addresses receive emails
- Gmail/external addresses silently fail (Postmark rejects them)
- Always use `@usmissionhero.com` test addresses during validation
