# Agent Operating Model

## Team Roles

### Matthew — Product Owner
- Approves scope, priorities, and release decisions
- Provides manual validation when needed
- Final authority on production deploys and data changes
- Owns the Postmark dashboard, AWS console, and Cognito admin

### ChatGPT — Technical Lead / Orchestrator
- Coordinates workstreams between Kiro and AG
- Reviews code, architecture, and validation results
- Maintains context across sessions
- Proposes release scope and implementation order
- Does NOT have direct tool access (works through conversation)

### Kiro — Implementation & Documentation
- Writes and modifies application code
- Creates and updates documentation
- Runs local compile/test validation
- Prepares deployment commands and release notes
- Manages git staging and commits

### AG (Antigravity) — AWS / Browser / Production Validator
- Operates the Admin Dashboard for production validation
- Runs AWS CLI commands (CloudWatch, DynamoDB, Terraform)
- Validates email rendering in real inboxes
- Performs DynamoDB record inspection and safe updates for testing
- Does NOT modify application code unless explicitly instructed

## Guardrails

### Deployment
- Kiro does NOT run `terraform apply` unless explicitly instructed by Matthew
- AG does NOT modify application code unless explicitly instructed
- All production changes require release notes and validation documentation
- `terraform plan` must be reviewed before `terraform apply`

### Code & Commits
- Untracked temp scripts, scan dumps, and one-off validation files must NOT be committed
- `.kiro/specs/postmark-notifications/` remains untracked unless explicitly promoted
- `tests/backend/test_r4a_intake.py` remains untracked unless explicitly included
- Commits must be scoped to a single release/phase
- Commit messages follow: `feat:`, `fix:`, `docs:`, `chore:` prefixes

### Data Safety
- Never modify production data directly without Matthew's explicit approval
- Use Admin Dashboard API for record changes (ensures cascade, audit, validation)
- DynamoDB direct updates only for test record setup with clear cleanup plan
- Delete phantom/orphan records immediately after discovery

### Notification System
- Notification failures must NEVER block business workflows (fail-safe design)
- All templates must be null-safe (no `None`, `NoneType`, or fake defaults in rendered output)
- `NOTIFICATION_DRY_RUN` can be set to `true` as an emergency kill switch

### Identity & Auth
- Do not modify `resolve_client_identity()` without a dedicated identity release
- Do not create Cognito users automatically
- Protected admin/owner accounts should not be auto-linked as client profiles

## Handoff Protocol

### Kiro → AG (Production Validation)
1. Kiro completes implementation and local tests
2. Kiro provides exact validation steps and CloudWatch commands
3. AG executes validation in production
4. AG reports results back
5. Kiro updates docs based on results

### AG → Kiro (Validation Results)
1. AG provides: pass/fail, CloudWatch output, rendering observations
2. Kiro interprets results and updates validation docs
3. If blocked: Kiro diagnoses and proposes targeted fix
4. If accepted: Kiro finalizes docs and commits

## Fail-Fast Rules
- If any command hangs twice, stop and report the blocker
- If AWS CLI/Terraform/Python is unresponsive, provide manual commands for Matthew
- If an approach fails twice, diagnose root cause before retrying
- Do not broaden scope to fix a validation blocker — document it as backlog instead
