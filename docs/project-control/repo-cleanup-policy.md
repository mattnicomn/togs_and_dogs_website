# Repo Cleanup Policy

## File Classification

### Keep (Tracked)
Files that are part of the application, documentation, or test suite.
- `src/` — all application code
- `web/` — all frontend code
- `infra/` — all Terraform configuration
- `docs/` — all documentation
- `tests/` — all test files that are part of a release
- `.gitignore`, `CHANGELOG.md`, `ARCHITECTURE.md`, etc.

### Promote (Untracked → Tracked)
Files that should be committed when their associated feature/release is ready.
- `.kiro/specs/postmark-notifications/` — promote when notification ledger/quota/webhooks are implemented
- `tests/backend/test_r4a_intake.py` — promote if it becomes part of a CI suite

### Archive (Move to docs/archive/)
Files that have historical value but are no longer active.
- Superseded planning docs
- Old validation reports for completed releases
- Deprecated operational guides

### Delete (Remove from Disk)
Files that have no ongoing value and should not be committed.
- One-off validation scripts: `cw_check.ps1`, `cw_cancellation.ps1`, `cw_post_assign.ps1`
- Temp data dumps: `*.json` scan outputs, `*.xlsx` test exports
- API test scripts: `api_test.py`, `api_e2e_test.py`
- DynamoDB query scripts: `find_pending*.py`, `create_test_req.py`, `fix_test_req.py`

## Current Cleanup Candidates

| File | Classification | Action |
|------|---------------|--------|
| `.kiro/specs/postmark-notifications/` | Promote (future) | Keep untracked for now |
| `tests/backend/test_r4a_intake.py` | Promote (future) | Keep untracked for now |
| `cw_cancellation.ps1` | Delete | Safe to remove |
| `infra/prod/backend.zip` | Gitignored | Should be in .gitignore |
| `infra/prod/tfplan` | Gitignored | Should be in .gitignore |
| `infra/prod/tfplan-rollback` | Gitignored | Should be in .gitignore |

## .gitignore Additions Recommended

```
# Terraform artifacts
infra/prod/backend.zip
infra/prod/tfplan
infra/prod/tfplan-rollback
infra/prod/.terraform/

# Validation scripts
cw_*.ps1
```

## Rules

1. **Do not delete files without Matthew's approval** if they might contain useful data
2. **Do not commit temp scripts** — delete them after use or add to .gitignore
3. **Archive rather than delete** documentation that has historical context
4. **Promote untracked files** only when their associated feature is complete and accepted
5. **Review untracked files** at each release checkpoint
