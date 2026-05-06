# Remaining Data Issues Cleanup

**Date:** 2026-05-06
**Executed by:** Targeted script (`scripts/cleanup_data_issues_targeted.py`)
**Table:** `togs-and-dogs-prod-data`

---

## Objective

Following the malformed audit cleanup, 4 records remained flagged as "Data Issues" in the admin portal. This cleanup targeted those specific 4 records, which were verified as non-audit test artifacts.

## Starting State

- **Data Issues count:** 4

## Record Classification & Actions

| Record | Classification | Action Taken | Reason |
| :--- | :--- | :--- | :--- |
| `JOB#1da26dbb-6db7-4bbd-91e7-00aa569273b7` | Orphaned duplicate JOB test record (`status: JOB_CREATED`) | **DELETED** | Superseded by `JOB#0c353779`; not referenced by active `REQ#98394347`. |
| `JOB#0c353779-a12a-42e1-a2da-df19d047b4d7` | Active JOB test record (`status: JOB_CREATED`) | **UPDATED** to `SCHEDULED` | Active `job_id` on `REQ#98394347`. `JOB_CREATED` is not a valid UI status. |
| `PET#45691f4a-7343-4209-ac2e-6b09ff28029d` | Orphaned test PET record (`status: None`) | **DELETED** | No status and no active REQ/JOB references. |
| `PET#1eee3233-e09d-4ac5-9562-ce0c93cccff7` | Active test PET record missing client info | **ENRICHED** | Added `client_name: Test Validation` and `pet_name: Max` to satisfy UI requirements without creating a fake client record. This pet is referenced by the active `REQ#98394347`. |

**Note:** `REQ#98394347-960a-4b8c-a305-5c9229ede605` (`status: APPROVED`) was verified as the active test request and was left completely **INTACT**.

## Backup

A JSON backup of the exact state of all involved records (including the `REQ` and `CLIENT` records for context) was created before any modifications.

- **Backup path:** `backups/data-issues-cleanup/data-issues-backup-2026-05-06-174919.json`

## Execution Results

- `JOB#1da26dbb...`: Successfully deleted.
- `PET#45691f4a...`: Successfully deleted.
- `JOB#0c353779...`: Status updated to `SCHEDULED`.
- `PET#1eee3233...`: Enriched with `client_name` and `pet_name`.

## Post-Cleanup Validation

- **Final Data Issues count:** 0
- **REQ#98394347 intact:** Confirmed (status remains `APPROVED`, `job_id` references `JOB#0c353779`).
- **Real business records deleted:** Confirmed None.
- **Admin Request List loads:** Confirmed (programmatic verification; browser quota limited).
- **System/audit records visible in request list:** Confirmed None.
