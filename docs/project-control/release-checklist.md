# Release Checklist

## Pre-Release

- [ ] Code changes complete and saved
- [ ] `py -m py_compile` passes for all modified `.py` files
- [ ] Local tests pass (`py tests/backend/test_*.py`)
- [ ] Language server diagnostics show no errors
- [ ] `git status` shows only intended files modified/untracked
- [ ] Release notes created/updated
- [ ] Validation checklist prepared for AG

## Deploy (Backend)

- [ ] AWS SSO session refreshed: `aws sso login --profile usmissionhero-website-prod`
- [ ] Delete stale zip if needed: `del infra\prod\backend.zip`
- [ ] `terraform plan` — confirm Lambda code hash updates ONLY
- [ ] Verify: 0 added, 0 destroyed, no IAM/DynamoDB/API Gateway/Secrets changes
- [ ] `terraform apply -auto-approve` (only after Matthew approves)
- [ ] Confirm apply completes successfully

## Deploy (Frontend)

- [ ] `npm run build` passes
- [ ] `aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod`
- [ ] `aws cloudfront create-invalidation --distribution-id E35L00QPA2IRCY --paths "/*"`
- [ ] Confirm invalidation ID returned

## Post-Release Validation

- [ ] AG performs production validation per the validation playbook
- [ ] CloudWatch logs checked for errors (CRITICAL_FAILURE, AttributeError)
- [ ] Email rendering confirmed (if notification change)
- [ ] No regressions in existing functionality
- [ ] Validation report updated with results

## Acceptance

- [ ] Matthew confirms validation passed
- [ ] Release notes marked as Accepted
- [ ] `docs/release-notes/index.md` updated
- [ ] Final commit includes all code + docs
- [ ] `git status` clean (only known untracked items remain)

## Rollback

**IMPORTANT:** Rollback `terraform apply` requires Matthew's explicit approval before execution, same as production deploy. Do not execute rollback without confirmation.

### Notification Emergency
```
# In infra/prod/locals.tf:
NOTIFICATION_DRY_RUN = "true"
# Then (requires Matthew approval):
terraform apply -auto-approve
```

### Full Backend Revert
```
git log --oneline -5  # Find the last good commit
git checkout <commit> -- src/backend/
# Requires Matthew approval:
terraform apply -auto-approve
```

### Frontend Revert
```
git checkout <commit> -- web/
npm run build
# Requires Matthew approval:
aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod
aws cloudfront create-invalidation --distribution-id E35L00QPA2IRCY --paths "/*"
```
