# Release 1: Scheduling & Record Integrity

**Deployed:** 2026-05-11  
**Environment:** Production  
**CloudFront Invalidation:** IB0NBV163G0JGB9D2ZAPKZLRYY

---

## Files Deployed

### Backend (Lambda code update via Terraform)
| File | Change |
|------|--------|
| `src/backend/common/cascade.py` | NEW — REQ → JOB cascade utility |
| `src/backend/handlers/cancellation_handler.py` | Added cascade to JOB on cancel decision |
| `src/backend/handlers/review_handler.py` | Replaced inline JOB update with cascade utility |
| `src/backend/handlers/job_handler.py` | Copies end_date and visit_window to JOB |
| `src/backend/handlers/admin_handler.py` | Filters JOB# from request list + adds cascade to bulk actions |

### Frontend (S3 + CloudFront)
| File | Change |
|------|--------|
| `web/src/components/AdminDashboard.jsx` | Excludes JOB# from list/Data Issues, adds Restore to Approved |

### Documentation (not deployed — repo only)
| File | Purpose |
|------|---------|
| `docs/planning/intake-client-scheduling-modernization-evaluation.md` | Discovery document |
| `docs/planning/release-1-scheduling-record-integrity-plan.md` | Implementation plan |
| `docs/planning/release-1-scheduling-record-integrity-validation.md` | Validation report |

---

## Behavior Changed

### 1. Request List — No More Duplicate Rows
- **Before:** Both parent REQ# and child JOB# records appeared as separate rows in the admin Request List. The same booking showed twice in "Scheduled with Staff."
- **After:** Only parent REQ# records appear. One booking = one row.

### 2. Consistent Cancel/Archive/Trash Cascade
- **Before:** `review_handler` cascaded status to JOB records, but `cancellation_handler` did not. This caused orphaned JOB records stuck in ASSIGNED after parent was cancelled.
- **After:** All lifecycle transitions cascade from REQ → JOB via shared `cascade_status_to_job()` utility.

### 3. Rollback Consistency
- **Before:** Rolling back ASSIGNED → APPROVED removed `worker_id` from REQ but not from JOB, causing JOB to appear in Data Issues.
- **After:** Rollback removes `worker_id` from both REQ and JOB. JOB status resets to JOB_CREATED.

### 4. Data Issues Cleanup
- **Before:** JOB# records with missing worker_id appeared in Data Issues.
- **After:** JOB# records are excluded from Data Issues entirely. Only parent REQ# records with actual data problems appear.

### 5. Recovery Action
- **Before:** Cancelled/Archived/Deleted records could only be reopened to Pending Review.
- **After:** "Restore to Approved" action available for Cancelled, Archived, and Deleted records. Restores to APPROVED status (ready for re-assignment). Owner/admin only.

### 6. JOB Record Completeness
- **Before:** JOB records only copied `start_date` from parent REQ.
- **After:** JOB records also copy `end_date` and `visit_window` for full scheduling context.

---

## Live Validation Checklist

| # | Test | Expected | Result |
|---|------|----------|--------|
| 1 | Request List → Scheduled with Staff | One row per booking | ☐ |
| 2 | Overnight booking display | Single row with date range | ☐ |
| 3 | Record details still accessible | Customer, service, staff, dates visible | ☐ |
| 4 | Scheduler Day/Week views | Shows upcoming work correctly | ☐ |
| 5 | Data Issues filter | No JOB# records, only real REQ# issues | ☐ |
| 6 | Cancelled records | Show "Restore to Approved" action | ☐ |
| 7 | Archived records | Show "Restore to Approved" action | ☐ |
| 8 | Active records | Do NOT show "Restore to Approved" | ☐ |
| 9 | No console errors | Browser dev tools clean | ☐ |
| 10 | API responses | 200 OK on admin/requests calls | ☐ |

---

## Known Limitations

1. **Existing orphaned JOB records** remain in DynamoDB but are invisible to the admin. They don't affect user experience. A future cleanup script can address these if needed.

2. **"Restore to Approved" is MVP recovery.** It always restores to APPROVED regardless of the record's previous state. Future enhancement: track `previous_status` for exact-state recovery.

3. **MasterScheduler uses REQ records only.** Since REQ records have all scheduling fields (start_date, end_date, worker_id, service_type, visit_window), this works correctly. If future features need JOB-specific data in the scheduler, a separate data path would be needed.

---

## Rollback Instructions

If issues are discovered:

### Backend Rollback
```bash
# Revert to previous commit
git stash  # or git checkout -- src/backend/
# Re-run terraform apply to deploy previous code
terraform apply -auto-approve
```

### Frontend Rollback
```bash
# Rebuild from previous commit
git stash -- web/src/components/AdminDashboard.jsx
npm run build  # in web/
aws s3 sync web/dist/ s3://togs-and-dogs-prod-toganddogs-hosting --delete --profile usmissionhero-website-prod
aws cloudfront create-invalidation --distribution-id E35L00QPA2IRCY --paths "/*" --profile usmissionhero-website-prod
```

### Risk Assessment
- **Rollback is safe.** No schema changes, no data migration, no destructive operations.
- **Data is unaffected.** All changes are read/filter/cascade logic. Existing records are unchanged.

---

## Release 2 Readiness

**Release 2 intake enhancements can begin after live validation is confirmed.**

The record integrity foundation is in place:
- Request List shows one row per booking
- All lifecycle actions cascade consistently
- Recovery path exists for accidental state changes
- JOB records are managed internally

Release 2 scope (planned):
- Multi-select visit window
- Preferred sitter field
- Structured per-pet fields
- Client profile automation
- Quote/payment inline editing
